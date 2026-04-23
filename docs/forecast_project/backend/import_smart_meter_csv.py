import argparse
import csv
from pathlib import Path
from datetime import datetime, timezone

from supabase_client import get_supabase

SMART_METER_TABLE = "smart_meter_reading"
REQUIRED_COLUMNS = ["meter_B", "freeze_date", "A+KWH"]


def _normalize_freeze_date(value: str) -> str | None:
    value = (value or "").strip()
    if not value:
        return None

    # Accept both "YYYY-MM-DD HH:MM:SS" and ISO formats.
    try:
        if "T" in value:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        else:
            dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            dt = dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_row(row: dict) -> dict | None:
    meter = (row.get("meter_B") or "").strip()
    freeze_raw = row.get("freeze_date")
    kwh_raw = row.get("A+KWH")

    if not meter:
        return None

    freeze_date = _normalize_freeze_date(str(freeze_raw or ""))
    if freeze_date is None:
        return None

    try:
        kwh = float(kwh_raw)
    except (TypeError, ValueError):
        return None

    if kwh < 0:
        return None

    return {
        "meter_B": meter,
        "freeze_date": freeze_date,
        "A+KWH": kwh,
    }


def import_csv(
    csv_file: str,
    batch_size: int = 5000,
    limit: int | None = None,
    mode: str = "upsert",
) -> None:
    csv_path = Path(csv_file).expanduser().resolve()
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    client = get_supabase()

    inserted = 0
    read_rows = 0

    batch: list[dict] = []
    seen_in_batch: set[tuple[str, str]] = set()

    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"CSV is missing required columns: {missing}")

        for raw in reader:
            read_rows += 1
            parsed = _parse_row(raw)
            if parsed is None:
                continue

            key = (parsed["meter_B"], parsed["freeze_date"])
            if key in seen_in_batch:
                continue

            seen_in_batch.add(key)
            batch.append(parsed)

            if limit is not None and inserted + len(batch) >= limit:
                batch = batch[: max(limit - inserted, 0)]

            if len(batch) >= batch_size or (limit is not None and inserted + len(batch) >= limit):
                if batch:
                    if mode == "insert":
                        client.table(SMART_METER_TABLE).insert(batch).execute()
                    else:
                        client.table(SMART_METER_TABLE).upsert(
                            batch,
                            on_conflict="meter_B,freeze_date",
                        ).execute()
                    inserted += len(batch)
                print(f"Read {read_rows} rows, inserted {inserted} rows...")
                batch = []
                seen_in_batch.clear()

            if limit is not None and inserted >= limit:
                break

    if batch and (limit is None or inserted < limit):
        if mode == "insert":
            client.table(SMART_METER_TABLE).insert(batch).execute()
        else:
            client.table(SMART_METER_TABLE).upsert(
                batch,
                on_conflict="meter_B,freeze_date",
            ).execute()
        inserted += len(batch)
        print(f"Read {read_rows} rows, inserted {inserted} rows...")

    print("Done.")
    print(f"Imported rows: {inserted}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import smart meter CSV into Supabase")
    parser.add_argument(
        "--csv",
        default="../data/test_data_for_db.csv",
        help="Path to CSV file containing meter_B, freeze_date, A+KWH",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5000,
        help="Rows per insert batch",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional max rows to insert (useful for testing)",
    )
    parser.add_argument(
        "--mode",
        choices=["upsert", "insert"],
        default="upsert",
        help="Import mode. 'upsert' is idempotent and safe for reruns.",
    )

    args = parser.parse_args()
    import_csv(args.csv, args.batch_size, args.limit, args.mode)

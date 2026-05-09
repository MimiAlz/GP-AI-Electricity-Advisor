"""
NILM Monthly Electricity Bill Generator
========================================
Usage:
    python nilm_bill.py --csv path/to/month_data.csv
    python nilm_bill.py --csv path/to/month_data.csv --account "Ahmad Al-Rashid" --balance 5.200

The CSV must have:
  - A timestamp column (first column, Unix seconds or parseable datetime)
  - A 'WHE' column (or 'Whole-House Meter') for the aggregate power in Watts

All appliance models and their metadata are loaded from ./checkpoints/
Cross-correlation profiles are loaded from ./nilm_datasets/
"""

import os
import sys
import json
import argparse
import math
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from datetime import datetime


# ─────────────────────────────────────────────────────────────────────────────
# 1. CONFIG — must match preprocessing notebook exactly
# ─────────────────────────────────────────────────────────────────────────────

MAINS_COL          = 'Whole-House Meter'
WATTS_ON_THRESHOLD = 50.0
N_CHANNELS         = 7
MINUTES_PER_STEP   = 1.0          # AMPds is 1-minute resolution

CONTEXT_CONFIG = {
    'Clothes Dryer' : {'lead': 30, 'trail': 30},
    'Clothes Washer': {'lead':  5, 'trail': 15},
    'Dishwasher'    : {'lead': 30, 'trail': 30},
    'Heat Pump'     : {'lead': 60, 'trail': 60},
    'Kitchen Fridge': {'lead': 10, 'trail': 10},
}

MIN_EVENT_DURATION = {
    'Clothes Dryer' : 10,
    'Clothes Washer': 10,
    'Dishwasher'    : 10,
    'Heat Pump'     :  5,
    'Kitchen Fridge':  2,
}

MERGE_GAP_CONFIG = {
    'Clothes Dryer' : 0,
    'Clothes Washer': 0,
    'Dishwasher'    : 0,
    'Heat Pump'     : 0,
    'Kitchen Fridge': 0,
}

# ─────────────────────────────────────────────────────────────────────────────
# 2. NEPCO Residential Tiered Tariff (JD / kWh)
#    Source: NEPCO residential tariff schedule — cumulative monthly tiers
# ─────────────────────────────────────────────────────────────────────────────

NEPCO_TIERS = [
    (160,           0.033),   # 0–160 kWh      → 33 fils/kWh
    (300,           0.078),   # 161–300 kWh    → 78 fils/kWh
    (500,           0.113),   # 301–500 kWh    → 113 fils/kWh
    (600,           0.156),   # 501–600 kWh    → 156 fils/kWh
    (750,           0.188),   # 601–750 kWh    → 188 fils/kWh
    (1000,          0.220),   # 751–1000 kWh   → 220 fils/kWh
    (float('inf'),  0.288),   # >1000 kWh      → 288 fils/kWh
]
FIXED_CHARGE_JD = 0.70        # fixed monthly service charge


def calc_nepco_bill(total_kwh: float) -> float:
    """Total monthly bill in JD for a given consumption."""
    charge = FIXED_CHARGE_JD
    prev   = 0.0
    for ceiling, rate in NEPCO_TIERS:
        if total_kwh <= prev:
            break
        chunk   = min(total_kwh, ceiling) - prev
        charge += chunk * rate
        prev    = ceiling
    return round(charge, 3)


def attribute_appliance_cost(app_kwh: float, total_kwh: float) -> float:
    """
    Proportional share of the variable (non-fixed) bill for one appliance.
    """
    if total_kwh <= 0 or app_kwh <= 0:
        return 0.0
    fraction      = app_kwh / total_kwh
    total_bill    = calc_nepco_bill(total_kwh)
    variable_bill = max(total_bill - FIXED_CHARGE_JD, 0.0)
    return round(fraction * variable_bill, 3)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Feature Engineering — exact copy from preprocessing notebook
# ─────────────────────────────────────────────────────────────────────────────

def normalize_with_cap(arr: np.ndarray, cap: float) -> np.ndarray:
    arr = np.clip(arr, 0, None).astype(np.float32)
    if cap <= 0:
        return arr
    return np.clip(arr / cap, 0.0, 1.0).astype(np.float32)


def compute_autocorr(window: np.ndarray) -> np.ndarray:
    n      = len(window)
    w      = window - window.mean()
    var    = np.var(w) + 1e-8
    result = np.zeros(n, dtype=np.float32)
    result[0] = 1.0
    for lag in range(1, n):
        result[lag] = float(np.mean(w[:n - lag] * w[lag:]) / var)
    return np.clip(result, -1.0, 1.0)


def compute_crosscorr(window: np.ndarray, profile: np.ndarray) -> np.ndarray:
    n = min(len(window), len(profile))
    if n == 0:
        return np.zeros(len(window), dtype=np.float32)
    w     = window[:n] - window[:n].mean()
    p     = profile[:n] - profile[:n].mean()
    denom = float(np.std(w) * np.std(p)) + 1e-8
    corr  = float(np.clip(np.mean(w * p) / denom, -1.0, 1.0))
    return np.full(len(window), corr, dtype=np.float32)


def compute_delta(window: np.ndarray) -> np.ndarray:
    delta = np.diff(window.astype(np.float32), prepend=window[0])
    return np.clip(delta, -1.0, 1.0).astype(np.float32)


def compute_delta2(window: np.ndarray) -> np.ndarray:
    delta  = np.diff(window.astype(np.float32), prepend=window[0])
    delta2 = np.diff(delta, prepend=delta[0])
    return np.clip(delta2, -1.0, 1.0).astype(np.float32)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Event Extraction — aggregate only (no appliance column needed)
# ─────────────────────────────────────────────────────────────────────────────

def extract_aggregate_events(
    df: pd.DataFrame,
    appliance: str,
    norm_caps: dict,
    crosscorr_profile: np.ndarray,
    lead: int,
    trail: int,
    min_duration_min: int,
) -> list:
    """
    Extract event-shaped windows from the aggregate signal.

    Because we have NO appliance sub-meter during inference, we can't know
    the exact start/end of each appliance event.  Instead we use a
    power-change detector on the aggregate: any sustained rise > WATTS_ON_THRESHOLD
    for at least min_duration_min minutes is treated as a candidate event window.

    The window is then featurised identically to the training pipeline so
    the model receives the same 7-channel input it was trained on.
    Each window will be classified independently by the appliance model.
    """
    mains_arr = df[MAINS_COL].values.astype(np.float64)
    times     = df.index
    n         = len(mains_arr)
    cap_m     = norm_caps[MAINS_COL]

    # ── Detect candidate "something turned on" windows in the aggregate ──────
    # Strategy: smooth the signal, then threshold the absolute delta to find
    # transitions, then group into ON periods of sufficient length.
    smoothed = pd.Series(mains_arr).rolling(3, min_periods=1, center=True).mean().values
    baseline = pd.Series(mains_arr).rolling(60, min_periods=1).min().values
    above    = (smoothed - baseline) > WATTS_ON_THRESHOLD

    diff   = np.diff(above.astype(int), prepend=0)
    starts = list(np.where(diff == 1)[0])
    ends   = list(np.where(diff == -1)[0])
    if len(starts) > len(ends):
        ends.append(n - 1)

    patterns = []
    for s, e in zip(starts, ends):
        duration = e - s
        if duration < min_duration_min:
            continue

        i_start = max(0, s - lead)
        i_end   = min(n, e + trail)
        mains_seg = mains_arr[i_start:i_end]
        L = len(mains_seg)
        if L == 0:
            continue

        mains_norm = normalize_with_cap(mains_seg, cap_m)

        ch0 = mains_norm
        ch1 = compute_autocorr(mains_norm)
        ch2 = compute_crosscorr(mains_norm, crosscorr_profile)

        mid_idx  = i_start + L // 2
        mid_idx  = min(mid_idx, len(times) - 1)
        mid_time = times[mid_idx]
        hour     = mid_time.hour + mid_time.minute / 60.0
        sin_h    = float(np.sin(2 * np.pi * hour / 24.0))
        cos_h    = float(np.cos(2 * np.pi * hour / 24.0))
        ch3 = np.full(L, sin_h, dtype=np.float32)
        ch4 = np.full(L, cos_h, dtype=np.float32)

        ch5 = compute_delta(mains_norm)
        ch6 = compute_delta2(mains_norm)

        agg_7ch = np.stack([ch0, ch1, ch2, ch3, ch4, ch5, ch6], axis=-1)  # (L, 7)

        patterns.append({
            'agg_7ch'     : agg_7ch,
            'length'      : L,
            'duration_min': duration,       # real ON duration (no lead/trail)
            'i_start'     : i_start,        # kept for kWh integration
            'i_end'       : i_end,
            'mains_norm'  : mains_norm,     # kept for kWh integration
            'cap_m'       : cap_m,
        })

    return patterns


def pad_patterns_infer(patterns: list, max_len: int) -> tuple:
    """Pad to max_len — same logic as preprocessing pad_patterns()."""
    N    = len(patterns)
    X    = np.zeros((N, max_len, N_CHANNELS), dtype=np.float32)
    mask = np.zeros((N, max_len),             dtype=np.float32)

    for i, pat in enumerate(patterns):
        L           = min(pat['length'], max_len)
        X[i, :L, :] = pat['agg_7ch'][:L]
        mask[i, :L] = 1.0

    return X, mask


# ─────────────────────────────────────────────────────────────────────────────
# 5. BiLSTM Model — identical to pipeline notebook
# ─────────────────────────────────────────────────────────────────────────────

class BiLSTM_S2S(nn.Module):
    def __init__(self, n_channels=7, hidden1=128, hidden2=64, dropout=0.3):
        super().__init__()
        self.lstm1 = nn.LSTM(n_channels, hidden1, 1,
                             batch_first=True, bidirectional=True)
        self.drop1 = nn.Dropout(dropout)
        self.lstm2 = nn.LSTM(hidden1 * 2, hidden2, 1,
                             batch_first=True, bidirectional=True)
        self.drop2 = nn.Dropout(dropout)
        self.head  = nn.Sequential(
            nn.Linear(hidden2 * 2, 64),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(64, 1),
            nn.Sigmoid(),
        )

    def forward(self, x):
        out, _ = self.lstm1(x)
        out    = self.drop1(out)
        out, _ = self.lstm2(out)
        out    = self.drop2(out)
        return self.head(out).squeeze(-1)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Load Models
# ─────────────────────────────────────────────────────────────────────────────

def load_all_models(checkpoint_dir: str, device: torch.device):
    models = {}
    metas  = {}

    meta_files = sorted(f for f in os.listdir(checkpoint_dir)
                        if f.endswith('_meta.json'))
    if not meta_files:
        raise FileNotFoundError(
            f'No *_meta.json files found in {checkpoint_dir}/\n'
            'Run the "Save Model Metadata" cell in the pipeline notebook first.'
        )

    for mf in meta_files:
        with open(os.path.join(checkpoint_dir, mf)) as f:
            meta = json.load(f)

        app  = meta['appliance']
        ckpt = meta['checkpoint']

        if not os.path.exists(ckpt):
            print(f'  [SKIP] Checkpoint missing: {ckpt}')
            continue

        model = BiLSTM_S2S(
            n_channels=meta['n_channels'],
            hidden1   =meta['hidden1'],
            hidden2   =meta['hidden2'],
            dropout   =meta['dropout'],
        ).to(device)
        model.load_state_dict(torch.load(ckpt, map_location=device))
        model.eval()

        models[app] = model
        metas[app]  = meta

    return models, metas


# ─────────────────────────────────────────────────────────────────────────────
# 7. Inference — predict appliance power for every candidate event
# ─────────────────────────────────────────────────────────────────────────────

@torch.no_grad()
def infer_events(
    model: nn.Module,
    X: np.ndarray,          # (N, max_len, 7)
    device: torch.device,
    batch_size: int = 64,
) -> np.ndarray:
    """Returns predicted normalised power (N, max_len)."""
    preds = []
    for i in range(0, len(X), batch_size):
        batch = torch.from_numpy(X[i:i + batch_size]).to(device)
        preds.append(model(batch).cpu().numpy())
    return np.concatenate(preds, axis=0)


def compute_monthly_kwh(
    patterns: list,
    preds_norm: np.ndarray,   # (N, max_len)  — normalised
    mask: np.ndarray,         # (N, max_len)
    opt_thr: float,           # optimal threshold in normalised space
    norm_cap: float,          # appliance normalisation cap (Watts)
) -> float:
    """
    Convert sequence predictions to kWh.

    For each event window:
      - Apply threshold: timesteps below opt_thr → 0 W
      - Multiply normalised prediction by norm_cap → Watts
      - Only count real (non-padded) timesteps via mask
      - 1 timestep = 1 minute → divide Watt-minutes by 60,000 to get kWh
    """
    total_watt_minutes = 0.0

    for i, pat in enumerate(patterns):
        L = min(pat['length'], preds_norm.shape[1])

        pred_slice = preds_norm[i, :L]   # normalised [0,1]
        mask_slice = mask[i, :L]         # 1 = real, 0 = padding

        # Apply ON/OFF threshold
        pred_on = np.where(pred_slice > opt_thr, pred_slice, 0.0)

        # Convert to Watts and accumulate (mask ensures no padding leaks in)
        total_watt_minutes += float((pred_on * mask_slice).sum()) * norm_cap

    return total_watt_minutes / 60_000.0   # Watt-minutes → kWh


# ─────────────────────────────────────────────────────────────────────────────
# 8. Load & validate the user's CSV
# ─────────────────────────────────────────────────────────────────────────────

def load_aggregate_csv(csv_path: str) -> pd.DataFrame:
    """
    Load monthly aggregate CSV.  Accepts:
      - First column = Unix timestamp (seconds) or any parseable datetime string
      - Column named 'WHE' or 'Whole-House Meter' for aggregate power in Watts
    """
    df = pd.read_csv(csv_path)

    # ── Timestamp ──────────────────────────────────────────────────────────
    time_col = df.columns[0]
    try:
        df[time_col] = pd.to_datetime(df[time_col], unit='s', errors='raise')
    except Exception:
        df[time_col] = pd.to_datetime(df[time_col], errors='coerce')

    df = df.set_index(time_col).sort_index()
    df.index.name = 'time'

    # ── Rename WHE if needed ───────────────────────────────────────────────
    if 'WHE' in df.columns and MAINS_COL not in df.columns:
        df = df.rename(columns={'WHE': MAINS_COL})

    if MAINS_COL not in df.columns:
        raise ValueError(
            f"CSV must contain a column named 'WHE' or '{MAINS_COL}'.\n"
            f"Found columns: {list(df.columns)}"
        )

    df[MAINS_COL] = df[MAINS_COL].clip(lower=0)

    n_days = (df.index[-1] - df.index[0]).days + 1
    print(f'  Loaded {len(df):,} rows  |  '
          f'{df.index[0].date()} → {df.index[-1].date()}  ({n_days} days)')

    return df


# ─────────────────────────────────────────────────────────────────────────────
# 9. Print the Bill
# ─────────────────────────────────────────────────────────────────────────────

def print_bill(
    app_kwh: dict,
    account_name: str,
    balance_jd: float,
    period_str: str,
):
    total_kwh    = sum(app_kwh.values())
    total_bill   = calc_nepco_bill(total_kwh)
    amount_due   = round(total_bill + balance_jd, 3)
    sorted_apps  = sorted(app_kwh.items(), key=lambda x: x[1], reverse=True)
    app_cost     = {app: attribute_appliance_cost(kwh, total_kwh)
                    for app, kwh in app_kwh.items()}

    W   = 62
    SEP = '─' * W

    def box_top():    print('┌' + SEP + '┐')
    def box_bot():    print('└' + SEP + '┘')
    def box_mid():    print('├' + SEP + '┤')
    def box_line(s):  print('│ ' + s.ljust(W - 1) + '│')
    def centre(s):    print('│' + s.center(W) + '│')
    def blank():      print('│' + ' ' * W + '│')

    now = datetime.now().strftime('%d %b %Y  %H:%M')

    box_top()
    centre('  ⚡  NILM ELECTRICITY BILL  ⚡')
    centre('Jordan — NEPCO Residential Tariff')
    blank()
    centre(f'Account : {account_name}')
    centre(f'Period  : {period_str}')
    centre(f'Issued  : {now}')

    # ── Appliance breakdown ────────────────────────────────────────────────
    box_mid()
    centre('TOP APPLIANCES BY CONSUMPTION')
    box_mid()
    box_line(f"  {'#':<3} {'Appliance':<22} {'kWh':>7}  {'Cost':>9}  {'Share':>7}")
    box_line('  ' + '─' * 56)

    for rank, (app, kwh) in enumerate(sorted_apps, 1):
        cost  = app_cost[app]
        share = (kwh / total_kwh * 100) if total_kwh > 0 else 0
        n_blocks = int(share / 4)          # 1 block per 4%
        bar  = '▓' * n_blocks + '░' * (25 - n_blocks)
        box_line(f"  {rank:<3} {app:<22} {kwh:>7.2f}  {cost:>7.3f} JD  {share:>5.1f}%")
        box_line(f"  {'':3} {'':22} {bar}")

    # ── Consumption summary ────────────────────────────────────────────────
    box_mid()
    centre('CONSUMPTION SUMMARY')
    box_mid()

    prev = 0.0
    for ceiling, rate in NEPCO_TIERS:
        if total_kwh <= prev:
            break
        chunk = min(total_kwh, ceiling) - prev
        band  = f'{int(prev)+1}–{int(ceiling) if ceiling != float("inf") else "∞"}'
        box_line(f"  Tier {band:>10} kWh  @{rate*1000:>3.0f} fils/kWh"
                 f"  {chunk:>7.1f} kWh = {chunk * rate:>7.3f} JD")
        prev = ceiling

    blank()
    box_line(f"  Total Consumption          {total_kwh:>10.3f} kWh")
    box_line(f"  Fixed Monthly Charge       {FIXED_CHARGE_JD:>10.3f} JD")

    # ── Bill total ─────────────────────────────────────────────────────────
    box_mid()
    box_line(f"  Current Month Bill         {total_bill:>10.3f} JD")

    if balance_jd != 0:
        label = 'Previous Balance (owed)' if balance_jd > 0 else 'Previous Credit'
        box_line(f"  {label:<27} {abs(balance_jd):>10.3f} JD")

    box_mid()
    box_line(f"  {'TOTAL AMOUNT DUE':<27} {amount_due:>10.3f} JD")
    box_bot()

    print()
    print('Notes:')
    print('  • Consumption estimated via NILM model from aggregate meter data.')
    print('  • Each timestep = 1 minute. Unmonitored appliances not shown.')
    print('  • NEPCO tiers applied cumulatively on total monthly kWh.')
    print('  • Appliance cost = proportional share of variable tariff charge.')


# ─────────────────────────────────────────────────────────────────────────────
# 10. Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='NILM Monthly Bill Generator')
    parser.add_argument('--csv',      required=True,
                        help='Path to monthly aggregate CSV file')
    parser.add_argument('--account',  default='Household',
                        help='Account holder name (default: Household)')
    parser.add_argument('--balance',  type=float, default=0.0,
                        help='Previous month balance in JD (positive = owed, '
                             'negative = credit). Default: 0.0')
    parser.add_argument('--checkpoints', default='checkpoints',
                        help='Checkpoint directory (default: checkpoints/)')
    parser.add_argument('--nilm-dir',    default='nilm_datasets',
                        help='NILM datasets directory (default: nilm_datasets/)')
    args = parser.parse_args()

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    # ── Load CSV ─────────────────────────────────────────────────────────────
    print('\n[1/4] Loading aggregate data...')
    df = load_aggregate_csv(args.csv)
    period_str = (f"{df.index[0].strftime('%d %b %Y')} – "
                  f"{df.index[-1].strftime('%d %b %Y')}")

    # Load norm caps (needed for feature engineering)
    norm_caps_df = pd.read_csv(os.path.join(args.nilm_dir, 'norm_caps.csv'))
    norm_caps    = norm_caps_df.iloc[0].to_dict()

    # ── Load models ───────────────────────────────────────────────────────────
    print('\n[2/4] Loading appliance models...')
    models, metas = load_all_models(args.checkpoints, device)
    print(f'      {len(models)} appliance models loaded.')

    # ── Extract events & run inference ────────────────────────────────────────
    print('\n[3/4] Extracting events and running inference...\n')
    app_kwh = {}

    for app, model in models.items():
        meta    = metas[app]
        cfg     = CONTEXT_CONFIG.get(app, {'lead': 10, 'trail': 10})
        min_dur = MIN_EVENT_DURATION.get(app, 2)
        max_len = meta['max_len']
        opt_thr = meta['opt_thr']      # optimal normalised threshold from val set
        cap_a   = meta['norm_cap']

        # Load the saved cross-correlation profile for this appliance
        safe         = app.replace(' ', '_').replace('/', '-')
        profile_path = os.path.join(args.nilm_dir, f'{safe}_crosscorr_profile.npy')
        if os.path.exists(profile_path):
            profile = np.load(profile_path)
        else:
            print(f'  [WARN] No cross-correlation profile for {app} — using zeros')
            profile = np.zeros(cfg['lead'] + 10 + cfg['trail'], dtype=np.float32)

        # Extract candidate event windows from the aggregate
        patterns = extract_aggregate_events(
            df          = df,
            appliance   = app,
            norm_caps   = norm_caps,
            crosscorr_profile = profile,
            lead        = cfg['lead'],
            trail       = cfg['trail'],
            min_duration_min = min_dur,
        )

        if len(patterns) == 0:
            print(f'  {app:<22}  0 events detected  →  0.000 kWh')
            app_kwh[app] = 0.0
            continue

        # Pad to max_len
        X, mask = pad_patterns_infer(patterns, max_len)

        # Run model
        preds_norm = infer_events(model, X, device)

        # Integrate to kWh
        kwh = compute_monthly_kwh(
            patterns   = patterns,
            preds_norm = preds_norm,
            mask       = mask,
            opt_thr    = opt_thr,
            norm_cap   = cap_a,
        )
        app_kwh[app] = kwh
        print(f'  {app:<22}  {len(patterns):>4} events  →  {kwh:>8.3f} kWh')

    # ── Print bill ────────────────────────────────────────────────────────────
    print('\n[4/4] Generating bill...\n')
    print_bill(
        app_kwh      = app_kwh,
        account_name = args.account,
        balance_jd   = args.balance,
        period_str   = period_str,
    )


if __name__ == '__main__':
    main()






# ============================================================
# CELL B — NILM Bill Generator
# Add this as a new cell AFTER Cell A (or in a separate
# notebook / script).  Reads the saved checkpoints and
# runs inference on the preprocessed test split.
# ============================================================

import os, json, math
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from datetime import datetime


# ── 1. NEPCO Residential Tiered Tariff (JD / kWh) ───────────────────────────
# Source: NEPCO residential tariff schedule
# Tiers are CUMULATIVE monthly kWh.  The marginal rate applies to each tier.
NEPCO_TIERS = [
    (160,  0.033),   # 0–160 kWh  → 33 fils/kWh
    (300,  0.078),   # 161–300    → 78 fils/kWh
    (500,  0.113),   # 301–500    → 113 fils/kWh
    (600,  0.156),   # 501–600    → 156 fils/kWh
    (750,  0.188),   # 601–750    → 188 fils/kWh
    (1000, 0.220),   # 751–1000   → 220 fils/kWh
    (float('inf'), 0.288),  # >1000 → 288 fils/kWh
]
FIXED_CHARGE_JD = 0.70   # fixed monthly service charge


def calc_nepco_bill(total_kwh: float) -> float:
    """Return total bill in JD for a given monthly consumption."""
    charge = FIXED_CHARGE_JD
    prev   = 0.0
    for ceiling, rate in NEPCO_TIERS:
        if total_kwh <= prev:
            break
        chunk   = min(total_kwh, ceiling) - prev
        charge += chunk * rate
        prev    = ceiling
    return round(charge, 3)


def kwh_cost_for_appliance(app_kwh: float, total_kwh: float) -> float:
    """
    Attribute a proportional share of the tiered bill to one appliance.
    Uses marginal-rate attribution: the appliance's share of total kWh
    times the *marginal* bill contribution of those kWh.
    """
    if total_kwh <= 0:
        return 0.0
    fraction = app_kwh / total_kwh
    total_bill_jd = calc_nepco_bill(total_kwh)
    # Subtract the fixed charge before splitting
    variable_bill = max(total_bill_jd - FIXED_CHARGE_JD, 0.0)
    return round(fraction * variable_bill, 3)


# ── 2. Model definition (copy from pipeline notebook) ───────────────────────

class BiLSTM_S2S(nn.Module):
    def __init__(self, n_channels=7, hidden1=128, hidden2=64, dropout=0.3):
        super().__init__()
        self.lstm1 = nn.LSTM(n_channels, hidden1, 1,
                             batch_first=True, bidirectional=True)
        self.drop1 = nn.Dropout(dropout)
        self.lstm2 = nn.LSTM(hidden1 * 2, hidden2, 1,
                             batch_first=True, bidirectional=True)
        self.drop2 = nn.Dropout(dropout)
        self.head  = nn.Sequential(
            nn.Linear(hidden2 * 2, 64),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(64, 1),
            nn.Sigmoid(),
        )

    def forward(self, x):
        out, _ = self.lstm1(x)
        out    = self.drop1(out)
        out, _ = self.lstm2(out)
        out    = self.drop2(out)
        return self.head(out).squeeze(-1)


# ── 3. Load all saved models ─────────────────────────────────────────────────

CHECKPOINT_DIR = 'checkpoints'
NILM_DIR       = 'nilm_datasets'
DEVICE         = torch.device('cuda' if torch.cuda.is_available() else 'cpu')


def load_all_models(checkpoint_dir=CHECKPOINT_DIR):
    """Load every appliance model found in checkpoint_dir."""
    models = {}
    metas  = {}

    meta_files = [f for f in os.listdir(checkpoint_dir) if f.endswith('_meta.json')]
    if not meta_files:
        raise FileNotFoundError(
            f'No *_meta.json files found in {checkpoint_dir}. '
            'Run Cell A first to save model metadata.'
        )

    for mf in meta_files:
        with open(os.path.join(checkpoint_dir, mf)) as f:
            meta = json.load(f)

        app  = meta['appliance']
        ckpt = meta['checkpoint']

        if not os.path.exists(ckpt):
            print(f'  [WARNING] Checkpoint missing for {app}: {ckpt}')
            continue

        model = BiLSTM_S2S(
            n_channels = meta['n_channels'],
            hidden1    = meta['hidden1'],
            hidden2    = meta['hidden2'],
            dropout    = meta['dropout'],
        ).to(DEVICE)
        model.load_state_dict(torch.load(ckpt, map_location=DEVICE))
        model.eval()

        models[app] = model
        metas[app]  = meta
        print(f'  Loaded: {app}  (F1={meta["metrics"].get("F1", "?"):.3f}  '
              f'checkpoint={os.path.basename(ckpt)})')

    return models, metas


print('Loading appliance models...')
MODELS, METAS = load_all_models()
print(f'\n{len(MODELS)} models ready.\n')


# ── 4. Run inference on preprocessed test split ──────────────────────────────
# The test split X_test.npy contains the 7-channel aggregate event patterns
# that were built during preprocessing — only the aggregate signal (no appliance
# labels) is used as input to each model.

def infer_appliance(model, meta, X_test: np.ndarray) -> np.ndarray:
    """
    Run the model on X_test (N, max_len, 7).
    Returns predicted power in WATTS (N, max_len).
    """
    model.eval()
    all_preds = []
    batch_size = 64

    with torch.no_grad():
        for i in range(0, len(X_test), batch_size):
            batch = torch.from_numpy(X_test[i:i + batch_size]).to(DEVICE)
            pred  = model(batch).cpu().numpy()   # (B, max_len) normalised [0,1]
            all_preds.append(pred)

    preds_norm = np.concatenate(all_preds, axis=0)     # (N, max_len)
    preds_w    = preds_norm * meta['norm_cap']          # → Watts
    return preds_w


def compute_kwh_from_predictions(
    preds_w: np.ndarray,
    mask: np.ndarray,
    opt_thr_norm: float,
    norm_cap: float,
    minutes_per_step: float = 1.0,
) -> float:
    """
    Sum watts over real (non-padded) timesteps, apply ON/OFF threshold,
    convert to kWh.  Each timestep = 1 minute by default (AMPds is 1-min).
    """
    thr_w = opt_thr_norm * norm_cap
    # Zero out timesteps the model predicts as OFF
    preds_on = np.where(preds_w > thr_w, preds_w, 0.0)
    # Only real (non-padded) positions count
    real_w  = preds_on * mask                           # (N, max_len)
    total_w_minutes = float(real_w.sum())               # Watt-minutes
    kwh = total_w_minutes / 60_000.0                    # Wh → kWh
    return kwh


# Run inference for every appliance
print('Running inference on test split...\n')
app_kwh = {}

for app, model in MODELS.items():
    meta  = METAS[app]
    safe  = app.replace(' ', '_').replace('/', '-')
    app_dir = os.path.join(NILM_DIR, safe)

    x_path = os.path.join(app_dir, 'X_test.npy')
    m_path = os.path.join(app_dir, 'mask_test.npy')

    if not os.path.exists(x_path):
        print(f'  [SKIP] No test data for {app}')
        continue

    X_test   = np.load(x_path)    # (N, max_len, 7) — aggregate only
    mask_test = np.load(m_path)   # (N, max_len)

    preds_w = infer_appliance(model, meta, X_test)

    kwh = compute_kwh_from_predictions(
        preds_w,
        mask_test,
        opt_thr_norm = meta['opt_thr'],
        norm_cap     = meta['norm_cap'],
    )
    app_kwh[app] = kwh
    print(f'  {app:<22}  {kwh:>8.3f} kWh  ({len(X_test)} test events)')


# ── 5. Build and print the electricity bill ──────────────────────────────────

total_kwh  = sum(app_kwh.values())
total_bill = calc_nepco_bill(total_kwh)
sorted_apps = sorted(app_kwh.items(), key=lambda x: x[1], reverse=True)

# JD cost attributed to each appliance
app_cost = {
    app: kwh_cost_for_appliance(kwh, total_kwh)
    for app, kwh in app_kwh.items()
}

# ── Visual bill ──────────────────────────────────────────────────────────────
WIDTH = 60
LINE  = '─' * WIDTH

def centre(text): return text.center(WIDTH)
def row(label, val): return f"  {label:<30}{val:>26}"

now = datetime.now().strftime('%d %b %Y  %H:%M')

print()
print('┌' + '─' * WIDTH + '┐')
print('│' + centre('  NILM ELECTRICITY BILL  ')        + '│')
print('│' + centre('Jordan — NEPCO Residential Tariff') + '│')
print('│' + centre(f'Generated: {now}')                + '│')
print('├' + LINE                                        + '┤')
print('│' + centre('APPLIANCE BREAKDOWN (highest to lowest)')  + '│')
print('├' + LINE                                        + '┤')
print('│' + f"  {'#':<4}{'Appliance':<22}{'kWh':>8}{'Cost (JD)':>12}{'Share':>10}"  + '  │')
print('│' + '  ' + '─' * 56 + '  │')

for rank, (app, kwh) in enumerate(sorted_apps, 1):
    cost  = app_cost[app]
    share = (kwh / total_kwh * 100) if total_kwh > 0 else 0
    bar   = '█' * int(share / 5)   # 1 block per 5%
    print(f'│  {rank:<4}{app:<22}{kwh:>8.2f}{cost:>11.3f} JD'
          f'{share:>8.1f}%  │')
    print(f'│  {"":4}{"":22}  {bar:<44}  │')

print('├' + LINE + '┤')
print('│' + row('Total Consumption:', f'{total_kwh:.3f} kWh')          + '  │')
print('│' + row('Fixed Monthly Charge:', f'{FIXED_CHARGE_JD:.3f} JD')  + '  │')

# Show tiered breakdown
prev = 0
for ceiling, rate in NEPCO_TIERS:
    if total_kwh <= prev:
        break
    chunk = min(total_kwh, ceiling) - prev
    band  = f'{int(prev)+1}–{int(ceiling)} kWh  @{rate*1000:.0f} fils'
    print('│' + row(f'  Tier ({band}):', f'{chunk * rate:.3f} JD') + '  │')
    prev = ceiling

print('├' + LINE + '┤')
print('│' + row('TOTAL BILL:', f'{total_bill:.3f} JD')               + '  │')
print('└' + '─' * WIDTH + '┘')

print()
print('Notes:')
print('  • Consumption estimated from NILM model predictions on test data.')
print('  • Each timestep = 1 minute (AMPds 1-minute resolution).')
print('  • NEPCO tiered tariff applied cumulatively per month.')
print('  • Cost per appliance = proportional share of variable bill charge.')
print('  • Unmonitored load (background) is not included above.')
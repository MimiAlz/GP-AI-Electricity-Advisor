"""
prepare_test_data.py
====================
Prepares the test data from Electricity_P.csv exactly the way the
preprocessing notebook did, and packages it ready to send to the backend.

HOW IT WORKS
------------
The preprocessing notebook split the data chronologically:
    Train : first 80%
    Val   : 80% → 85%
    Test  : last 15%   ← this is what we use here

For each appliance it then:
1. Detected ON/OFF transitions in the appliance column
2. Extracted each ON event with lead/trail context from the AGGREGATE only
3. Built the 7-channel tensor
4. Padded to MAX_LEN

This script does the same thing for the TEST split only, and produces
a list of event dicts ready to send to the backend one by one.

HOW TO USE
----------
    from prepare_test_data import load_test_events

    events = load_test_events(
        csv_path      = 'Electricity_P.csv',
        nilm_dir      = 'nilm_datasets',
    )

    # events is a dict: { appliance_name: [ {X, mask, ground_truth_watts}, ... ] }
    # Send each event to the backend individually.
"""

import os
import numpy as np
import pandas as pd


# ── Constants (must match preprocessing notebook exactly) ─────────────────────

MAINS_COL = 'Whole-House Meter'

APPLIANCE_NAMES = {
    'CDE': 'Clothes Dryer',
    'CWE': 'Clothes Washer',
    'DWE': 'Dishwasher',
    'FGE': 'Kitchen Fridge',
    'HPE': 'Heat Pump',
    'TVE': 'TV',
    'WHE': 'Whole-House Meter',
}

TARGET_APPLIANCES = [
    'Clothes Dryer',
    'Clothes Washer',
    'Dishwasher',
    'Kitchen Fridge',
    'Heat Pump',
    'TV',
]

WATTS_ON_THRESHOLD = 50.0

CONTEXT_CONFIG = {
    'Clothes Dryer' : {'lead': 30, 'trail': 30},
    'Clothes Washer': {'lead': 5,  'trail': 15},
    'Dishwasher'    : {'lead': 30, 'trail': 30},
    'Heat Pump'     : {'lead': 60, 'trail': 60},
    'Kitchen Fridge': {'lead': 10, 'trail': 10},
    'TV'            : {'lead': 2,  'trail': 2},
}

MIN_EVENT_DURATION = {
    'Clothes Dryer' : 10,
    'Clothes Washer': 10,
    'Dishwasher'    : 10,
    'Heat Pump'     : 5,
    'Kitchen Fridge': 2,
    'TV'            : 1,
}

DROP_COLS = [
    'MHE', 'RSE', 'GRE', 'B1E', 'BME', 'EQE', 'OFE', 'UTE',
    'B2E', 'DNE', 'EBE', 'OUE', 'UNE', 'HTE', 'WOE', 'FRE',
]


# ── Feature engineering (same as preprocessing notebook) ─────────────────────

def normalize_with_cap(arr: np.ndarray, cap: float) -> np.ndarray:
    arr = np.clip(arr, 0, None).astype(np.float32)
    if cap <= 0:
        return arr
    return np.clip(arr / cap, 0.0, 1.0).astype(np.float32)


def compute_autocorr(window: np.ndarray) -> np.ndarray:
    n   = len(window)
    w   = window - window.mean()
    var = np.var(w) + 1e-8
    result    = np.zeros(n, dtype=np.float32)
    result[0] = 1.0
    for lag in range(1, n):
        result[lag] = float(np.mean(w[:n - lag] * w[lag:]) / var)
    return np.clip(result, -1.0, 1.0)


def compute_crosscorr(window: np.ndarray, profile: np.ndarray) -> np.ndarray:
    n = min(len(window), len(profile))
    if n == 0:
        return np.zeros(len(window), dtype=np.float32)
    w = window[:n] - window[:n].mean()
    p = profile[:n] - profile[:n].mean()
    denom = float(np.std(w) * np.std(p)) + 1e-8
    corr  = float(np.clip(np.mean(w * p) / denom, -1.0, 1.0))
    return np.full(len(window), corr, dtype=np.float32)


def compute_delta(window: np.ndarray) -> np.ndarray:
    delta = np.diff(window.astype(np.float32), prepend=window[0])
    return np.clip(delta, -1.0, 1.0).astype(np.float32)


def compute_delta2(window: np.ndarray) -> np.ndarray:
    d1 = np.diff(window.astype(np.float32), prepend=window[0])
    d2 = np.diff(d1, prepend=d1[0])
    return np.clip(d2, -1.0, 1.0).astype(np.float32)


# ── Data loading (same as preprocessing notebook) ────────────────────────────

def load_and_clean_ampds(csv_path: str) -> pd.DataFrame:
    """
    Load Electricity_P.csv and apply the same cleaning as the
    preprocessing notebook:
      - Drop unused columns
      - Rename to human-readable names
      - Parse timestamps
      - Clip negatives
      - Apply 50W hard threshold per appliance
    """
    ampd = pd.read_csv(csv_path)
    ampd = ampd.drop(columns=[c for c in DROP_COLS if c in ampd.columns])
    ampd = ampd.rename(columns=APPLIANCE_NAMES)
    ampd = ampd.rename(columns={ampd.columns[0]: 'time'})
    ampd['time'] = pd.to_datetime(ampd['time'], unit='s', errors='coerce')
    ampd = ampd.set_index('time').sort_index()

    # Clip negatives
    for col in ampd.columns:
        ampd[col] = ampd[col].clip(lower=0)

    # Apply 50W hard threshold to appliances only
    for app in TARGET_APPLIANCES:
        if app in ampd.columns:
            ampd[app] = ampd[app].where(ampd[app] >= WATTS_ON_THRESHOLD, other=0.0)

    return ampd


# ── Event extraction (same logic as preprocessing notebook) ──────────────────

def extract_test_events(df_test: pd.DataFrame,
                        appliance: str,
                        norm_caps: dict,
                        crosscorr_profile: np.ndarray,
                        max_len: int) -> list:
    """
    Extract all ON events from the test split for one appliance.

    Returns a list of dicts, each representing one event:
        'X'                : np.ndarray (1, max_len, 7)  — model input
        'mask'             : np.ndarray (1, max_len)     — 1=real, 0=padding
        'ground_truth_norm': np.ndarray (real_len,)      — normalised target
        'ground_truth_w'   : np.ndarray (real_len,)      — Watts target
        'real_len'         : int
        'appliance'        : str
    """
    if appliance not in df_test.columns:
        return []

    c         = CONTEXT_CONFIG[appliance]
    lead      = c['lead']
    trail     = c['trail']
    min_dur   = MIN_EVENT_DURATION.get(appliance, 2)

    app_arr   = df_test[appliance].values.astype(np.float64)
    mains_arr = df_test[MAINS_COL].values.astype(np.float64)
    times     = df_test.index
    n         = len(df_test)

    cap_m = norm_caps[MAINS_COL]
    cap_a = norm_caps[appliance]

    # Find ON/OFF transitions
    is_on  = (app_arr > 0).astype(int)
    diff   = np.diff(is_on, prepend=0)
    starts = list(np.where(diff == 1)[0])
    ends   = list(np.where(diff == -1)[0])

    if len(starts) > len(ends):
        ends.append(n - 1)

    events = []

    for s, e in zip(starts, ends):
        duration_min = e - s
        if duration_min < min_dur:
            continue

        i_start = max(0, s - lead)
        i_end   = min(n, e + trail)

        mains_seg = mains_arr[i_start:i_end]
        app_seg   = app_arr[i_start:i_end]
        L         = len(mains_seg)

        if L == 0:
            continue

        # ── Build 7 channels (identical to preprocessing notebook) ────────
        mains_norm = normalize_with_cap(mains_seg, cap_m)
        app_norm   = normalize_with_cap(app_seg,   cap_a)

        ch0 = mains_norm
        ch1 = compute_autocorr(mains_norm)
        ch2 = compute_crosscorr(mains_norm, crosscorr_profile)

        mid_idx  = i_start + L // 2
        mid_idx  = min(mid_idx, len(times) - 1)
        mid_time = times[mid_idx]
        hour     = mid_time.hour + mid_time.minute / 60.0
        sin_h    = float(np.sin(2 * np.pi * hour / 24.0))
        cos_h    = float(np.cos(2 * np.pi * hour / 24.0))
        ch3      = np.full(L, sin_h, dtype=np.float32)
        ch4      = np.full(L, cos_h, dtype=np.float32)
        ch5      = compute_delta(mains_norm)
        ch6      = compute_delta2(mains_norm)

        agg_7ch = np.stack([ch0, ch1, ch2, ch3, ch4, ch5, ch6], axis=-1)  # (L, 7)

        # ── Pad to MAX_LEN ────────────────────────────────────────────────
        real_len = min(L, max_len)
        X        = np.zeros((1, max_len, 7), dtype=np.float32)
        mask     = np.zeros((1, max_len),    dtype=np.float32)
        X[0, :real_len, :]  = agg_7ch[:real_len]
        mask[0, :real_len]  = 1.0

        events.append({
            'X'                : X,                          # (1, max_len, 7) — send this to backend
            'mask'             : mask,                       # (1, max_len)
            'ground_truth_norm': app_norm[:real_len],        # normalised — for evaluation
            'ground_truth_w'   : app_seg[:real_len] ,        # raw Watts  — for evaluation
            'real_len'         : real_len,
            'appliance'        : appliance,
        })

    return events


# ── Main function ─────────────────────────────────────────────────────────────

def load_test_events(
    csv_path: str = 'Electricity_P.csv',
    nilm_dir: str = 'nilm_datasets',
) -> dict:
    """
    Load Electricity_P.csv, take the test split (last 15%),
    and extract all events per appliance.

    Returns
    -------
    dict : { appliance_name: [ event_dict, ... ] }

    Each event_dict has:
        'X'              : (1, max_len, 7)  ← this is what you send to the backend
        'mask'           : (1, max_len)
        'ground_truth_w' : (real_len,)      ← Watts, for evaluation only
        'real_len'       : int
        'appliance'      : str
    """

    # ── 1. Load norm_caps ────────────────────────────────────────────────────
    norm_caps_path = os.path.join(nilm_dir, 'norm_caps.csv')
    norm_caps = pd.read_csv(norm_caps_path).iloc[0].to_dict()
    print(f'Loaded norm_caps: {len(norm_caps)} entries')

    # ── 2. Load max_lens ─────────────────────────────────────────────────────
    max_lens_path = os.path.join(nilm_dir, 'max_lens.csv')
    max_lens = {k: int(v) for k, v in pd.read_csv(max_lens_path).iloc[0].to_dict().items()}
    print(f'Loaded max_lens: {max_lens}')

    # ── 3. Load crosscorr profiles ───────────────────────────────────────────
    profiles = {}
    for app in TARGET_APPLIANCES:
        safe = app.replace(' ', '_').replace('/', '-')
        path = os.path.join(nilm_dir, f'{safe}_crosscorr_profile.npy')
        if os.path.exists(path):
            profiles[app] = np.load(path)
    print(f'Loaded {len(profiles)} crosscorr profiles')

    # ── 4. Load and clean AMPds CSV ──────────────────────────────────────────
    print(f'\nLoading {csv_path}...')
    ampd = load_and_clean_ampds(csv_path)
    print(f'Total rows: {len(ampd):,}')

    # ── 5. Chronological split — take test portion (last 15%) ────────────────
    n        = len(ampd)
    val_end  = int(n * 0.85)
    df_test  = ampd.iloc[val_end:].copy()
    print(f'Test split : {len(df_test):,} rows  '
          f'({df_test.index[0].date()} → {df_test.index[-1].date()})')

    # ── 6. Extract events per appliance ──────────────────────────────────────
    all_events = {}

    for app in TARGET_APPLIANCES:
        if app not in profiles or app not in max_lens:
            print(f'  Skipping {app} — missing profile or max_len')
            continue

        events = extract_test_events(
            df_test           = df_test,
            appliance         = app,
            norm_caps         = norm_caps,
            crosscorr_profile = profiles[app],
            max_len           = max_lens[app],
        )
        all_events[app] = events
        print(f'  {app:<22}: {len(events):>4} test events  '
              f'(max_len={max_lens[app]})')

    total = sum(len(v) for v in all_events.values())
    print(f'\nTotal test events across all appliances: {total}')
    return all_events


# ── Example: how to use this with the backend ─────────────────────────────────

if __name__ == '__main__':
    import sys
    sys.path.insert(0, '.')
    from nilm_inference import NILMBackend
    import torch

    # ── Step 1: prepare test data ─────────────────────────────────────────────
    test_events = load_test_events(
        csv_path = 'Electricity_P.csv',
        nilm_dir = 'nilm_datasets',
    )

    # ── Step 2: load backend ──────────────────────────────────────────────────
    backend = NILMBackend.from_checkpoints(
        checkpoint_dir = 'checkpoints',
        nilm_dir       = 'nilm_datasets',
    )

    # ── Step 3: run inference event by event ──────────────────────────────────
    print('\n--- Running inference on test events ---\n')

    for app, events in test_events.items():
        if not events:
            continue

        print(f'{app} ({len(events)} events):')
        model  = backend.models[app]
        meta   = backend.metas[app]
        device = backend.device

        mae_list = []

        for ev in events:
            X        = ev['X']        # (1, max_len, 7) — the model input
            mask     = ev['mask']     # (1, max_len)
            gt_w     = ev['ground_truth_w']   # Watts, for evaluation
            real_len = ev['real_len']

            # Run model
            with torch.no_grad():
                x_tensor  = torch.from_numpy(X).to(device)
                pred_norm = model(x_tensor).cpu().numpy()   # (1, max_len)

            # Trim and denormalise
            pred_w = pred_norm[0, :real_len] * meta['norm_cap']  # Watts

            # Evaluate
            mae = float(np.mean(np.abs(pred_w - gt_w[:real_len])))
            mae_list.append(mae)

        print(f'  Mean MAE across {len(mae_list)} events: {np.mean(mae_list):.2f} W\n')

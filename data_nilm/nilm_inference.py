"""
nilm_inference.py
=================
Drop-in backend connector for the NILM BiLSTM Seq-to-Seq pipeline.

HOW TO USE
----------
1.  Copy this file to the same directory as your checkpoints/ folder.
2.  After training, make sure you have run the metadata-saving cell in
    NILM_Pipeline_v4.ipynb (the one that writes best_*_v4_meta.json).
3.  Make sure nilm_datasets/ exists with norm_caps.csv, max_lens.csv,
    and the per-appliance *_crosscorr_profile.npy files.
4.  Call NILMBackend.from_checkpoints() once at startup, then call
    .predict_event() for each incoming event window.

DIRECTORY LAYOUT EXPECTED
--------------------------
checkpoints/
    best_Clothes_Dryer_v4.pt
    best_Clothes_Dryer_v4_meta.json
    best_Clothes_Washer_v4.pt
    best_Clothes_Washer_v4_meta.json
    ... (one .pt + one _meta.json per appliance)

nilm_datasets/
    norm_caps.csv
    max_lens.csv
    Clothes_Dryer_crosscorr_profile.npy
    Clothes_Washer_crosscorr_profile.npy
    Dishwasher_crosscorr_profile.npy
    Heat_Pump_crosscorr_profile.npy
    Kitchen_Fridge_crosscorr_profile.npy
    TV_crosscorr_profile.npy
"""

import os
import json
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ─────────────────────────────────────────────────────────────────────────────
# 1.  Model definition  (copied verbatim from NILM_Pipeline_v4.ipynb)
# ─────────────────────────────────────────────────────────────────────────────

class BiLSTM_S2S(nn.Module):
    """
    Bidirectional 2-layer LSTM Seq-to-Seq NILM model.
    Input : (B, T, n_channels)
    Output: (B, T)  — predicted appliance power (normalised [0,1])
    """
    def __init__(self, n_channels=7, hidden1=128, hidden2=64, dropout=0.3):
        super().__init__()
        self.lstm1 = nn.LSTM(
            input_size=n_channels, hidden_size=hidden1,
            num_layers=1, batch_first=True, bidirectional=True,
        )
        self.drop1 = nn.Dropout(dropout)
        self.lstm2 = nn.LSTM(
            input_size=hidden1 * 2, hidden_size=hidden2,
            num_layers=1, batch_first=True, bidirectional=True,
        )
        self.drop2 = nn.Dropout(dropout)
        self.head = nn.Sequential(
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
        out    = self.head(out)
        return out.squeeze(-1)


# ─────────────────────────────────────────────────────────────────────────────
# 2.  Feature engineering helpers  (copied from NILM_Preprocessing_v4.ipynb)
# ─────────────────────────────────────────────────────────────────────────────

def normalize_with_cap(arr: np.ndarray, cap: float) -> np.ndarray:
    """P99-normalise to [0, 1]."""
    arr = np.clip(arr, 0, None).astype(np.float32)
    if cap <= 0:
        return arr
    return np.clip(arr / cap, 0.0, 1.0).astype(np.float32)


def compute_autocorr(window: np.ndarray) -> np.ndarray:
    """Normalised autocorrelation — lag-0 = 1.0."""
    n   = len(window)
    w   = window - window.mean()
    var = np.var(w) + 1e-8
    result    = np.zeros(n, dtype=np.float32)
    result[0] = 1.0
    for lag in range(1, n):
        result[lag] = float(np.mean(w[:n - lag] * w[lag:]) / var)
    return np.clip(result, -1.0, 1.0)


def compute_crosscorr(window: np.ndarray, profile: np.ndarray) -> np.ndarray:
    """
    Normalised cross-correlation between window and reference profile.
    Returns a scalar broadcast to the full window length.
    """
    n = min(len(window), len(profile))
    if n == 0:
        return np.zeros(len(window), dtype=np.float32)
    w = window[:n] - window[:n].mean()
    p = profile[:n] - profile[:n].mean()
    denom = float(np.std(w) * np.std(p)) + 1e-8
    corr  = float(np.clip(np.mean(w * p) / denom, -1.0, 1.0))
    return np.full(len(window), corr, dtype=np.float32)


def compute_delta(window: np.ndarray) -> np.ndarray:
    """First difference — captures step changes."""
    delta = np.diff(window.astype(np.float32), prepend=window[0])
    return np.clip(delta, -1.0, 1.0).astype(np.float32)


def compute_delta2(window: np.ndarray) -> np.ndarray:
    """Second difference — acceleration of change."""
    d1 = np.diff(window.astype(np.float32), prepend=window[0])
    d2 = np.diff(d1, prepend=d1[0])
    return np.clip(d2, -1.0, 1.0).astype(np.float32)


def build_7ch_tensor(
    mains_window: np.ndarray,       # raw Watts, shape (L,)
    timestamps: pd.DatetimeIndex,   # length L, for hour encoding
    mains_cap: float,               # norm_caps['Whole-House Meter']
    crosscorr_profile: np.ndarray,  # pre-built profile for this appliance
) -> np.ndarray:
    """
    Construct the 7-channel feature tensor for one event window.

    Returns
    -------
    np.ndarray of shape (L, 7), float32
        Ch0: normalised raw aggregate
        Ch1: autocorrelation
        Ch2: cross-correlation vs appliance ON profile
        Ch3: sin(hour)
        Ch4: cos(hour)
        Ch5: first difference (delta)
        Ch6: second difference (delta²)
    """
    mains_norm = normalize_with_cap(mains_window, mains_cap)

    ch0 = mains_norm
    ch1 = compute_autocorr(mains_norm)
    ch2 = compute_crosscorr(mains_norm, crosscorr_profile)

    # Use midpoint timestamp for time encoding
    mid_idx  = min(len(timestamps) // 2, len(timestamps) - 1)
    mid_time = timestamps[mid_idx]
    hour     = mid_time.hour + mid_time.minute / 60.0
    sin_h    = float(np.sin(2 * np.pi * hour / 24.0))
    cos_h    = float(np.cos(2 * np.pi * hour / 24.0))
    L        = len(mains_norm)
    ch3      = np.full(L, sin_h, dtype=np.float32)
    ch4      = np.full(L, cos_h, dtype=np.float32)

    ch5 = compute_delta(mains_norm)
    ch6 = compute_delta2(mains_norm)

    return np.stack([ch0, ch1, ch2, ch3, ch4, ch5, ch6], axis=-1)  # (L, 7)


def pad_to_max_len(
    tensor_7ch: np.ndarray,  # (L, 7)
    max_len: int,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Pad (L, 7) → (1, max_len, 7) and build a mask (1, max_len).

    Returns
    -------
    X    : np.ndarray  (1, max_len, 7)  float32
    mask : np.ndarray  (1, max_len)     float32   1=real, 0=padding
    """
    L      = min(len(tensor_7ch), max_len)
    X      = np.zeros((1, max_len, 7),  dtype=np.float32)
    mask   = np.zeros((1, max_len),     dtype=np.float32)
    X[0, :L, :]  = tensor_7ch[:L]
    mask[0, :L]  = 1.0
    return X, mask


# ─────────────────────────────────────────────────────────────────────────────
# 3.  Main backend class
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ApplianceMeta:
    """All per-appliance scalars needed at inference time."""
    appliance:   str
    norm_cap:    float   # P99 cap in Watts
    max_len:     int     # padding length (minutes)
    opt_thr:     float   # ON/OFF threshold in normalised space
    thr_watts:   float   # opt_thr * norm_cap
    n_channels:  int
    hidden1:     int
    hidden2:     int
    dropout:     float
    crosscorr_profile: np.ndarray  # shape varies per appliance


@dataclass
class PredictionResult:
    """Return value of NILMBackend.predict_event()."""
    appliance:        str
    power_watts:      np.ndarray  # shape (real_len,) — Watts per minute
    is_on:            np.ndarray  # shape (real_len,) — bool
    energy_wh:        float
    norm_cap:         float
    opt_thr_watts:    float


class NILMBackend:
    """
    Loads all trained appliance models + metadata once, then exposes
    a simple predict_event() method for the backend to call.

    Parameters
    ----------
    checkpoint_dir : str
        Folder containing best_*_v4.pt and best_*_v4_meta.json files.
    nilm_dir : str
        Folder containing norm_caps.csv, max_lens.csv, and
        *_crosscorr_profile.npy files.
    device : str
        'cuda' or 'cpu'.
    """

    MAINS_COL = 'Whole-House Meter'
    WATTS_ON_THRESHOLD = 50.0   # hard clip applied before normalization

    def __init__(
        self,
        models:    Dict[str, BiLSTM_S2S],
        metas:     Dict[str, ApplianceMeta],
        mains_cap: float,
        device:    torch.device,
    ):
        self.models    = models
        self.metas     = metas
        self.mains_cap = mains_cap
        self.device    = device

    # ── constructor ──────────────────────────────────────────────────────────

    @classmethod
    def from_checkpoints(
        cls,
        checkpoint_dir: str = 'checkpoints',
        nilm_dir:       str = 'nilm_datasets',
        device_str:     str = 'auto',
    ) -> 'NILMBackend':
        """
        Load everything from disk and return a ready-to-use NILMBackend.

        Call this ONCE at server startup.
        """
        if device_str == 'auto':
            device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            device = torch.device(device_str)

        # ── 1. norm_caps ─────────────────────────────────────────────────────
        norm_caps_path = os.path.join(nilm_dir, 'norm_caps.csv')
        if not os.path.exists(norm_caps_path):
            raise FileNotFoundError(f'norm_caps.csv not found at {norm_caps_path}')
        norm_caps_df = pd.read_csv(norm_caps_path)
        norm_caps    = norm_caps_df.iloc[0].to_dict()
        mains_cap    = float(norm_caps[cls.MAINS_COL])
        print(f'[NILMBackend] norm_caps loaded — mains cap = {mains_cap:.1f} W')

        # ── 2. max_lens ──────────────────────────────────────────────────────
        max_lens_path = os.path.join(nilm_dir, 'max_lens.csv')
        if not os.path.exists(max_lens_path):
            raise FileNotFoundError(f'max_lens.csv not found at {max_lens_path}')
        max_lens_df = pd.read_csv(max_lens_path)
        max_lens    = {k: int(v) for k, v in max_lens_df.iloc[0].to_dict().items()}
        print(f'[NILMBackend] max_lens loaded — {len(max_lens)} appliances')

        # ── 3. cross-corr profiles ───────────────────────────────────────────
        profiles: Dict[str, np.ndarray] = {}
        for fname in os.listdir(nilm_dir):
            if fname.endswith('_crosscorr_profile.npy'):
                safe = fname.replace('_crosscorr_profile.npy', '')
                app  = safe.replace('_', ' ')
                profiles[app] = np.load(os.path.join(nilm_dir, fname))
        print(f'[NILMBackend] cross-corr profiles loaded — {len(profiles)} appliances')

        # ── 4. model checkpoints + meta JSONs ────────────────────────────────
        models: Dict[str, BiLSTM_S2S] = {}
        metas:  Dict[str, ApplianceMeta] = {}

        meta_files = [f for f in os.listdir(checkpoint_dir) if f.endswith('_meta.json')]
        if not meta_files:
            raise FileNotFoundError(
                f'No *_meta.json files in {checkpoint_dir}. '
                'Run the metadata-saving cell in NILM_Pipeline_v4.ipynb first.'
            )

        for mf in sorted(meta_files):
            meta_path = os.path.join(checkpoint_dir, mf)
            with open(meta_path) as f:
                raw = json.load(f)

            app  = raw['appliance']
            ckpt = raw['checkpoint']

            if not os.path.exists(ckpt):
                print(f'  [WARNING] Checkpoint missing for {app}: {ckpt} — skipping')
                continue

            if app not in profiles:
                print(f'  [WARNING] No cross-corr profile for {app} — skipping')
                continue

            model = BiLSTM_S2S(
                n_channels=raw['n_channels'],
                hidden1=raw['hidden1'],
                hidden2=raw['hidden2'],
                dropout=raw['dropout'],
            ).to(device)
            model.load_state_dict(torch.load(ckpt, map_location=device))
            model.eval()

            models[app] = model
            metas[app]  = ApplianceMeta(
                appliance          = app,
                norm_cap           = float(raw['norm_cap']),
                max_len            = int(raw['max_len']),
                opt_thr            = float(raw['opt_thr']),
                thr_watts          = float(raw['thr_watts']),
                n_channels         = int(raw['n_channels']),
                hidden1            = int(raw['hidden1']),
                hidden2            = int(raw['hidden2']),
                dropout            = float(raw['dropout']),
                crosscorr_profile  = profiles[app],
            )
            print(f'  Loaded: {app:<22}  '
                  f'max_len={raw["max_len"]:>4}  '
                  f'opt_thr={raw["opt_thr"]:.4f}  '
                  f'({raw["thr_watts"]:.1f} W)')

        print(f'[NILMBackend] Ready — {len(models)} models loaded on {device}')
        return cls(models=models, metas=metas, mains_cap=mains_cap, device=device)

    # ── inference ────────────────────────────────────────────────────────────

    def predict_event(
        self,
        appliance:      str,
        mains_watts:    np.ndarray,       # raw aggregate, shape (L,)
        timestamps:     pd.DatetimeIndex, # length L, 1-min resolution
    ) -> PredictionResult:
        """
        Run inference for one event window for a single appliance.

        Parameters
        ----------
        appliance   : exact name, e.g. 'Heat Pump'
        mains_watts : 1D array of aggregate power readings in Watts (1-min steps)
        timestamps  : matching DatetimeIndex (same length as mains_watts)

        Returns
        -------
        PredictionResult with power_watts, is_on, energy_wh
        """
        if appliance not in self.models:
            raise KeyError(f'No model loaded for appliance "{appliance}". '
                           f'Available: {list(self.models.keys())}')

        meta  = self.metas[appliance]
        model = self.models[appliance]

        # 1. Apply 50W hard threshold (same as preprocessing)
        mains_clipped = np.clip(mains_watts, 0, None)
        mains_clipped[mains_clipped < self.WATTS_ON_THRESHOLD] = 0.0

        # 2. Build 7-channel feature tensor
        tensor_7ch = build_7ch_tensor(
            mains_window      = mains_clipped,
            timestamps        = timestamps,
            mains_cap         = self.mains_cap,
            crosscorr_profile = meta.crosscorr_profile,
        )  # (L, 7)

        # 3. Pad to MAX_LEN and create mask
        X, mask = pad_to_max_len(tensor_7ch, meta.max_len)  # (1, max_len, 7)

        # 4. Run model
        with torch.no_grad():
            x_tensor = torch.from_numpy(X).to(self.device)  # (1, max_len, 7)
            pred_norm = model(x_tensor).cpu().numpy()        # (1, max_len)

        # 5. Trim to real length and denormalise
        real_len    = int(mask[0].sum())
        pred_norm   = pred_norm[0, :real_len]                # (real_len,)
        power_watts = pred_norm * meta.norm_cap              # back to Watts

        # 6. ON/OFF classification using optimal threshold
        is_on = power_watts > meta.thr_watts

        # 7. Energy (Wh) — sum ON-state power * 1 minute per step / 60
        energy_wh = float(power_watts[is_on].sum() / 60.0)

        return PredictionResult(
            appliance     = appliance,
            power_watts   = power_watts,
            is_on         = is_on,
            energy_wh     = energy_wh,
            norm_cap      = meta.norm_cap,
            opt_thr_watts = meta.thr_watts,
        )

    def predict_all_appliances(
        self,
        mains_watts: np.ndarray,
        timestamps:  pd.DatetimeIndex,
    ) -> Dict[str, PredictionResult]:
        """
        Run predict_event() for every loaded appliance on the same window.
        Useful when you receive a whole-house reading and want to disaggregate
        all appliances in one call.
        """
        return {
            app: self.predict_event(app, mains_watts, timestamps)
            for app in self.models
        }

    @property
    def appliances(self) -> List[str]:
        return list(self.models.keys())


# ─────────────────────────────────────────────────────────────────────────────
# 4.  Quick usage example  (run this file directly to test loading)
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import sys

    # ── startup: load everything once ────────────────────────────────────────
    backend = NILMBackend.from_checkpoints(
        checkpoint_dir='checkpoints',
        nilm_dir='nilm_datasets',
        device_str='auto',
    )

    print(f'\nAppliances available: {backend.appliances}\n')

    # ── simulate one incoming event window ───────────────────────────────────
    # In production this would come from your meter / API.
    # Here we just fabricate a 90-minute window at 1-min resolution.
    np.random.seed(0)
    N   = 90
    now = pd.Timestamp.now().floor('min')
    ts  = pd.date_range(start=now, periods=N, freq='1min')

    # Fake aggregate: baseline ~400W with a 2000W spike in the middle
    mains = np.full(N, 400.0)
    mains[20:70] += np.random.normal(2000, 100, 50)

    # ── run inference for all appliances ─────────────────────────────────────
    results = backend.predict_all_appliances(mains, ts)

    print(f'{"Appliance":<22} {"Energy (Wh)":>12} {"ON steps":>10} {"Peak W":>10}')
    print('-' * 58)
    for app, res in results.items():
        on_steps = int(res.is_on.sum())
        peak_w   = float(res.power_watts.max()) if len(res.power_watts) else 0.0
        print(f'{app:<22} {res.energy_wh:>12.2f} {on_steps:>10} {peak_w:>10.1f}')

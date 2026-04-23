import numpy as np
import torch

from model_loader import get_model_assets
from preprocess import build_features
from tariff import calc_bill_jod, get_tier


def forecast(timestamps: list[str], readings: list[float], meter_id: str | None = None) -> dict:
    assets = get_model_assets()
    model = assets["model"]
    scaler = assets["scaler"]
    feats = assets["feats"]

    if model is None or scaler is None or feats is None:
        raise RuntimeError("Forecast model assets are not loaded")

    if len(timestamps) != len(readings):
        raise ValueError("timestamps and readings must be the same length")

    window = build_features(timestamps=timestamps, readings=readings, feats=feats)
    window = np.nan_to_num(window, nan=0.0)
    window_scaled = scaler.transform(window)

    with torch.no_grad():
        xb = torch.tensor(window_scaled, dtype=torch.float32).unsqueeze(0)
        raw_output = float(model(xb).item())

    pred_kwh = float(max(np.expm1(raw_output), 0.0))

    return {
        "meter_id": meter_id,
        "predicted_kwh": round(pred_kwh, 2),
        "tariff_tier": get_tier(pred_kwh),
        "estimated_bill_jod": calc_bill_jod(pred_kwh),
    }
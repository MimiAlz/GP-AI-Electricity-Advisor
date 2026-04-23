import io
import pickle
from pathlib import Path

import torch

from model import MinimalLSTM

model = None
scaler = None
feats = None
cfg = None

def load_model():
    global model, scaler, feats, cfg
    model_path = Path(__file__).resolve().parent / "forecast_model.pkl"
    try:
        if model_path.exists() and model_path.stat().st_size > 0:
            with model_path.open("rb") as f:
                bundle = pickle.load(f)

            cfg = bundle["model_config"]
            scaler = bundle["scaler"]
            feats = bundle["feats"]

            loaded_model = MinimalLSTM(cfg["n_feats"], cfg["hidden_size"], cfg["dropout"])
            loaded_model.load_state_dict(
                torch.load(io.BytesIO(bundle["model_state_bytes"]), map_location="cpu")
            )
            loaded_model.eval()
            model = loaded_model
        else:
            model = None
            scaler = None
            feats = None
            cfg = None
    except Exception:
        model = None
        scaler = None
        feats = None
        cfg = None

def get_model():
    return model


def get_model_assets():
    return {
        "model": model,
        "scaler": scaler,
        "feats": feats,
        "cfg": cfg,
    }
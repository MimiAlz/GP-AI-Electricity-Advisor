"""
nilm_loader.py
==============
Singleton loader for the NILMBackend — mirrors model_loader.py.

Call load_nilm() once at server startup (inside the FastAPI startup event).
Call get_nilm_backend() from route handlers; it raises HTTP 503 if not ready.
"""

from pathlib import Path
from typing import Optional

from fastapi import HTTPException

from nilm.nilm_inference import NILMBackend

_backend: Optional[NILMBackend] = None

NILM_DIR = str(Path(__file__).resolve().parent / "nilm")


def load_nilm() -> None:
    """Load all NILM appliance models from disk.  Call once at startup."""
    global _backend
    try:
        _backend = NILMBackend.from_checkpoints(
            checkpoint_dir=NILM_DIR,
            nilm_dir=NILM_DIR,
            device_str="cpu",
        )
    except Exception as exc:
        print(f"[nilm_loader] WARNING: NILM models failed to load — {exc}")
        _backend = None


def get_nilm_backend() -> NILMBackend:
    """Return the loaded NILMBackend or raise 503 if unavailable."""
    if _backend is None:
        raise HTTPException(
            status_code=503,
            detail="NILM models are not loaded. Check server logs for details.",
        )
    if not _backend.appliances:
        raise HTTPException(
            status_code=503,
            detail="NILM backend loaded but no appliance models are available.",
        )
    return _backend

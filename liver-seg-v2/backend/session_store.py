"""
session_store.py
----------------
In-memory session store for lazy slice loading and 3D mesh serving.

Session data structure:
{
    "ct_path":             str,
    "pred_path":           str,
    "n_slices":            int,
    "tumor_slice_indices": list[int],
    "slice_meta":          list[dict],
    "tumor_detected":      bool,
    "tumor_voxels":        int,
    "liver_voxels":        int,
    "volume_name":         str,
    "mesh":                dict | None,   ← NEW: {liver, tumor} mesh data
    "created_at":          float,
}
"""

import logging
import shutil
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SESSION_TTL_HOURS = 1
SESSIONS_DIR = Path(__file__).parent / "sessions"

_store: dict[str, dict] = {}


def init():
    SESSIONS_DIR.mkdir(exist_ok=True)
    for folder in SESSIONS_DIR.iterdir():
        if folder.is_dir():
            shutil.rmtree(folder, ignore_errors=True)
    logger.info(f"Session store initialised at {SESSIONS_DIR}")


def session_dir(session_id: str) -> Path:
    d = SESSIONS_DIR / session_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def save(session_id: str, data: dict) -> None:
    data["created_at"] = time.time()
    _store[session_id] = data
    logger.info(f"Session {session_id} saved ({data.get('n_slices','?')} slices)")


def save_mesh(session_id: str, mesh: dict) -> None:
    """Store mesh data into an existing session."""
    if session_id in _store:
        _store[session_id]["mesh"] = mesh
        logger.info(f"Session {session_id} mesh stored")


def get(session_id: str) -> Optional[dict]:
    return _store.get(session_id)


def cleanup_expired() -> int:
    cutoff = time.time() - SESSION_TTL_HOURS * 3600
    expired = [sid for sid, d in _store.items() if d["created_at"] < cutoff]
    for sid in expired:
        shutil.rmtree(SESSIONS_DIR / sid, ignore_errors=True)
        del _store[sid]
        logger.info(f"Session {sid} expired")
    return len(expired)

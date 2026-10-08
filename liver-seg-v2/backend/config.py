"""
config.py
---------
Central configuration for the nnUNet backend.

HOW TO POINT THE APP AT YOUR DATA
----------------------------------
The app looks for nnunet_data in this order:

  1. NNUNET_BASE environment variable
     Set it once by running this in Command Prompt:
       setx NNUNET_BASE "G:\\My Drive\\08-3D-Liver-Tumor-Segmentation\\nnunet_data"
     Then restart the terminal.

  2. NNUNET_BASE_FALLBACK string below
     Edit it directly if you prefer not to use an env variable.

  3. Common Google Drive locations (auto-checked automatically)

If none are found the app will print a clear error at startup telling
you exactly what to fix.
"""

import os
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
#  EDIT THIS if you are not using an environment variable
# ─────────────────────────────────────────────────────────────────────────────
NNUNET_BASE_FALLBACK: str = r"C:\Users\DYPIU\Desktop\08-3D-Liver-Tumor-Segmentation\nnunet_data"

# ─────────────────────────────────────────────────────────────────────────────
#  Common Google Drive sync locations — checked automatically
#  Add more rows here if your Drive mounts to a different letter
# ─────────────────────────────────────────────────────────────────────────────
_GDRIVE_CANDIDATES: list[str] = [
    r"G:\My Drive\08-3D-Liver-Tumor-Segmentation\nnunet_data",
    r"H:\My Drive\08-3D-Liver-Tumor-Segmentation\nnunet_data",
    r"I:\My Drive\08-3D-Liver-Tumor-Segmentation\nnunet_data",
    os.path.expanduser(r"~\Google Drive\08-3D-Liver-Tumor-Segmentation\nnunet_data"),
    os.path.expanduser(r"~\My Drive\08-3D-Liver-Tumor-Segmentation\nnunet_data"),
    os.path.expanduser(r"~\OneDrive\08-3D-Liver-Tumor-Segmentation\nnunet_data"),
]


def _resolve_nnunet_base() -> str:
    # 1. Environment variable
    env_val = os.environ.get("NNUNET_BASE", "").strip()
    if env_val and Path(env_val).exists():
        print(f"[config] NNUNET_BASE from environment variable: {env_val}")
        return env_val

    # 2. Hardcoded fallback
    if Path(NNUNET_BASE_FALLBACK).exists():
        print(f"[config] NNUNET_BASE from fallback: {NNUNET_BASE_FALLBACK}")
        return NNUNET_BASE_FALLBACK

    # 3. Auto-detect Google Drive
    for candidate in _GDRIVE_CANDIDATES:
        if Path(candidate).exists():
            print(f"[config] NNUNET_BASE auto-detected: {candidate}")
            return candidate

    raise RuntimeError(
        "\n\n"
        "=" * 60 + "\n"
        "  ERROR: nnunet_data folder not found!\n"
        "=" * 60 + "\n\n"
        "  Fix ONE of the following:\n\n"
        "  A) Open Command Prompt and run:\n"
        '     setx NNUNET_BASE "C:\\full\\path\\to\\nnunet_data"\n'
        "     Then close the terminal and re-run run.bat\n\n"
        "  B) Open backend\\config.py and edit NNUNET_BASE_FALLBACK\n\n"
        "  The nnunet_data folder must contain:\n"
        "     nnUNet_results\\Dataset003_Liver\\...\n"
        "     nnUNet_preprocessed\\Dataset003_Liver\\...\n"
        "     nnUNet_raw\\Dataset003_Liver\\...\n"
        "=" * 60 + "\n"
    )


# Resolved at import time — fails immediately with a clear message if missing
NNUNET_BASE: str = _resolve_nnunet_base()

# ─────────────────────────────────────────────────────────────────────────────
#  DO NOT EDIT BELOW (unless dataset ID or trainer name changed)
# ─────────────────────────────────────────────────────────────────────────────

DATASET_ID:     str       = "003"
DATASET_NAME:   str       = f"Dataset{DATASET_ID}_Liver"
TRAINER:        str       = "nnUNetTrainer_500epochs"
ENSEMBLE_FOLDS: list[int] = [0, 1, 2, 3]
CHECKPOINT:     str       = "checkpoint_final.pth"

NNUNET_RAW:     str = os.path.join(NNUNET_BASE, "nnUNet_raw")
NNUNET_PREP:    str = os.path.join(NNUNET_BASE, "nnUNet_preprocessed")
NNUNET_RESULTS: str = os.path.join(NNUNET_BASE, "nnUNet_results")

TEMP_DIR:    Path = Path(__file__).parent / "temp"
TEMP_INPUT:  Path = TEMP_DIR / "input"
TEMP_OUTPUT: Path = TEMP_DIR / "output"

MAX_UPLOAD_MB:   int       = 500
ALLOWED_ORIGINS: list[str] = [
    "http://localhost:5173",
    "http://localhost:3000",
]

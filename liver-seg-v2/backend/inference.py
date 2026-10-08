"""
inference.py
------------
nnUNet 2D 4-fold ensemble prediction with lazy-slice session support.
Now accepts volume_name and stores it in the session for HTML filename generation.
"""

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict

import nibabel as nib
import numpy as np

import session_store
from config import (
    DATASET_ID, TRAINER, ENSEMBLE_FOLDS, CHECKPOINT,
    NNUNET_RAW, NNUNET_PREP, NNUNET_RESULTS, TEMP_INPUT, TEMP_OUTPUT,
)

logger = logging.getLogger(__name__)


def _build_env() -> dict:
    env = os.environ.copy()
    env["nnUNet_raw"]          = NNUNET_RAW
    env["nnUNet_preprocessed"] = NNUNET_PREP
    env["nnUNet_results"]      = NNUNET_RESULTS
    env["nnUNet_n_proc_DA"]    = "4"
    env["OMP_NUM_THREADS"]     = "4"
    env["ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS"] = "4"
    return env


def _stage_input(src: str, request_id: str) -> tuple[Path, Path, str]:
    input_dir  = TEMP_INPUT  / request_id
    output_dir = TEMP_OUTPUT / request_id
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    case_name = f"liver_{request_id}"
    shutil.copy2(src, input_dir / f"{case_name}_0000.nii.gz")
    logger.info(f"[{request_id}] Staged input")
    return input_dir, output_dir, case_name


def _predict(input_dir: Path, output_dir: Path, request_id: str) -> None:
    cmd = [
        "nnUNetv2_predict",
        "-i", str(input_dir),
        "-o", str(output_dir),
        "-d", DATASET_ID,
        "-c", "2d",
        "-f", *[str(f) for f in ENSEMBLE_FOLDS],
        "-tr", TRAINER,
        "-chk", CHECKPOINT,
        "-npp", "4",
        "-nps", "4",
    ]
    logger.info(f"[{request_id}] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, env=_build_env(), capture_output=True, text=True)
    if result.stdout:
        logger.info(f"[{request_id}] stdout:\n{result.stdout[-2000:]}")
    if result.stderr:
        logger.warning(f"[{request_id}] stderr:\n{result.stderr[-500:]}")
    if result.returncode != 0:
        raise RuntimeError(
            f"nnUNetv2_predict failed (code {result.returncode}).\n"
            f"stderr: {result.stderr[-400:]}"
        )


def _load_prediction(output_dir: Path, case_name: str) -> tuple[np.ndarray, nib.Nifti1Image]:
    pred_path = output_dir / f"{case_name}.nii.gz"
    if not pred_path.exists():
        candidates = list(output_dir.glob("*.nii.gz"))
        if not candidates:
            raise FileNotFoundError(f"No prediction output in {output_dir}")
        pred_path = candidates[0]
        logger.warning(f"Using fallback: {pred_path.name}")
    nii = nib.load(pred_path)
    return nii.get_fdata().astype(np.uint8), nii


def _clip_tumour_to_liver(labels: np.ndarray) -> np.ndarray:
    """Zero tumour voxels outside the liver region."""
    invalid = (labels == 2) & ~(labels >= 1)
    if invalid.sum() > 0:
        labels = labels.copy()
        labels[invalid] = 0
        logger.info(f"Clipped {invalid.sum():,} tumour voxels outside liver")
    return labels


def _compute_slice_meta(labels: np.ndarray) -> tuple[list, list]:
    n = labels.shape[2]
    meta, tumor_idxs = [], []
    for z in range(n):
        sl = labels[:, :, z]
        tp = int((sl == 2).sum())
        lp = int((sl >= 1).sum())
        meta.append({"slice_index": z, "tumor_pixels": tp,
                     "liver_pixels": lp, "has_tumor": tp > 0})
        if tp > 0:
            tumor_idxs.append(z)
    return meta, tumor_idxs


def _save_session(
    session_id: str,
    ct_path: str,
    labels: np.ndarray,
    pred_nii: nib.Nifti1Image,
    slice_meta: list,
    tumor_idxs: list,
    liver_voxels: int,
    tumor_voxels: int,
    tumor_detected: bool,
    volume_name: str,
) -> None:
    sdir = session_store.session_dir(session_id)

    ct_dest = sdir / "ct.nii.gz"
    shutil.copy2(ct_path, ct_dest)

    pred_dest = sdir / "pred.nii.gz"
    nib.save(nib.Nifti1Image(labels.astype(np.uint8), pred_nii.affine, pred_nii.header),
             str(pred_dest))

    session_store.save(session_id, {
        "ct_path":             str(ct_dest),
        "pred_path":           str(pred_dest),
        "n_slices":            int(labels.shape[2]),
        "tumor_slice_indices": tumor_idxs,
        "slice_meta":          slice_meta,
        "tumor_detected":      tumor_detected,
        "tumor_voxels":        tumor_voxels,
        "liver_voxels":        liver_voxels,
        "volume_name":         volume_name,   # ← stored for HTML filename
    })
    logger.info(f"[{session_id}] Session saved (volume: {volume_name})")


def run_inference(nifti_path: str, session_id: str, volume_name: str = "") -> Dict:
    """
    Run nnUNet prediction and save session for lazy slice serving.

    Parameters
    ----------
    nifti_path  : path to uploaded .nii.gz
    session_id  : unique ID for this request
    volume_name : clean name derived from original filename (e.g. "liver_0001")
    """
    input_dir, output_dir, case_name = _stage_input(nifti_path, session_id)

    try:
        _predict(input_dir, output_dir, session_id)
        labels, pred_nii = _load_prediction(output_dir, case_name)
        labels            = _clip_tumour_to_liver(labels)

        liver_mask     = labels >= 1
        tumor_mask     = labels == 2
        liver_voxels   = int(liver_mask.sum())
        tumor_voxels   = int(tumor_mask.sum())
        tumor_detected = tumor_voxels > 0

        logger.info(
            f"[{session_id}] liver={liver_voxels:,} "
            f"tumour={tumor_voxels:,} detected={tumor_detected}"
        )

        slice_meta, tumor_idxs = _compute_slice_meta(labels)

        _save_session(
            session_id, nifti_path, labels, pred_nii,
            slice_meta, tumor_idxs,
            liver_voxels, tumor_voxels, tumor_detected,
            volume_name,
        )

        return {
            "liver":               liver_mask,
            "tumor":               tumor_mask,
            "labels":              labels,
            "tumor_detected":      tumor_detected,
            "tumor_voxels":        tumor_voxels,
            "liver_voxels":        liver_voxels,
            "n_slices":            int(labels.shape[2]),
            "tumor_slice_indices": tumor_idxs,
            "slice_meta":          slice_meta,
            "session_id":          session_id,
        }

    finally:
        shutil.rmtree(input_dir,  ignore_errors=True)
        shutil.rmtree(output_dir, ignore_errors=True)
        logger.info(f"[{session_id}] Temp dirs cleaned up")
"""
mesh_generator.py
-----------------
Converts boolean numpy masks into smooth 3D surface meshes.

Key fixes:
  - Liver uses step_size=2 in marching cubes (was 1) — far fewer raw triangles,
    cleaner geometry, less speckle noise from nnUNet 2D slice boundaries
  - Tumour uses adaptive smoothing based on voxel count
  - Fallback to raw mask if smoothing erases structure
"""
'''
import logging
from typing import Dict, Any, Optional

import numpy as np
from scipy.ndimage import gaussian_filter, binary_fill_holes, binary_closing
from skimage import measure
from skimage.morphology import ball

logger = logging.getLogger(__name__)


def _smooth_mask(mask: np.ndarray, sigma: float) -> np.ndarray:
    if sigma <= 0:
        return mask
    blurred = gaussian_filter(mask.astype(np.float32), sigma=sigma)
    return blurred > 0.4


def _fill_and_close(mask: np.ndarray, radius: int) -> np.ndarray:
    if radius <= 0:
        return mask
    struct = ball(radius)
    closed = binary_closing(mask, structure=struct)
    filled = np.zeros_like(closed)
    for i in range(closed.shape[0]):
        filled[i] = binary_fill_holes(closed[i])
    return filled


def _laplacian_smooth(vertices, faces, iterations=8, lambda_=0.5):
    """Vectorised Laplacian smooth — replaces pure-Python loop (was minutes, now seconds)."""
    import scipy.sparse as sp

    n = len(vertices)
    # Build sparse adjacency matrix from face edges
    i_idx = np.concatenate([faces[:, 0], faces[:, 1], faces[:, 2],
                             faces[:, 1], faces[:, 2], faces[:, 0]])
    j_idx = np.concatenate([faces[:, 1], faces[:, 2], faces[:, 0],
                             faces[:, 0], faces[:, 1], faces[:, 2]])
    data  = np.ones(len(i_idx), dtype=np.float32)
    A     = sp.csr_matrix((data, (i_idx, j_idx)), shape=(n, n))

    # Row-normalise to get averaging matrix
    row_sums = np.asarray(A.sum(axis=1)).ravel()
    row_sums[row_sums == 0] = 1.0
    D_inv = sp.diags(1.0 / row_sums)
    L     = D_inv @ A          # L[i] = mean of neighbours of i

    verts = vertices.copy().astype(np.float32)
    for _ in range(iterations):
        neighbour_mean = L @ verts
        verts += lambda_ * (neighbour_mean - verts)
    return verts


def _normalise_vertices(vertices):
    centre = (vertices.max(axis=0) + vertices.min(axis=0)) / 2.0
    verts  = vertices - centre
    scale  = np.abs(verts).max()
    if scale > 0:
        verts /= scale
    return verts


def _decimate(faces, max_faces):
    if len(faces) <= max_faces:
        return faces
    idx = np.random.choice(len(faces), max_faces, replace=False)
    return faces[idx]


def _adaptive_params(voxel_count: int, is_liver: bool) -> dict:
    """
    Adaptive smoothing parameters based on structure size.

    Liver is always large — use strong smoothing + step_size=2 in
    marching cubes to get clean geometry without millions of tiny faces.

    Tumour bands:
        tiny   < 1 000   — no smoothing, no closing
        small  < 5 000   — very light
        medium < 50 000  — moderate
        large  >= 50 000 — full
    """
    if is_liver:
        return dict(
            sigma=3.5,
            iterations=8,
            closing_radius=4,
            step_size=2,      # ← key: reduces raw face count ~4x, cleaner surface
            max_faces=80_000,
            min_voxels=8,
        )

    # Tumour — adaptive
    if voxel_count < 1_000:
        return dict(sigma=0.0, iterations=2,  closing_radius=0, step_size=1, max_faces=20_000, min_voxels=8)
    if voxel_count < 5_000:
        return dict(sigma=0.8, iterations=5,  closing_radius=1, step_size=1, max_faces=25_000, min_voxels=8)
    if voxel_count < 50_000:
        return dict(sigma=1.5, iterations=5,  closing_radius=2, step_size=1, max_faces=35_000, min_voxels=8)
    return     dict(sigma=2.5, iterations=6,  closing_radius=3, step_size=1, max_faces=40_000, min_voxels=8)


def mask_to_mesh(
    mask: np.ndarray,
    is_liver: bool = False,
) -> Optional[Dict[str, Any]]:
    voxel_count = int(mask.sum())
    if voxel_count < 8:
        logger.info(f"Mask too small ({voxel_count} voxels) — skipping")
        return None

    p = _adaptive_params(voxel_count, is_liver)
    label = "Liver" if is_liver else "Tumour"
    logger.info(
        f"{label}: {voxel_count:,} voxels | "
        f"sigma={p['sigma']} iter={p['iterations']} "
        f"closing={p['closing_radius']} step={p['step_size']}"
    )

    processed = _fill_and_close(mask, radius=p["closing_radius"])
    processed = _smooth_mask(processed, sigma=p["sigma"])

    if processed.sum() < p["min_voxels"]:
        logger.warning(
            f"{label}: smoothing erased mask "
            f"({voxel_count} → {processed.sum()} voxels). Using raw mask."
        )
        processed = mask.copy()

    if processed.sum() < 8:
        logger.warning(f"{label}: still too small after fallback — skipping")
        return None

    try:
        verts, faces, _, _ = measure.marching_cubes(
            processed.astype(np.float32),
            level=0.5,
            step_size=p["step_size"],
            allow_degenerate=False,
        )
    except Exception as exc:
        logger.error(f"Marching cubes failed: {exc}")
        return None

    logger.info(f"{label} raw mesh: {len(verts)} verts, {len(faces)} faces")

    if p["iterations"] > 0 and len(verts) > 0:
        verts = _laplacian_smooth(verts, faces,
                                  iterations=p["iterations"], lambda_=0.5)

    faces = _decimate(faces, p["max_faces"])
    verts = _normalise_vertices(verts)

    logger.info(f"{label} final mesh: {len(verts)} verts, {len(faces)} faces")

    return {
        "vertices":     verts.tolist(),
        "faces":        faces.tolist(),
        "vertex_count": len(verts),
        "face_count":   len(faces),
    }


def generate_meshes(masks) -> Dict:
    logger.info("Generating liver mesh ...")
    liver_mesh = mask_to_mesh(masks["liver"], is_liver=True)

    logger.info("Generating tumour mesh ...")
    tumor_mesh = mask_to_mesh(masks["tumor"], is_liver=False)

    return {"liver": liver_mesh, "tumor": tumor_mesh}

    '''
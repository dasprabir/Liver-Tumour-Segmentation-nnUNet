"""
main.py
-------
FastAPI application — nnUNet 2D 4-fold ensemble.

Endpoints
---------
GET  /health
GET  /model/info
POST /predict
GET  /slice/{session_id}/{z}
GET  /slice-raw/{session_id}/{z}
GET  /slice-coronal/{session_id}/{y}
GET  /slice-coronal-raw/{session_id}/{y}
GET  /slice-sagittal/{session_id}/{x}
GET  /slice-sagittal-raw/{session_id}/{x}
GET  /session-meta/{session_id}
GET  /save-results/{session_id}
POST /demo/upload
GET  /demo/viewer/{case}
GET  /demo/result/{case}
"""

import asyncio
import base64
from functools import partial
import io
import json
import logging
import os
import shutil
import tempfile
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict

import nibabel as nib
import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, FileResponse
import httpx


from PIL import Image

import session_store
from config import (
    DATASET_ID, DATASET_NAME, TRAINER, ENSEMBLE_FOLDS, CHECKPOINT,
    NNUNET_BASE, NNUNET_RESULTS, MAX_UPLOAD_MB, ALLOWED_ORIGINS,
    TEMP_INPUT, TEMP_OUTPUT,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Liver HU window — matches preprocessing in 01_preprocessing_msd_to_npy_v2.ipynb
# (clip to [-100, 400] before z-score normalisation)
HU_MIN = -100
HU_MAX =  400
LIVER_COLOUR = np.array([50,  220, 200, 150], dtype=np.uint8)
TUMOR_COLOUR = np.array([255,  40,  40, 200], dtype=np.uint8)

DEMO_RESULTS = Path(__file__).parent / "resultsTs"
logger.info(f"Demo results path: {DEMO_RESULTS}")

# ─────────────────────────────────────────────────────────────────
#  Blank PNG (for out-of-range orthogonal slices)
# ─────────────────────────────────────────────────────────────────

def _blank_png(w: int = 64, h: int = 64) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color=(0, 0, 0)).save(buf, format="PNG")
    return buf.getvalue()

_BLANK_PNG_BYTES = _blank_png()

# ─────────────────────────────────────────────────────────────────
#  Slice rendering
# ─────────────────────────────────────────────────────────────────

def _window_to_uint8(s: np.ndarray) -> np.ndarray:
    return ((np.clip(s, HU_MIN, HU_MAX) - HU_MIN) / (HU_MAX - HU_MIN) * 255).astype(np.uint8)


def _to_png(arr: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(arr.astype(np.uint8)).save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _render_raw(ct: np.ndarray, z: int) -> bytes:
    # After as_closest_canonical, array is (X, Y, Z).
    # Transpose slice to (Y, X) so rows=Y, cols=X — standard radiological view.
    g = _window_to_uint8(ct[:, :, z].T)   # (Y, X)
    return _to_png(np.stack([g, g, g], axis=-1))


def _render_overlay(ct: np.ndarray, lab: np.ndarray, z: int) -> bytes:
    # Same (Y, X) transpose for both CT and mask so they stay in register.
    g    = _window_to_uint8(ct[:, :, z].T)        # (Y, X)
    rgba = np.stack([g, g, g, np.full_like(g, 255)], axis=-1)
    lp   = lab[:, :, z].T >= 1
    rgba[lp] = (rgba[lp].astype(np.uint16) * (255 - LIVER_COLOUR[3]) +
                LIVER_COLOUR.astype(np.uint16) * LIVER_COLOUR[3]) // 255
    tp   = lab[:, :, z].T == 2
    rgba[tp] = (rgba[tp].astype(np.uint16) * (255 - TUMOR_COLOUR[3]) +
                TUMOR_COLOUR.astype(np.uint16) * TUMOR_COLOUR[3]) // 255
    return _to_png(rgba)


def _render_coronal_overlay(ct: np.ndarray, lab: np.ndarray, y: int) -> bytes:
    """Coronal slice — cut along Y axis (anterior-posterior).
    In RAS canonical: ct[:, y, :] gives (X, Z). Transpose → (Z, X), then
    flipud so superior (high Z) is at top of image."""
    g    = _window_to_uint8(ct[:, y, :].T)   # (Z, X)
    rgba = np.stack([g, g, g, np.full_like(g, 255)], axis=-1)
    lp   = lab[:, y, :].T >= 1
    rgba[lp] = (rgba[lp].astype(np.uint16) * (255 - LIVER_COLOUR[3]) +
                LIVER_COLOUR.astype(np.uint16) * LIVER_COLOUR[3]) // 255
    tp   = lab[:, y, :].T == 2
    rgba[tp] = (rgba[tp].astype(np.uint16) * (255 - TUMOR_COLOUR[3]) +
                TUMOR_COLOUR.astype(np.uint16) * TUMOR_COLOUR[3]) // 255
    return _to_png(np.flipud(rgba))


def _render_coronal_raw(ct: np.ndarray, y: int) -> bytes:
    g = _window_to_uint8(ct[:, y, :].T)   # (Z, X)
    return _to_png(np.flipud(np.stack([g, g, g], axis=-1)))


def _render_sagittal_overlay(ct: np.ndarray, lab: np.ndarray, x: int) -> bytes:
    """Sagittal slice — cut along X axis (left-right).
    In RAS canonical: ct[x, :, :] gives (Y, Z). Transpose → (Z, Y), then
    flipud so superior (high Z) is at top of image."""
    g    = _window_to_uint8(ct[x, :, :].T)   # (Z, Y)
    rgba = np.stack([g, g, g, np.full_like(g, 255)], axis=-1)
    lp   = lab[x, :, :].T >= 1
    rgba[lp] = (rgba[lp].astype(np.uint16) * (255 - LIVER_COLOUR[3]) +
                LIVER_COLOUR.astype(np.uint16) * LIVER_COLOUR[3]) // 255
    tp   = lab[x, :, :].T == 2
    rgba[tp] = (rgba[tp].astype(np.uint16) * (255 - TUMOR_COLOUR[3]) +
                TUMOR_COLOUR.astype(np.uint16) * TUMOR_COLOUR[3]) // 255
    return _to_png(np.flipud(rgba))


def _render_sagittal_raw(ct: np.ndarray, x: int) -> bytes:
    g = _window_to_uint8(ct[x, :, :].T)   # (Z, Y)
    return _to_png(np.flipud(np.stack([g, g, g], axis=-1)))


# ─────────────────────────────────────────────────────────────────
#  Per-plane slice meta helpers
# ─────────────────────────────────────────────────────────────────

def _compute_coronal_meta(lab: np.ndarray) -> tuple[list, list]:
    """Compute tumor/liver pixel counts for each coronal (Y) slice."""
    n = lab.shape[1]
    meta, tumor_idxs = [], []
    for y in range(n):
        sl = lab[:, y, :]
        tp = int((sl == 2).sum())
        lp = int((sl >= 1).sum())
        meta.append({"slice_index": y, "tumor_pixels": tp,
                     "liver_pixels": lp, "has_tumor": tp > 0})
        if tp > 0:
            tumor_idxs.append(y)
    return meta, tumor_idxs


def _compute_sagittal_meta(lab: np.ndarray) -> tuple[list, list]:
    """Compute tumor/liver pixel counts for each sagittal (X) slice."""
    n = lab.shape[0]
    meta, tumor_idxs = [], []
    for x in range(n):
        sl = lab[x, :, :]
        tp = int((sl == 2).sum())
        lp = int((sl >= 1).sum())
        meta.append({"slice_index": x, "tumor_pixels": tp,
                     "liver_pixels": lp, "has_tumor": tp > 0})
        if tp > 0:
            tumor_idxs.append(x)
    return meta, tumor_idxs


# ─────────────────────────────────────────────────────────────────
#  Volume cache
# ─────────────────────────────────────────────────────────────────
_vol_cache: dict[str, tuple[np.ndarray, np.ndarray]] = {}


def _get_volumes(session_id: str) -> tuple[np.ndarray, np.ndarray]:
    if session_id in _vol_cache:
        return _vol_cache[session_id]
    sess = session_store.get(session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found.")

    ct_img  = nib.load(sess["ct_path"])
    lab_img = nib.load(sess["pred_path"])

    # ── Shape must match (CT and prediction must come from same volume)
    if ct_img.shape != lab_img.shape:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Shape mismatch: CT={ct_img.shape} vs pred={lab_img.shape}. "
                "Ensure nnU-Net prediction was run on the same image."
            ),
        )

    # ── Warn if affines diverge (spacing / origin mismatch)
    if not np.allclose(ct_img.affine, lab_img.affine, atol=1e-3):
        logger.warning(
            f"[{session_id}] Affine mismatch between CT and prediction — "
            f"overlay may be misaligned.\n"
            f"  CT affine:   {ct_img.affine.tolist()}\n"
            f"  Pred affine: {lab_img.affine.tolist()}"
        )

    ct  = ct_img.get_fdata(dtype=np.float32)
    lab = lab_img.get_fdata().astype(np.uint8)

    logger.info(
        f"[{session_id}] Volumes loaded — shape={ct.shape}, "
        f"orientation={nib.aff2axcodes(ct_img.affine)}"
    )

    _vol_cache[session_id] = (ct, lab)
    return ct, lab


# ─────────────────────────────────────────────────────────────────
#  HTML builder (axial)
# ─────────────────────────────────────────────────────────────────


def _write_plane_html(
    session_id: str,
    out_path: Path,
    plane: str,          # "axial" | "coronal" | "sagittal"
) -> int:
    """
    Stream a single-plane standalone HTML slider to *out_path*.

    Splitting into three separate files (one per plane) means each file is
    ~3× smaller than the old combined file, so the browser only has to hold
    one plane's images in memory at a time — no OOM crash.

    Returns the final file size in bytes.
    """
    sess = session_store.get(session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    ct, lab     = _get_volumes(session_id)
    volume_name = sess.get("volume_name", session_id)
    tumor_detected = sess.get("tumor_detected", False)
    liver_voxels   = sess.get("liver_voxels", 0)
    tumor_voxels   = sess.get("tumor_voxels", 0)

    # ── Per-plane setup ────────────────────────────────────────────
    if plane == "axial":
        n_slices    = sess["n_slices"]
        slice_meta  = sess["slice_meta"]
        tumor_idxs  = sess["tumor_slice_indices"]
        first_i     = tumor_idxs[0] if tumor_idxs else 0
        render_raw  = lambda i: _render_raw(ct, i)
        render_ov   = lambda i: _render_overlay(ct, lab, i)
        plane_label = "Axial"
        plane_desc  = f"{n_slices} axial slices"
    elif plane == "coronal":
        n_slices    = ct.shape[1]
        slice_meta_raw, tumor_idxs = _compute_coronal_meta(lab)
        slice_meta  = [{"slice_index": m["slice_index"], "tumor_pixels": m["tumor_pixels"],
                        "liver_pixels": m["liver_pixels"], "has_tumor": m["has_tumor"]}
                       for m in slice_meta_raw]
        first_i     = tumor_idxs[0] if tumor_idxs else n_slices // 2
        render_raw  = lambda i: _render_coronal_raw(ct, i)
        render_ov   = lambda i: _render_coronal_overlay(ct, lab, i)
        plane_label = "Coronal"
        plane_desc  = f"{n_slices} coronal slices"
    elif plane == "sagittal":
        n_slices    = ct.shape[0]
        slice_meta_raw, tumor_idxs = _compute_sagittal_meta(lab)
        slice_meta  = [{"slice_index": m["slice_index"], "tumor_pixels": m["tumor_pixels"],
                        "liver_pixels": m["liver_pixels"], "has_tumor": m["has_tumor"]}
                       for m in slice_meta_raw]
        first_i     = tumor_idxs[0] if tumor_idxs else n_slices // 2
        render_raw  = lambda i: _render_sagittal_raw(ct, i)
        render_ov   = lambda i: _render_sagittal_overlay(ct, lab, i)
        plane_label = "Sagittal"
        plane_desc  = f"{n_slices} sagittal slices"
    else:
        raise ValueError(f"Unknown plane: {plane!r}")

    badge_tumor = "<span class='badge badge-t'>Tumour detected</span>" if tumor_detected else ""
    jump_btn    = f"<button class='jump-btn' onclick='jumpTo()'>Jump to tumour</button>" if tumor_idxs else ""
    count_tag   = f"<span class='tab-count'>{len(tumor_idxs)}</span>" if tumor_idxs else ""

    meta_js = str([
        {"z": m["slice_index"], "tp": m["tumor_pixels"],
         "lp": m["liver_pixels"], "ht": m["has_tumor"]}
        for m in slice_meta
    ]).replace("True", "true").replace("False", "false")

    def _b64(data: bytes) -> str:
        return base64.b64encode(data).decode()

    logger.info(f"[{session_id}] Streaming {plane} HTML → {out_path} ({n_slices} slices)...")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>LiverSeg — {volume_name} — {plane_label}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#080b12;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;
      display:flex;flex-direction:column;align-items:center;min-height:100vh;padding:20px 16px;gap:14px}}
h1{{font-size:1.4rem;font-weight:700}}h1 span{{color:#c85a7a}}
.plane-tag{{font-size:.7rem;font-weight:700;padding:2px 10px;border-radius:99px;margin-left:8px;
            background:rgba(200,90,122,.12);border:1px solid rgba(200,90,122,.35);color:#c85a7a;
            vertical-align:middle;letter-spacing:.06em;text-transform:uppercase}}
.meta{{font-size:.75rem;color:#64748b;font-family:monospace;text-align:center}}
.badges{{display:flex;gap:8px;justify-content:center;flex-wrap:wrap}}
.badge{{font-size:.7rem;font-weight:700;padding:3px 10px;border-radius:99px}}
.badge-t{{background:rgba(255,40,40,.15);color:#ff6060;border:1px solid rgba(255,40,40,.3)}}
.badge-l{{background:rgba(50,220,200,.1);color:#32dcc8;border:1px solid rgba(50,220,200,.25)}}
.viewer{{display:flex;flex-direction:column;gap:10px;width:100%;max-width:1060px}}
.toprow{{display:flex;align-items:center;gap:10px;flex-wrap:wrap;min-height:28px}}
.slice-lbl{{font-size:.82rem;color:#94a3b8}}.slice-lbl strong{{color:#e2e8f0}}
.count-tag{{margin-left:6px;font-size:.65em;background:rgba(255,64,64,.2);
            color:#ff6060;border-radius:4px;padding:1px 5px}}
.vbadges{{display:flex;gap:6px;flex:1}}
.vbadge{{font-size:.7rem;font-weight:700;padding:2px 8px;border-radius:99px}}
.vbadge-t{{background:rgba(255,40,40,.15);color:#ff6060;border:1px solid rgba(255,40,40,.3)}}
.vbadge-l{{background:rgba(50,220,200,.1);color:#32dcc8;border:1px solid rgba(50,220,200,.25)}}
.jump-btn{{margin-left:auto;padding:4px 13px;border-radius:7px;
           border:1px solid rgba(200,90,122,.4);background:rgba(200,90,122,.1);
           color:#c85a7a;font-size:.73rem;font-weight:700;cursor:pointer;
           font-family:inherit;transition:all .15s}}
.jump-btn:hover{{background:rgba(200,90,122,.2)}}
.panels{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
.panel{{display:flex;flex-direction:column;gap:5px}}
.plbl{{font-size:.65rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;
       color:#64748b;display:flex;align-items:center;gap:5px}}
.dot{{width:7px;height:7px;border-radius:50%}}
.dot-g{{background:#64748b}}.dot-a{{background:#32dcc8}}
img{{width:100%;border-radius:10px;image-rendering:pixelated;background:#000}}
.slider-row{{display:flex;align-items:center;gap:10px}}
.snum{{font-family:monospace;font-size:.75rem;color:#64748b;min-width:24px;text-align:center}}
input[type=range]{{flex:1;accent-color:#c85a7a;height:4px}}
.chart{{width:100%}}
.chart-lbl{{font-size:.7rem;color:#64748b;margin-bottom:4px}}
.bars{{display:flex;align-items:flex-end;height:44px;gap:1px}}
.bar{{flex:1;border-radius:2px 2px 0 0;cursor:pointer;min-height:2px}}
.bar-t{{background:rgba(255,64,64,.7)}}.bar-e{{background:rgba(255,255,255,.06)}}
.bar.active-bar{{outline:1px solid #c85a7a}}
.stats{{display:flex;gap:20px;flex-wrap:wrap}}
.stat{{font-size:.78rem;color:#94a3b8;display:flex;align-items:center;gap:6px}}
.sdot{{width:8px;height:8px;border-radius:50%}}
.chips{{display:flex;gap:10px;flex-wrap:wrap;justify-content:center;width:100%;max-width:1060px}}
.chip{{display:flex;align-items:center;gap:7px;background:#0f1219;
       border:1px solid rgba(255,255,255,.07);border-radius:10px;padding:10px 16px}}
.chip-dot{{width:8px;height:8px;border-radius:50%;flex-shrink:0}}
.chip-val{{font-size:1.1rem;font-weight:700;color:#e2e8f0}}
.chip-lbl{{font-size:.72rem;color:#64748b}}
footer{{font-size:.7rem;color:#334155;text-align:center;margin-top:4px}}
@media(max-width:600px){{.panels{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<h1>Liver<span>Seg</span><span class="plane-tag">{plane_label}</span></h1>
<p class="meta">{volume_name} &nbsp;&middot;&nbsp; {plane_desc}</p>
<div class="badges">
  <span class="badge badge-l">Liver detected</span>
  {badge_tumor}
</div>
<div class="viewer">
  <div class="toprow">
    <span class="slice-lbl">
      Slice <strong id="lbl">{first_i}</strong> / {n_slices-1}
      {count_tag}
    </span>
    <div class="vbadges" id="vbadges"></div>
    {jump_btn}
  </div>
  <div class="panels">
    <div class="panel">
      <div class="plbl"><span class="dot dot-g"></span>CT Raw</div>
      <img id="raw-img"/>
    </div>
    <div class="panel">
      <div class="plbl"><span class="dot dot-a"></span>Segmentation Overlay</div>
      <img id="ov-img"/>
    </div>
  </div>
  <div class="slider-row">
    <span class="snum">0</span>
    <input type="range" id="slider" min="0" max="{n_slices-1}" value="{first_i}" oninput="goTo(+this.value)"/>
    <span class="snum">{n_slices-1}</span>
  </div>
  <div class="chart">
    <div class="chart-lbl">Tumour pixels per slice</div>
    <div class="bars" id="bars"></div>
  </div>
  <div class="stats">
    <span class="stat"><span class="sdot" style="background:#32dcc8"></span>Liver: <span id="lp">0</span> px</span>
    <span class="stat"><span class="sdot" style="background:#ff4040"></span>Tumour: <span id="tp">0</span> px</span>
    <span class="stat" style="color:#475569">&#x2190; &#x2192; to navigate</span>
  </div>
</div>
<div class="chips">
  <div class="chip"><span class="chip-dot" style="background:#32dcc8"></span>
    <span class="chip-val">{liver_voxels:,}</span><span class="chip-lbl">Liver voxels</span></div>
  <div class="chip"><span class="chip-dot" style="background:#ff4040"></span>
    <span class="chip-val">{tumor_voxels:,}</span><span class="chip-lbl">Tumour voxels</span></div>
  <div class="chip"><span class="chip-dot" style="background:#f59e0b"></span>
    <span class="chip-val">{len(tumor_idxs)}</span><span class="chip-lbl">Tumour slices</span></div>
  <div class="chip"><span class="chip-dot" style="background:#94a3b8"></span>
    <span class="chip-val">{n_slices}</span><span class="chip-lbl">Total slices</span></div>
</div>
<footer>For research use only &mdash; not a certified medical device &nbsp;&middot;&nbsp; LiverSeg</footer>
<script>
const META={meta_js};
let cur={first_i};
""")

        # ── Stream raw image array ─────────────────────────────────
        f.write('const RAW=[')
        for i in range(n_slices):
            if i: f.write(',')
            f.write(f'"{_b64(render_raw(i))}"')
        f.write('];\n')

        # ── Stream overlay image array ─────────────────────────────
        f.write('const OV=[')
        for i in range(n_slices):
            if i: f.write(',')
            f.write(f'"{_b64(render_ov(i))}"')
        f.write('];\n')

        # ── JS logic ───────────────────────────────────────────────
        f.write(f"""
const TUMORS={str(tumor_idxs)};
function goTo(i){{
  if(i<0||i>=RAW.length)return;
  cur=i;
  document.getElementById('raw-img').src='data:image/png;base64,'+RAW[i];
  document.getElementById('ov-img').src='data:image/png;base64,'+OV[i];
  document.getElementById('slider').value=i;
  document.getElementById('lbl').textContent=i;
  const m=META[i]||{{}};
  document.getElementById('lp').textContent=(m.lp||0).toLocaleString();
  document.getElementById('tp').textContent=(m.tp||0).toLocaleString();
  const vb=document.getElementById('vbadges');
  vb.innerHTML='';
  if(m.ht) vb.innerHTML+="<span class='vbadge vbadge-t'>Tumour</span>";
  if(m.lp>0) vb.innerHTML+="<span class='vbadge vbadge-l'>Liver</span>";
  document.querySelectorAll('#bars .bar').forEach((b,j)=>b.classList.toggle('active-bar',j===i));
}}
function jumpTo(){{
  if(!TUMORS.length)return;
  const densest=TUMORS.reduce((best,z)=>{{
    return((META[z]||{{}}).tp||0)>((META[best]||{{}}).tp||0)?z:best;
  }},TUMORS[0]);
  goTo(densest);
}}
function buildBars(){{
  const el=document.getElementById('bars');
  const maxTp=Math.max(...META.map(m=>m.tp||0),1);
  META.forEach((m,i)=>{{
    const b=document.createElement('div');
    b.className='bar '+(m.ht?'bar-t':'bar-e')+(i==={first_i}?' active-bar':'');
    b.style.height=Math.max(Math.round(((m.tp||0)/maxTp)*100),m.ht?6:2)+'%';
    b.onclick=()=>goTo(i);
    b.title='Slice '+i+': '+(m.tp||0)+' tumour px';
    el.appendChild(b);
  }});
}}
document.addEventListener('keydown',e=>{{
  if(e.key==='ArrowRight'||e.key==='ArrowDown')goTo(Math.min(cur+1,RAW.length-1));
  if(e.key==='ArrowLeft'||e.key==='ArrowUp')goTo(Math.max(cur-1,0));
}});
buildBars();
goTo({first_i});
</script>
</body></html>""")

    file_size = out_path.stat().st_size
    logger.info(
        f"[{session_id}] {plane_label} HTML written → {out_path} "
        f"({file_size // (1024*1024)} MB)"
    )
    return file_size


# ─────────────────────────────────────────────────────────────────
#  App lifecycle
# ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    TEMP_INPUT.mkdir(parents=True, exist_ok=True)
    TEMP_OUTPUT.mkdir(parents=True, exist_ok=True)
    session_store.init()
    base = Path(NNUNET_RESULTS) / DATASET_NAME / f"{TRAINER}__nnUNetPlans__2d"
    missing = [f for f in ENSEMBLE_FOLDS
               if not (base / f"fold_{f}" / CHECKPOINT).exists()]
    if missing: logger.warning(f"Missing checkpoints: {missing}")
    else: logger.info(f"All {len(ENSEMBLE_FOLDS)} checkpoints verified.")
    yield
    session_store.cleanup_expired()
    _vol_cache.clear()


app = FastAPI(title="Liver Tumour Segmentation API", version="3.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS,
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    t = time.perf_counter()
    r = await call_next(request)
    r.headers["X-Process-Time"] = f"{time.perf_counter()-t:.3f}s"
    return r


def _validate_upload(file: UploadFile) -> None:
    name = file.filename or ""
    if not (name.endswith(".nii.gz") or name.endswith(".nii")):
        raise HTTPException(status_code=400, detail="Only .nii or .nii.gz accepted.")


def _check_size(path: str) -> None:
    mb = os.path.getsize(path) / 1_048_576
    if mb > MAX_UPLOAD_MB:
        raise HTTPException(status_code=413, detail=f"File {mb:.1f} MB exceeds limit.")


# ─────────────────────────────────────────────────────────────────
#  Endpoints
# ─────────────────────────────────────────────────────────────────

@app.get("/health", tags=["system"])
async def health(): return {"status": "ok"}


@app.get("/model/info", tags=["system"])
async def model_info() -> Dict[str, Any]:
    base = Path(NNUNET_RESULTS) / DATASET_NAME / f"{TRAINER}__nnUNetPlans__2d"
    return {
        "framework": "nnUNetv2", "config": "2d",
        "dataset_id": DATASET_ID, "dataset_name": DATASET_NAME,
        "trainer": TRAINER, "ensemble_folds": ENSEMBLE_FOLDS,
        "checkpoint": CHECKPOINT, "nnunet_base": NNUNET_BASE,
        "fold_status": {
            f"fold_{f}": "ready" if (base / f"fold_{f}" / CHECKPOINT).exists() else "MISSING"
            for f in ENSEMBLE_FOLDS
        },
    }


@app.post("/predict", tags=["segmentation"])
async def predict(file: UploadFile = File(...)) -> JSONResponse:
    from inference import run_inference
    session_id  = str(uuid.uuid4())[:8]
    filename    = file.filename or "unknown.nii.gz"
    logger.info(f"[{session_id}] Received: {filename}")
    _validate_upload(file)

    stem = filename
    for ext in (".nii.gz", ".nii"):
        if stem.endswith(ext): stem = stem[:-len(ext)]
    if stem.endswith("_0000"): stem = stem[:-5]
    volume_name = stem

    suffix   = ".nii.gz" if filename.endswith(".nii.gz") else ".nii"
    tmp_dir  = Path(tempfile.mkdtemp(prefix="liver_upload_"))
    tmp_path = tmp_dir / f"{session_id}{suffix}"

    try:
        with open(tmp_path, "wb") as buf:
            shutil.copyfileobj(file.file, buf)
        _check_size(str(tmp_path))

        t0     = time.perf_counter()
        loop   = asyncio.get_event_loop()
        masks  = await loop.run_in_executor(
            None, partial(run_inference, str(tmp_path), session_id, volume_name=volume_name)
        )
        elapsed = round(time.perf_counter() - t0, 3)

        logger.info(f"[{session_id}] Done in {elapsed}s")
        return JSONResponse(content={
            "session_id":          session_id,
            "request_id":          session_id,
            "volume_name":         volume_name,
            "processing_time_s":   elapsed,
            "tumor_detected":      masks["tumor_detected"],
            "liver_voxels":        masks["liver_voxels"],
            "tumor_voxels":        masks["tumor_voxels"],
            "n_slices":            masks["n_slices"],
            "tumor_slice_indices": masks["tumor_slice_indices"],
            "slice_meta":          masks["slice_meta"],
        })

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"[{session_id}] Error: {exc}")
        raise HTTPException(status_code=500, detail=f"Segmentation failed: {str(exc)}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@app.get("/session-meta/{session_id}", tags=["viewer"])
async def get_session_meta(session_id: str) -> JSONResponse:
    """
    Returns real volume dimensions and per-plane tumor metadata for
    coronal and sagittal views. Called by the frontend after /predict.
    """
    sess = session_store.get(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found.")

    loop = asyncio.get_event_loop()

    def _compute():
        ct, lab = _get_volumes(session_id)
        cor_meta, cor_tumor = _compute_coronal_meta(lab)
        sag_meta, sag_tumor = _compute_sagittal_meta(lab)
        return {
            "coronal_n":             ct.shape[1],
            "sagittal_n":            ct.shape[0],
            "coronal_slice_meta":    cor_meta,
            "coronal_tumor_indices": cor_tumor,
            "sagittal_slice_meta":   sag_meta,
            "sagittal_tumor_indices": sag_tumor,
        }

    data = await loop.run_in_executor(None, _compute)
    return JSONResponse(content=data)


@app.get("/slice/{session_id}/{z}", tags=["viewer"])
async def get_slice_overlay(session_id: str, z: int) -> Response:
    sess = session_store.get(session_id)
    if not sess: raise HTTPException(status_code=404, detail="Session not found.")
    if z < 0 or z >= sess["n_slices"]:
        raise HTTPException(status_code=400, detail=f"Slice {z} out of range.")
    ct, lab = _get_volumes(session_id)
    return Response(content=_render_overlay(ct, lab, z), media_type="image/png",
                    headers={"Cache-Control": "public, max-age=3600"})


@app.get("/slice-raw/{session_id}/{z}", tags=["viewer"])
async def get_slice_raw(session_id: str, z: int) -> Response:
    sess = session_store.get(session_id)
    if not sess: raise HTTPException(status_code=404, detail="Session not found.")
    if z < 0 or z >= sess["n_slices"]:
        raise HTTPException(status_code=400, detail=f"Slice {z} out of range.")
    ct, _ = _get_volumes(session_id)
    return Response(content=_render_raw(ct, z), media_type="image/png",
                    headers={"Cache-Control": "public, max-age=3600"})


@app.get("/slice-coronal/{session_id}/{y}", tags=["viewer"])
async def get_slice_coronal(session_id: str, y: int) -> Response:
    sess = session_store.get(session_id)
    if not sess: raise HTTPException(status_code=404, detail="Session not found.")
    ct, lab = _get_volumes(session_id)
    # Return blank PNG for out-of-range instead of 400 — frontend hardcodes PLANE_SIZE=512
    if y < 0 or y >= ct.shape[1]:
        return Response(content=_BLANK_PNG_BYTES, media_type="image/png",
                        headers={"Cache-Control": "public, max-age=3600"})
    return Response(content=_render_coronal_overlay(ct, lab, y), media_type="image/png",
                    headers={"Cache-Control": "public, max-age=3600"})


@app.get("/slice-coronal-raw/{session_id}/{y}", tags=["viewer"])
async def get_slice_coronal_raw(session_id: str, y: int) -> Response:
    sess = session_store.get(session_id)
    if not sess: raise HTTPException(status_code=404, detail="Session not found.")
    ct, _ = _get_volumes(session_id)
    if y < 0 or y >= ct.shape[1]:
        return Response(content=_BLANK_PNG_BYTES, media_type="image/png",
                        headers={"Cache-Control": "public, max-age=3600"})
    return Response(content=_render_coronal_raw(ct, y), media_type="image/png",
                    headers={"Cache-Control": "public, max-age=3600"})


@app.get("/slice-sagittal/{session_id}/{x}", tags=["viewer"])
async def get_slice_sagittal(session_id: str, x: int) -> Response:
    sess = session_store.get(session_id)
    if not sess: raise HTTPException(status_code=404, detail="Session not found.")
    ct, lab = _get_volumes(session_id)
    if x < 0 or x >= ct.shape[0]:
        return Response(content=_BLANK_PNG_BYTES, media_type="image/png",
                        headers={"Cache-Control": "public, max-age=3600"})
    return Response(content=_render_sagittal_overlay(ct, lab, x), media_type="image/png",
                    headers={"Cache-Control": "public, max-age=3600"})


@app.get("/slice-sagittal-raw/{session_id}/{x}", tags=["viewer"])
async def get_slice_sagittal_raw(session_id: str, x: int) -> Response:
    sess = session_store.get(session_id)
    if not sess: raise HTTPException(status_code=404, detail="Session not found.")
    ct, _ = _get_volumes(session_id)
    if x < 0 or x >= ct.shape[0]:
        return Response(content=_BLANK_PNG_BYTES, media_type="image/png",
                        headers={"Cache-Control": "public, max-age=3600"})
    return Response(content=_render_sagittal_raw(ct, x), media_type="image/png",
                    headers={"Cache-Control": "public, max-age=3600"})


@app.get("/save-results/{session_id}", tags=["viewer"])
async def save_results(session_id: str) -> JSONResponse:
    """
    Opens a native Save dialog asking for a *folder* (via directory chooser).
    Writes into that folder:
      {volume_name}_axial.html      — standalone axial slider
      {volume_name}_coronal.html    — standalone coronal slider
      {volume_name}_sagittal.html   — standalone sagittal slider
      {volume_name}_results.json    — full session metadata
      ct.nii.gz                     — original CT volume
      pred.nii.gz                   — segmentation mask

    Each HTML file contains only one plane's images so the browser loads
    ~3× less data at a time — no OOM crash on large volumes.
    """
    sess = session_store.get(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found.")

    volume_name = sess.get("volume_name", session_id)
    result: dict = {}

    logger.info(f"[{session_id}] Opening save dialog for {volume_name}...")

    def _save():
        try:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.lift()
            root.attributes("-topmost", True)
            save_dir = filedialog.askdirectory(
                title=f"Choose folder to save results — {volume_name}",
            )
            root.destroy()

            if not save_dir:
                result["status"] = "cancelled"
                return

            out = Path(save_dir)
            s   = session_store.get(session_id)

            # ── Axial HTML viewer only ─────────────────────────────
            html_path = out / f"{volume_name}_viewer.html"
            logger.info(f"[{session_id}] Writing axial viewer → {html_path}")
            html_size = _write_plane_html(session_id, html_path, "axial")

            # ── JSON results ───────────────────────────────────────
            json_path = out / f"{volume_name}_results.json"
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump({
                    "session_id":          session_id,
                    "volume_name":         volume_name,
                    "n_slices":            s.get("n_slices"),
                    "tumor_detected":      s.get("tumor_detected"),
                    "liver_voxels":        s.get("liver_voxels"),
                    "tumor_voxels":        s.get("tumor_voxels"),
                    "tumor_slice_indices": s.get("tumor_slice_indices", []),
                    "slice_meta":          s.get("slice_meta", []),
                    "ct_path":             str(out / "ct.nii.gz"),
                    "pred_path":           str(out / "pred.nii.gz"),
                }, f, indent=2)

            # ── NIfTI files ────────────────────────────────────────
            shutil.copy2(s["ct_path"],   out / "ct.nii.gz")
            shutil.copy2(s["pred_path"], out / "pred.nii.gz")

            result["status"]   = "saved"
            result["folder"]   = str(out)
            result["files"] = {
                "viewer_html": str(html_path),
                "json":        str(json_path),
                "ct_nii":      str(out / "ct.nii.gz"),
                "pred_nii":    str(out / "pred.nii.gz"),
            }
            result["size_mb"]  = round(html_size / 1e6, 1)
            logger.info(
                f"[{session_id}] Saved to {out} — "
                f"viewer={html_size//1_000_000:.0f}MB"
            )

        except Exception as e:
            logger.exception(f"[{session_id}] Save error: {e}")
            result["status"] = "error"
            result["detail"] = str(e)

    t = threading.Thread(target=_save)
    t.start()
    t.join(timeout=900)   # allow up to 15 min for very large volumes

    if not result:
        raise HTTPException(status_code=408, detail="Save dialog timed out.")
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("detail"))
    return JSONResponse(content=result)


@app.post("/demo/upload")
async def demo_upload(file: UploadFile = File(...)):
    filename = file.filename.lower().strip()
    case = filename.replace(".nii.gz", "").replace(".nii", "").replace("_0000", "")

    json_path = DEMO_RESULTS / f"{case}_results.json"
    if not json_path.exists():
        available = [p.stem.removesuffix("_results") for p in DEMO_RESULTS.glob("*_results.json")]
        raise HTTPException(status_code=404, detail=f"Demo not found for '{case}'. Available: {available}")

    with open(json_path, "r") as f:
        data = json.load(f)

    # Resolve NIfTI paths — check json metadata first, then all standard locations
    ct_path = next((c for c in [
        data.get("ct_path"),
        str(DEMO_RESULTS / case / "ct.nii.gz"),   # subfolder layout
        str(DEMO_RESULTS / "ct.nii.gz"),           # flat layout (same folder as JSON)
        str(DEMO_RESULTS / f"{case}_ct.nii.gz"),
    ] if c and Path(c).exists()), None)

    pred_path = next((c for c in [
        data.get("pred_path"),
        str(DEMO_RESULTS / case / "pred.nii.gz"),  # subfolder layout
        str(DEMO_RESULTS / "pred.nii.gz"),          # flat layout
        str(DEMO_RESULTS / f"{case}_pred.nii.gz"),
    ] if c and Path(c).exists()), None)

    if not ct_path or not pred_path:
        raise HTTPException(status_code=404,
            detail=f"NIfTI files not found for '{case}'. Place ct.nii.gz + pred.nii.gz in resultsTs/ or resultsTs/{case}/")

    # Register a live session under the case name so /demo/viewer can serve
    # slices lazily via /slice/{case}/{z} — no need to re-run inference.
    if session_store.get(case) is None:
        session_store.save(case, {
            "ct_path":             ct_path,
            "pred_path":           pred_path,
            "n_slices":            data["n_slices"],
            "tumor_slice_indices": data.get("tumor_slice_indices", []),
            "slice_meta":          data.get("slice_meta", []),
            "tumor_detected":      data.get("tumor_detected", False),
            "tumor_voxels":        data.get("tumor_voxels", 0),
            "liver_voxels":        data.get("liver_voxels", 0),
            "volume_name":         data.get("volume_name", case),
        })
        logger.info(f"[demo] Registered live session for '{case}'")

    data["session_id"] = case
    return data


@app.get("/demo/viewer/{case}")
async def demo_viewer(case: str):
    """
    Serve a lightweight lazy-loading axial-only viewer for demo cases.
    Fetches slices on demand from the API — no coronal/sagittal tabs.
    Falls back to the static file only if no live session exists for the case.
    """
    # Prefer live session — gives us the lazy-slice API endpoints
    sess = session_store.get(case)
    if sess:
        n_ax  = sess["n_slices"]
        tumor_ax   = sess.get("tumor_slice_indices", [])
        first_ax   = tumor_ax[0] if tumor_ax else 0
        tumor_detected = sess.get("tumor_detected", False)
        liver_voxels   = sess.get("liver_voxels", 0)
        tumor_voxels   = sess.get("tumor_voxels", 0)
        volume_name    = sess.get("volume_name", case)

        badge_tumor = "<span class='badge badge-t'>Tumour detected</span>" if tumor_detected else ""
        jump_btn    = "<button class='jump-btn' onclick='jumpToTumour()'>Jump to tumour</button>" if tumor_ax else ""
        ax_count    = f"<span class='tab-count'>{len(tumor_ax)}</span>" if tumor_ax else ""

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>LiverSeg \u2014 {volume_name}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#080b12;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;
      display:flex;flex-direction:column;align-items:center;min-height:100vh;padding:20px 16px;gap:14px}}
h1{{font-size:1.4rem;font-weight:700}}h1 span{{color:#c85a7a}}
.meta{{font-size:.75rem;color:#64748b;font-family:monospace;text-align:center}}
.badges{{display:flex;gap:8px;justify-content:center;flex-wrap:wrap}}
.badge{{font-size:.7rem;font-weight:700;padding:3px 10px;border-radius:99px}}
.badge-t{{background:rgba(255,40,40,.15);color:#ff6060;border:1px solid rgba(255,40,40,.3)}}
.badge-l{{background:rgba(50,220,200,.1);color:#32dcc8;border:1px solid rgba(50,220,200,.25)}}
.viewer{{display:flex;flex-direction:column;gap:10px;width:100%;max-width:1060px}}
.toprow{{display:flex;align-items:center;gap:10px;flex-wrap:wrap;min-height:28px}}
.slice-lbl{{font-size:.82rem;color:#94a3b8}}.slice-lbl strong{{color:#e2e8f0}}
.jump-btn{{margin-left:auto;padding:4px 13px;border-radius:7px;border:1px solid rgba(200,90,122,.4);
           background:rgba(200,90,122,.1);color:#c85a7a;font-size:.73rem;font-weight:700;
           cursor:pointer;font-family:inherit;transition:all .15s}}
.panels{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
.panel{{display:flex;flex-direction:column;gap:5px}}
.plbl{{font-size:.65rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;
       color:#64748b;display:flex;align-items:center;gap:5px}}
.dot{{width:7px;height:7px;border-radius:50%}}
.dot-g{{background:#64748b}}.dot-a{{background:#32dcc8}}
img{{width:100%;border-radius:10px;image-rendering:pixelated;background:#111;min-height:200px}}
.slider-row{{display:flex;align-items:center;gap:10px}}
.snum{{font-family:monospace;font-size:.75rem;color:#64748b;min-width:32px;text-align:center}}
input[type=range]{{flex:1;accent-color:#c85a7a;height:4px}}
.chart{{width:100%}}
.chart-lbl{{font-size:.7rem;color:#64748b;margin-bottom:4px}}
.bars{{display:flex;align-items:flex-end;height:44px;gap:1px}}
.bar{{flex:1;border-radius:2px 2px 0 0;cursor:pointer;min-height:2px}}
.bar-t{{background:rgba(255,64,64,.7)}}.bar-e{{background:rgba(255,255,255,.06)}}
.bar.active-bar{{outline:1px solid #c85a7a}}
.stats{{display:flex;gap:20px;flex-wrap:wrap}}
.stat{{font-size:.78rem;color:#94a3b8;display:flex;align-items:center;gap:6px}}
.sdot{{width:8px;height:8px;border-radius:50%}}
.chips{{display:flex;gap:10px;flex-wrap:wrap;justify-content:center;width:100%;max-width:1060px}}
.chip{{display:flex;align-items:center;gap:7px;background:#0f1219;border:1px solid rgba(255,255,255,.07);border-radius:10px;padding:10px 16px}}
.chip-dot{{width:8px;height:8px;border-radius:50%;flex-shrink:0}}
.chip-val{{font-size:1.1rem;font-weight:700;color:#e2e8f0}}
.chip-lbl{{font-size:.72rem;color:#64748b}}
footer{{font-size:.7rem;color:#334155;text-align:center;margin-top:4px}}
@media(max-width:600px){{.panels{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<h1>Liver<span>Seg</span></h1>
<p class="meta">{volume_name} &nbsp;&middot;&nbsp; {n_ax} axial slices</p>
<div class="badges">
  <span class="badge badge-l">Liver detected</span>
  {badge_tumor}
</div>

<div class="viewer">
  <div class="toprow">
    <span class="slice-lbl">Slice <strong id="lbl">{first_ax}</strong> / <span id="max">{n_ax-1}</span></span>
    {jump_btn}
  </div>
  <div class="panels">
    <div class="panel"><div class="plbl"><span class="dot dot-g"></span>CT Raw</div><img id="raw" alt="CT"/></div>
    <div class="panel"><div class="plbl"><span class="dot dot-a"></span>Segmentation Overlay</div><img id="ov" alt="Overlay"/></div>
  </div>
  <div class="slider-row">
    <span class="snum">0</span>
    <input type="range" id="sl" min="0" max="{n_ax-1}" value="{first_ax}" oninput="goTo(+this.value, true)"/>
    <span class="snum">{n_ax-1}</span>
  </div>
  <div class="chart"><div class="chart-lbl">Tumour pixels per slice</div><div class="bars" id="bars"></div></div>
  <div class="stats">
    <span class="stat"><span class="sdot" style="background:#32dcc8"></span>Liver: <span id="lp">—</span> px</span>
    <span class="stat"><span class="sdot" style="background:#ff4040"></span>Tumour: <span id="tp">—</span> px</span>
  </div>
</div>

<div class="chips">
  <div class="chip"><span class="chip-dot" style="background:#32dcc8"></span>
    <span class="chip-val">{liver_voxels:,}</span><span class="chip-lbl">Liver voxels</span></div>
  <div class="chip"><span class="chip-dot" style="background:#ff4040"></span>
    <span class="chip-val">{tumor_voxels:,}</span><span class="chip-lbl">Tumour voxels</span></div>
  <div class="chip"><span class="chip-dot" style="background:#f59e0b"></span>
    <span class="chip-val">{len(tumor_ax)}</span><span class="chip-lbl">Tumour slices</span></div>
  <div class="chip"><span class="chip-dot" style="background:#94a3b8"></span>
    <span class="chip-val">{n_ax}</span><span class="chip-lbl">Total slices</span></div>
</div>
<footer>For research use only &mdash; not a certified medical device &nbsp;&middot;&nbsp; LiverSeg</footer>

<script>
const SESSION  = "{case}";
const TUMOR_AX = {str(tumor_ax).replace("True","true").replace("False","false")};
const AX_META  = {{}};

const sliceMeta = {str(sess.get("slice_meta", [])).replace("True","true").replace("False","false")};
sliceMeta.forEach(m => AX_META[m.slice_index] = m);

// ── LOD parameters ────────────────────────────────────────────────
const MAX_CACHED   = 120;
const PREFETCH_WIN = 8;
const LOD_THRESH   = 300;

function dragStride(n) {{
  if (n <= LOD_THRESH) return 1;
  if (n <= 600)        return 2;
  if (n <= 1000)       return 4;
  return 6;
}}

function snap(i, stride) {{
  return Math.round(i / stride) * stride;
}}

// ── State ─────────────────────────────────────────────────────────
let cur      = {first_ax};
let limit    = {n_ax-1};
let dragging = false;

// ── LRU image cache ───────────────────────────────────────────────
const cache    = {{ raw: {{}}, ov: {{}} }};
const lruOrder = [];

function evictIfNeeded() {{
  while (lruOrder.length > MAX_CACHED) {{
    const evict = lruOrder.shift();
    delete cache.raw[evict];
    delete cache.ov[evict];
  }}
}}

function touchLRU(idx) {{
  const pos = lruOrder.indexOf(idx);
  if (pos !== -1) lruOrder.splice(pos, 1);
  lruOrder.push(idx);
}}

// ── URL builders ──────────────────────────────────────────────────
const RAW_URL = z => `/slice-raw/${{SESSION}}/${{z}}`;
const OV_URL  = z => `/slice/${{SESSION}}/${{z}}`;

// ── Fetch a single slice into cache (no-op if already cached) ─────
function fetchSlice(idx, priority) {{
  if (idx < 0 || idx > limit) return;
  if (cache.raw[idx]) {{ touchLRU(idx); return; }}

  const rawImg = new Image();
  const ovImg  = new Image();
  let   loaded = 0;

  const onLoad = () => {{
    if (++loaded < 2) return;
    cache.raw[idx] = rawImg;
    cache.ov[idx]  = ovImg;
    touchLRU(idx);
    evictIfNeeded();
    if (cur === idx || (priority && Math.abs(cur - idx) <= 1)) {{
      paintDisplay(idx);
    }}
  }};
  rawImg.onload = onLoad;
  ovImg.onload  = onLoad;
  rawImg.src = RAW_URL(idx);
  ovImg.src  = OV_URL(idx);
}}

// ── Paint cached images onto the visible <img> elements ──────────
function paintDisplay(idx) {{
  let display = -1;
  for (let d = 0; d <= 8; d++) {{
    if (cache.raw[idx - d]) {{ display = idx - d; break; }}
    if (cache.raw[idx + d]) {{ display = idx + d; break; }}
  }}
  if (display === -1) return;
  document.getElementById('raw').src = cache.raw[display].src;
  document.getElementById('ov').src  = cache.ov[display].src;
}}

// ── Prefetch window ────────────────────────────────────────────────
let prefetchTimer = null;
function schedulePrefetch(centre) {{
  clearTimeout(prefetchTimer);
  prefetchTimer = setTimeout(() => {{
    for (let d = 0; d <= PREFETCH_WIN; d++) {{
      fetchSlice(centre + d, false);
      fetchSlice(centre - d, false);
    }}
  }}, 80);
}}

// ── Main goTo ─────────────────────────────────────────────────────
function goTo(i, fromDrag) {{
  i = Math.max(0, Math.min(i, limit));
  const stride  = (fromDrag && dragging) ? dragStride(limit + 1) : 1;
  const snapped = snap(i, stride);

  cur = i;
  document.getElementById('sl').value        = i;
  document.getElementById('lbl').textContent = i;

  fetchSlice(snapped, true);
  paintDisplay(snapped);
  if (stride > 1) fetchSlice(i, true);
  schedulePrefetch(i);

  const m = AX_META[i] || {{}};
  document.getElementById('lp').textContent = (m.liver_pixels||0).toLocaleString();
  document.getElementById('tp').textContent = (m.tumor_pixels||0).toLocaleString();
  const bars = document.querySelectorAll('#bars .bar');
  bars.forEach((b, j) => b.classList.toggle('active-bar', j === i));
}}

// ── Drag tracking ─────────────────────────────────────────────────
const sl = document.getElementById('sl');
sl.addEventListener('pointerdown', () => {{ dragging = true; }});
sl.addEventListener('pointerup',   () => {{ dragging = false; goTo(cur, false); }});
sl.addEventListener('input', () => goTo(+sl.value, true));

// ── Jump to densest tumour slice ──────────────────────────────────
function jumpToTumour() {{
  if (!TUMOR_AX.length) return;
  const densest = TUMOR_AX.reduce((best, z) => {{
    const tp = (AX_META[z]||{{}}).tumor_pixels || 0;
    const bt = (AX_META[best]||{{}}).tumor_pixels || 0;
    return tp > bt ? z : best;
  }}, TUMOR_AX[0]);
  goTo(densest, false);
}}

// ── Tumour bar chart ──────────────────────────────────────────────
function buildBars() {{
  const el = document.getElementById('bars');
  el.innerHTML = '';
  const maxTp = Math.max(...sliceMeta.map(m => m.tumor_pixels||0), 1);
  sliceMeta.forEach(m => {{
    const b  = document.createElement('div');
    const tp = m.tumor_pixels || 0;
    b.className = 'bar ' + (m.has_tumor ? 'bar-t' : 'bar-e');
    b.style.height = Math.max(Math.round((tp/maxTp)*100), m.has_tumor ? 6 : 2) + '%';
    b.onclick = () => goTo(m.slice_index, false);
    b.title   = 'Slice ' + m.slice_index + ': ' + tp + ' tumour px';
    el.appendChild(b);
  }});
}}

// ── Keyboard navigation ───────────────────────────────────────────
document.addEventListener('keydown', e => {{
  if (e.key==='ArrowRight'||e.key==='ArrowDown') goTo(Math.min(cur+1, limit), false);
  if (e.key==='ArrowLeft' ||e.key==='ArrowUp')   goTo(Math.max(cur-1, 0),     false);
}});

// ── Init ──────────────────────────────────────────────────────────
buildBars();
goTo({first_ax}, false);
</script>
</body>
</html>"""
        return Response(content=html, media_type="text/html")

    # No live session — fall back to the pre-baked static file if it exists.
    # This is a last resort; the static files are huge and may crash old browsers.
    for suffix in ["_viewer.html", "_slider.html"]:
        p = DEMO_RESULTS / f"{case}{suffix}"
        if p.exists():
            logger.warning(
                f"[demo] Serving static HTML for '{case}' — no live session found. "
                "Browser may run out of memory on large volumes."
            )
            return FileResponse(p, media_type="text/html")
    raise HTTPException(status_code=404, detail=f"Viewer not found for '{case}'")


@app.get("/demo/result/{case}")
async def demo_result(case: str):
    json_path = DEMO_RESULTS / f"{case}_results.json"
    if not json_path.exists():
        raise HTTPException(404, "Result not found")
    return FileResponse(json_path, media_type="application/json")

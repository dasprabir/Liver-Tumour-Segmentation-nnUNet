"""
save_demo.py
------------
Saves a complete demo snapshot of the current session into:
    live_results/{volume_name}/
        session.json        — metadata to restore the result view
        ct.nii.gz           — original CT volume
        pred.nii.gz         — segmentation mask
        {volume_name}_viewer.html  — standalone combined 3-plane HTML viewer

The session.json restores the session so /slice and /slice-raw endpoints
work for live re-serving. The _viewer.html is a fully self-contained
export (no backend needed) matching the Save Results export format.

Usage (called from main.py):
    from save_demo import save_demo_snapshot
    save_demo_snapshot(session_id, session_data, live_results_dir)
"""

import json
import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


def save_demo_snapshot(
    session_id: str,
    session_data: dict,
    live_results_dir: Path,
    write_combined_html_fn=None,
) -> Path:
    """
    Copy ct.nii.gz + pred.nii.gz, write session.json, and optionally
    write a standalone _viewer.html into live_results/{volume_name}/.

    Parameters
    ----------
    session_id             : the live session ID
    session_data           : the session dict from session_store.get()
    live_results_dir       : Path to the live_results/ folder
    write_combined_html_fn : callable(session_id, out_path: Path) -> int
                             Pass _write_combined_html from main.py.
                             Streams HTML directly to out_path — no RAM spike.
                             If None, the HTML file is skipped.

    Returns
    -------
    Path to the case folder that was written
    """
    volume_name = session_data.get("volume_name") or session_id
    case_dir = live_results_dir / volume_name
    case_dir.mkdir(parents=True, exist_ok=True)

    # ── NIfTI copies ──────────────────────────────────────────────
    ct_src   = Path(session_data["ct_path"])
    pred_src = Path(session_data["pred_path"])
    ct_dest   = case_dir / "ct.nii.gz"
    pred_dest = case_dir / "pred.nii.gz"
    shutil.copy2(ct_src,   ct_dest)
    shutil.copy2(pred_src, pred_dest)

    # ── session.json (used by live re-serve endpoints) ────────────
    snapshot = {
        "session_id":          session_id,
        "volume_name":         volume_name,
        "n_slices":            session_data["n_slices"],
        "tumor_slice_indices": session_data["tumor_slice_indices"],
        "slice_meta":          session_data["slice_meta"],
        "tumor_detected":      session_data["tumor_detected"],
        "tumor_voxels":        session_data["tumor_voxels"],
        "liver_voxels":        session_data["liver_voxels"],
        "ct_path":             str(ct_dest),
        "pred_path":           str(pred_dest),
    }
    session_json = case_dir / "session.json"
    with open(session_json, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)
    logger.info(f"[{session_id}] Demo session.json saved → {session_json}")

    # ── Standalone combined HTML viewer ───────────────────────────
    if write_combined_html_fn is not None:
        try:
            html_path = case_dir / f"{volume_name}_viewer.html"
            logger.info(f"[{session_id}] Streaming viewer HTML → {html_path}...")
            file_size = write_combined_html_fn(session_id, html_path)
            logger.info(
                f"[{session_id}] Viewer HTML saved → {html_path} "
                f"({file_size // (1024*1024)} MB)"
            )
        except Exception as exc:
            # Non-fatal: session.json + NIfTIs are already written
            logger.warning(
                f"[{session_id}] Failed to write viewer HTML (non-fatal): {exc}"
            )
    else:
        logger.debug(f"[{session_id}] No write_combined_html_fn provided — skipping HTML export.")

    return case_dir


# ─────────────────────────────────────────────────────────────────
# CLI — regenerate _viewer.html for all cases in resultsTs/
#
# Run from backend/:
#   python save_demo.py              # all cases
#   python save_demo.py liver_160    # single case
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import time

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
    )

    try:
        import session_store
        from main import _write_combined_html, _vol_cache
    except ImportError as exc:
        logging.error(f"Import failed: {exc}\nRun from backend/ with the same venv as the server.")
        sys.exit(1)

    results_dir = Path(__file__).parent / "resultsTs"
    if not results_dir.exists():
        logging.error(f"resultsTs/ not found at {results_dir}")
        sys.exit(1)

    target_case = sys.argv[1] if len(sys.argv) > 1 else None
    json_files  = sorted(results_dir.glob("*_results.json"))
    if target_case:
        json_files = [f for f in json_files
                      if f.stem.removesuffix("_results") == target_case]
    if not json_files:
        logging.error(f"No cases found{f' matching {target_case!r}' if target_case else ''}")
        sys.exit(1)

    logging.info(f"Found {len(json_files)} case(s) to regenerate.\n")
    session_store.init()
    ok = err = skip = 0

    def _inject(sid, data):
        import session_store as ss
        for attr in ("_sessions", "sessions", "_store", "store", "_data"):
            d = getattr(ss, attr, None)
            if isinstance(d, dict):
                d[sid] = data
                return
        orig = ss.get
        ss.get = lambda s, _o=orig: data if s == sid else _o(s)

    def _remove(sid):
        import session_store as ss
        for attr in ("_sessions", "sessions", "_store", "store", "_data"):
            d = getattr(ss, attr, None)
            if isinstance(d, dict):
                d.pop(sid, None)
                return
        prev = ss.get
        ss.get = lambda s, _p=prev: None if s == sid else _p(s)

    for json_path in json_files:
        case = json_path.stem.removesuffix("_results")
        out_path = results_dir / f"{case}_viewer.html"

        try:
            with open(json_path, encoding="utf-8") as f:
                meta = json.load(f)
        except Exception as exc:
            logging.warning(f"[{case}] Bad JSON: {exc} — skipping")
            skip += 1
            continue

        ct_candidates   = [Path(meta["ct_path"])]   if meta.get("ct_path")   else []
        pred_candidates = [Path(meta["pred_path"])]  if meta.get("pred_path") else []
        ct_candidates   += [results_dir / case / "ct.nii.gz",   results_dir / f"{case}_ct.nii.gz"]
        pred_candidates += [results_dir / case / "pred.nii.gz", results_dir / f"{case}_pred.nii.gz"]

        ct_path   = next((p for p in ct_candidates   if p.exists()), None)
        pred_path = next((p for p in pred_candidates if p.exists()), None)
        if not ct_path or not pred_path:
            logging.warning(f"[{case}] NIfTIs missing — skipping")
            skip += 1
            continue

        tmp_id = f"regen_{case}"
        _inject(tmp_id, {
            "volume_name":         meta.get("volume_name", case),
            "n_slices":            meta["n_slices"],
            "tumor_slice_indices": meta.get("tumor_slice_indices", []),
            "slice_meta":          meta.get("slice_meta", []),
            "tumor_detected":      meta.get("tumor_detected", False),
            "tumor_voxels":        meta.get("tumor_voxels", 0),
            "liver_voxels":        meta.get("liver_voxels", 0),
            "ct_path":             str(ct_path),
            "pred_path":           str(pred_path),
        })

        t0 = time.perf_counter()
        try:
            file_size = _write_combined_html(tmp_id, out_path)
            elapsed   = round(time.perf_counter() - t0, 1)
            logging.info(f"[{case}] ✓  {out_path.name}  ({file_size//(1024*1024)} MB, {elapsed}s)")
            ok += 1
        except Exception as exc:
            logging.error(f"[{case}] ✗  {exc}")
            err += 1
        finally:
            _remove(tmp_id)
            _vol_cache.pop(tmp_id, None)

    logging.info(f"\nDone — {ok} written, {skip} skipped, {err} errors.")
    if err:
        sys.exit(1)

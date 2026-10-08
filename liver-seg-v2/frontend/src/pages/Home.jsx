// src/pages/Home.jsx
// Uses SliceViewerFull instead of SliceViewer so coronal/sagittal
// tabs get real dimensions, per-plane tumor charts, and live stats.

import { useState } from "react";
import Upload from "../components/Upload";
import SliceViewer from "../components/SliceViewer";
import { saveResults, getSessionMeta } from "../services/api";
import "./Home.css";

const DemoModeButton = () => (
  <a
    href="/demo"
    style={{
      display: "inline-flex",
      alignItems: "center",
      gap: "6px",
      padding: "5px 13px",
      borderRadius: "7px",
      border: "1px solid #30363d",
      background: "transparent",
      color: "#8b949e",
      fontSize: "12px",
      fontFamily: "inherit",
      textDecoration: "none",
      letterSpacing: "0.04em",
      transition: "all 0.15s",
      whiteSpace: "nowrap",
    }}
    onMouseEnter={(e) => {
      e.currentTarget.style.borderColor = "#f97316";
      e.currentTarget.style.color = "#f97316";
    }}
    onMouseLeave={(e) => {
      e.currentTarget.style.borderColor = "#30363d";
      e.currentTarget.style.color = "#8b949e";
    }}
  >
    <span style={{ fontSize: "13px" }}>🔬</span>
    Demo Mode
  </a>
);

export default function Home() {
    const [view,        setView]        = useState("upload");
    const [result,      setResult]      = useState(null);
    const [saveStatus,  setSaveStatus]  = useState(null);
    const [savedPath,   setSavedPath]   = useState("");
    // Per-plane meta for coronal + sagittal
    const [planeMeta,   setPlaneMeta]   = useState(null);

    const handleResult = async (data) => {
        setResult(data);
        setView("result");
        // Fetch coronal/sagittal meta in the background — non-blocking
        try {
            const meta = await getSessionMeta(data.session_id);
            setPlaneMeta(meta);
        } catch (err) {
            console.warn("session-meta fetch failed:", err);
        }
    };

    const handleReset = () => {
        setResult(null);
        setView("upload");
        setSaveStatus(null);
        setSavedPath("");
        setPlaneMeta(null);
    };

    const handleSave = async () => {
        if (!result?.session_id) return;
        setSaveStatus("saving");
        try {
            const res = await saveResults(result.session_id);
            if (res.status === "saved") { setSaveStatus("saved"); setSavedPath(res.folder ?? res.path ?? ""); }
            else setSaveStatus("cancelled");
        } catch { setSaveStatus("error"); }
    };

    const saveBtnLabel = {
        null:      "⬇ Save Results",
        saving:    "Generating sliders…",
        saved:     "✓ Saved",
        cancelled: "⬇ Save Results",
        error:     "Save failed — retry",
    }[saveStatus];

    const beta3dUrl = result?.session_id
        ? `/beta-3d?session=${result.session_id}`
        : "/beta-3d";

return (
    <div className="home-root">

        <header className="app-header">
            <div
                className="header-inner"
                style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                }}
            >
                <div className="logo">
                    <OrganIcon />
                    <span className="logo-text">
                        Liver<span className="logo-accent">Seg</span>
                    </span>
                </div>

                <DemoModeButton />

                <nav className="header-nav">
                    {view === "result" && (
                        <>
                            <a
                                href={beta3dUrl}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="nav-link nav-link-beta"
                                title="Experimental 3D mesh viewer (opens in new tab)"
                            >
                                View in 3D
                                <span className="beta-tag">Beta</span>
                            </a>
                            <button
                                className={`nav-btn nav-btn-save ${saveStatus === "saved" ? "nav-btn-success" : ""}`}
                                onClick={handleSave}
                                disabled={saveStatus === "saving"}
                            >
                                {saveBtnLabel}
                            </button>
                            <button className="nav-btn" onClick={handleReset}>
                                ← New Scan
                            </button>
                        </>
                    )}
                    <a href="http://localhost:8000/docs" target="_blank"
                        rel="noopener noreferrer" className="nav-link">Docs</a>
                </nav>
            </div>
        </header>

        <main className="home-main">

            {/* ── Upload ── */}
            {view === "upload" && (
                <div className="upload-page">
                    <div className="hero-text">
                        <h1 className="hero-title">
                            Liver Tumour<br />
                            <span className="hero-accent">Segmentation</span>
                        </h1>
                        <p className="hero-sub">
                            Upload a CT scan in NIfTI format. The nnUNet 2D 4-fold
                            ensemble segments the liver and detects tumour regions —
                            shown in a dual CT slice viewer with raw and overlay panels.
                        </p>
                        <div className="feature-pills">
                            {["nnUNet 2D · 4-Fold Ensemble", "GPU accelerated",
                              "NIfTI .nii.gz", "Dual slice viewer"].map(f => (
                                <span key={f} className="pill">{f}</span>
                            ))}
                        </div>
                    </div>
                    <div className="upload-card">
                        <Upload onResult={handleResult} />
                    </div>
                    <div className="info-grid">
                        <InfoCard icon="🧠" title="nnUNet Ensemble"
                            body="4-fold nnUNet 2D ensemble trained on MSD Task03. Liver Dice 0.9694 · Tumour Dice 0.8010." />
                        <InfoCard icon="⚡" title="GPU Accelerated"
                            body="Runs on your local CUDA GPU. Typical inference time 1–2 minutes per scan." />
                        <InfoCard icon="🔬" title="Dual Slice Viewer"
                            body="Raw CT and segmentation overlay side by side. Scroll all axial slices with the slider." />
                    </div>
                </div>
            )}

            {/* ── Result ── */}
            {view === "result" && result && (
                <div className="result-page">

                    <div className="result-header">
                        <div>
                            <h2 className="result-title">Segmentation Result</h2>
                            <div className="result-meta-row">
                                {result.volume_name && (
                                    <span className="result-volume">{result.volume_name}</span>
                                )}
                                <span className="result-sub">
                                    {result.processing_time_s?.toFixed(1)} s
                                    &nbsp;·&nbsp; Session: <code>{result.session_id}</code>
                                </span>
                            </div>
                            {saveStatus === "saved" && savedPath && (
                                <p className="save-path">Saved → {savedPath}</p>
                            )}
                        </div>
                        <div className="result-badges">
                            {result.liver_voxels > 0 && (
                                <span className="badge badge-liver">Liver detected</span>
                            )}
                            {result.tumor_detected
                                ? <span className="badge badge-tumor">Tumour detected</span>
                                : <span className="badge badge-none">No tumour</span>
                            }
                        </div>
                    </div>

                    {/* CT slices — full width */}
                    <section className="result-section">
                        <div className="section-label">
                            <span className="section-dot dot-2d" />
                            CT Slices
                            <span className="section-count">
                                {result.n_slices} axial &nbsp;·&nbsp;
                                {result.tumor_slice_indices?.length ?? 0} tumour slices
                            </span>
                        </div>
                        <div className="slice-viewer-wrap">
                            <SliceViewer
                                sessionId={result.session_id}
                                nSlices={result.n_slices}
                                sliceMeta={result.slice_meta}
                                tumorSliceIndices={result.tumor_slice_indices}
                                volumeName={result.volume_name}
                                coronalN={planeMeta?.coronal_n}
                                coronalSliceMeta={planeMeta?.coronal_slice_meta}
                                coronalTumorIndices={planeMeta?.coronal_tumor_indices}
                                sagittalN={planeMeta?.sagittal_n}
                                sagittalSliceMeta={planeMeta?.sagittal_slice_meta}
                                sagittalTumorIndices={planeMeta?.sagittal_tumor_indices}
                            />
                        </div>
                    </section>

                    {/* Stats */}
                    <div className="result-stats-row">
                        <StatChip label="Liver voxels"
                            value={result.liver_voxels?.toLocaleString() ?? "—"}
                            color="#32dcc8" />
                        <StatChip label="Tumour voxels"
                            value={result.tumor_voxels?.toLocaleString() ?? "—"}
                            color="#ff4040" />
                        <StatChip label="Tumour slices"
                            value={result.tumor_slice_indices?.length ?? 0}
                            color="#f59e0b" />
                        <StatChip label="Total slices"
                            value={result.n_slices ?? "—"}
                            color="#94a3b8" />
                    </div>

                </div>
            )}
        </main>

        <footer className="app-footer">
            <p>
                For research use only — not a certified medical device.
                <span className="footer-sep">·</span>
                LiverSeg v2.0
                <span className="footer-sep">·</span>
                nnUNet 2D · 4-Fold Ensemble
            </p>
        </footer>
    </div>
);
}

function InfoCard({ icon, title, body }) {
    return (
        <div className="info-card">
            <span className="info-icon">{icon}</span>
            <h4 className="info-title">{title}</h4>
            <p className="info-body">{body}</p>
        </div>
    );
}

function StatChip({ label, value, color }) {
    return (
        <div className="stat-chip">
            <span className="stat-chip-dot" style={{ background: color }} />
            <span className="stat-chip-val">{value}</span>
            <span className="stat-chip-label">{label}</span>
        </div>
    );
}

function OrganIcon() {
    return (
        <svg width="28" height="28" viewBox="0 0 28 28" fill="none"
            xmlns="http://www.w3.org/2000/svg">
            <path d="M4 10c0-4 3-7 7-7 2 0 3.5 1 3 3s1 4 4 4 6 3 6 7-4 7-8 7c-2 0-3-1-4-3s-3-3-5-3c-2 0-3-2-3-4v-4z"
                fill="#c85a7a" fillOpacity="0.9" />
            <circle cx="17" cy="17" r="3" fill="#ff2020" fillOpacity="0.85" />
        </svg>
    );
}

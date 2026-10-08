// src/pages/Beta3D.jsx
// ------------------------------------------------------------------
// Standalone 3D mesh viewer page.
// Accessed via: http://localhost:5173/beta-3d?session=SESSION_ID
//
// Fetches the mesh data from the backend session, then renders
// the Viewer3D component full-screen.
//
// This page is intentionally separate from the main flow so it
// can be removed easily in future without touching Home.jsx.
// ------------------------------------------------------------------

import { useEffect, useState } from "react";
import Viewer3D from "../components/Viewer3D";
import api from "../services/api";
import "./Beta3D.css";

export default function Beta3D() {
    // Read session_id from URL query param: /beta-3d?session=abc12345
    const params    = new URLSearchParams(window.location.search);
    const sessionId = params.get("session") || "";

    const [state,  setState]  = useState("loading");   // loading | ready | error
    const [meshes, setMeshes] = useState(null);
    const [volName, setVolName] = useState("");
    const [error,  setError]  = useState("");

    useEffect(() => {
        if (!sessionId) {
            setState("error");
            setError("No session ID in URL. Open this page from a segmentation result.");
            return;
        }

        // Fetch session info from /model/info (just to check backend is alive)
        // then fetch the mesh data stored in the result
        // We re-run inference? No — we read the stored session.
        // The session store holds ct_path, pred_path, metadata.
        // We need the mesh, but we didn't store it in session.
        // Solution: store mesh in session OR re-read from stored nifti.
        // Simplest: store mesh JSON in session_store at predict time.
        api.get(`/mesh/${sessionId}`)
            .then(r => {
                setMeshes({ liver: r.data.liver, tumor: r.data.tumor });
                setVolName(r.data.volume_name || sessionId);
                setState("ready");
            })
            .catch(err => {
                setError(err.message || "Failed to load mesh data.");
                setState("error");
            });
    }, [sessionId]);

    return (
        <div className="b3d-root">
            <header className="b3d-header">
                <div className="b3d-header-inner">
                    <a href="/" className="b3d-logo">
                        <OrganIcon />
                        <span>Liver<span className="b3d-accent">Seg</span></span>
                    </a>
                    <div className="b3d-header-right">
                        {volName && <span className="b3d-vol">{volName}</span>}
                        <span className="b3d-beta-badge">Beta</span>
                        <button className="b3d-back" onClick={() => window.history.back()}>
                            ← Back
                        </button>
                    </div>
                </div>
            </header>

            <main className="b3d-main">
                {state === "loading" && (
                    <div className="b3d-center">
                        <div className="b3d-spinner" />
                        <p>Loading 3D mesh…</p>
                    </div>
                )}

                {state === "error" && (
                    <div className="b3d-center b3d-error">
                        <p>⚠ {error}</p>
                        <p className="b3d-hint">
                            Run a segmentation first, then click "View in 3D" from the result page.
                        </p>
                    </div>
                )}

                {state === "ready" && meshes && (
                    <div className="b3d-viewer-wrap">
                        <Viewer3D liverMesh={meshes.liver} tumorMesh={meshes.tumor} />
                    </div>
                )}
            </main>

            <footer className="b3d-footer">
                <p>
                    Beta feature — 3D mesh quality is limited by nnUNet 2D slice-by-slice predictions.
                    <span className="b3d-sep">·</span>
                    For research use only.
                </p>
            </footer>
        </div>
    );
}

function OrganIcon() {
    return (
        <svg width="24" height="24" viewBox="0 0 28 28" fill="none"
            xmlns="http://www.w3.org/2000/svg">
            <path d="M4 10c0-4 3-7 7-7 2 0 3.5 1 3 3s1 4 4 4 6 3 6 7-4 7-8 7c-2 0-3-1-4-3s-3-3-5-3c-2 0-3-2-3-4v-4z"
                fill="#c85a7a" fillOpacity="0.9" />
            <circle cx="17" cy="17" r="3" fill="#ff2020" fillOpacity="0.85" />
        </svg>
    );
}

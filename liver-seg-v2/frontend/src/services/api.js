// src/services/api.js
// All fetch calls to the FastAPI backend in one place.

const BASE = "http://localhost:8000";

// ── Inference ──────────────────────────────────────────────────────────────

export async function predict(file, onProgress) {
    const formData = new FormData();
    formData.append("file", file);

    return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();

        xhr.upload.addEventListener("progress", (e) => {
            if (e.lengthComputable && onProgress) {
                onProgress(Math.round((e.loaded / e.total) * 100));
            }
        });

        xhr.addEventListener("load", () => {
            if (xhr.status >= 200 && xhr.status < 300) {
                try {
                    resolve(JSON.parse(xhr.responseText));
                } catch {
                    reject(new Error("Invalid JSON response from server."));
                }
            } else {
                let detail = `Server error ${xhr.status}`;
                try {
                    detail = JSON.parse(xhr.responseText)?.detail ?? detail;
                } catch {}
                reject(new Error(detail));
            }
        });

        xhr.addEventListener("error",   () => reject(new Error("Network error — is the backend running?")));
        xhr.addEventListener("timeout",  () => reject(new Error("Request timed out.")));

        xhr.open("POST", `${BASE}/predict`);
        xhr.timeout = 1_800_000; // 30 minutes
        xhr.send(formData);
    });
}

// ── Session meta (real coronal/sagittal dimensions + per-plane tumor meta) ──

export async function getSessionMeta(sessionId) {
    const r = await fetch(`${BASE}/session-meta/${sessionId}`);
    if (!r.ok) throw new Error(`Session meta fetch failed: ${r.status}`);
    return r.json();
}

// ── Slice fetching ─────────────────────────────────────────────────────────

export async function getSlice(sessionId, z) {
    const r = await fetch(`${BASE}/slice/${sessionId}/${z}`);
    if (!r.ok) throw new Error(`Slice ${z} fetch failed: ${r.status}`);
    const blob = await r.blob();
    return URL.createObjectURL(blob);
}

export async function getSliceRaw(sessionId, z) {
    const r = await fetch(`${BASE}/slice-raw/${sessionId}/${z}`);
    if (!r.ok) throw new Error(`Raw slice ${z} fetch failed: ${r.status}`);
    const blob = await r.blob();
    return URL.createObjectURL(blob);
}

// ── Orthogonal slice fetching ──────────────────────────────────────────────

export async function getSliceCoronal(sessionId, y) {
    const r = await fetch(`${BASE}/slice-coronal/${sessionId}/${y}`);
    if (!r.ok) throw new Error(`Coronal slice ${y} failed: ${r.status}`);
    return URL.createObjectURL(await r.blob());
}

export async function getSliceCoronalRaw(sessionId, y) {
    const r = await fetch(`${BASE}/slice-coronal-raw/${sessionId}/${y}`);
    if (!r.ok) throw new Error(`Coronal raw slice ${y} failed: ${r.status}`);
    return URL.createObjectURL(await r.blob());
}

export async function getSliceSagittal(sessionId, x) {
    const r = await fetch(`${BASE}/slice-sagittal/${sessionId}/${x}`);
    if (!r.ok) throw new Error(`Sagittal slice ${x} failed: ${r.status}`);
    return URL.createObjectURL(await r.blob());
}

export async function getSliceSagittalRaw(sessionId, x) {
    const r = await fetch(`${BASE}/slice-sagittal-raw/${sessionId}/${x}`);
    if (!r.ok) throw new Error(`Sagittal raw slice ${x} failed: ${r.status}`);
    return URL.createObjectURL(await r.blob());
}

// ── Save results (3 HTML sliders + JSON + NIfTIs) ─────────────────────────
// Uses XHR so we can set a proper timeout — fetch() has no built-in timeout
// and the browser will silently kill long requests.  Coronal + sagittal HTML
// generation can take several minutes on large volumes, so we allow 15 min.

export async function saveResults(sessionId) {
    return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();

        xhr.addEventListener("load", () => {
            if (xhr.status >= 200 && xhr.status < 300) {
                try {
                    resolve(JSON.parse(xhr.responseText));
                } catch {
                    reject(new Error("Invalid JSON response from server."));
                }
            } else {
                let detail = `Server error ${xhr.status}`;
                try { detail = JSON.parse(xhr.responseText)?.detail ?? detail; } catch {}
                reject(new Error(detail));
            }
        });

        xhr.addEventListener("error",   () => reject(new Error("Network error — is the backend running?")));
        xhr.addEventListener("timeout",  () => reject(new Error("Save timed out — the volume may be too large. Try again.")));

        xhr.open("GET", `${BASE}/save-results/${encodeURIComponent(sessionId)}`);
        xhr.timeout = 15 * 60 * 1000; // 15 minutes — matches server thread timeout
        xhr.send();
    });
}

// ── Demo ───────────────────────────────────────────────────────────────────

export async function uploadDemo(file) {
    const formData = new FormData();
    formData.append("file", file);

    const r = await fetch(`${BASE}/demo/upload`, {
        method: "POST",
        body: formData
    });

    if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        throw new Error(err.detail || "Demo upload failed");
    }

    return r.json();
}

export function getDemoViewer(caseId) {
    return `${BASE}/demo/viewer/${caseId}`;
}

export async function getDemoResult(caseId) {
    const r = await fetch(`${BASE}/demo/result/${caseId}`);
    if (!r.ok) throw new Error("Demo result failed");
    return r.json();
}

export default {
    predict,
    getSessionMeta,
    getSlice,
    getSliceRaw,
    getSliceCoronal,
    getSliceCoronalRaw,
    getSliceSagittal,
    getSliceSagittalRaw,
    saveResults,
    uploadDemo,
    getDemoViewer,
};

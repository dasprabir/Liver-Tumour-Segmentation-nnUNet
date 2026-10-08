// src/components/SliceViewerFull.jsx
// ------------------------------------------------------------------
// Drop-in replacement for SliceViewer that accepts real coronal/sagittal
// dimensions and per-plane slice meta, enabling tumor charts + stats
// for all three orientations.
//
// Props (superset of SliceViewer):
//   sessionId, nSlices, sliceMeta, tumorSliceIndices, volumeName
//   coronalN, coronalSliceMeta, coronalTumorIndices
//   sagittalN, sagittalSliceMeta, sagittalTumorIndices
// ------------------------------------------------------------------

import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import {
    getSlice, getSliceRaw,
    getSliceCoronal, getSliceCoronalRaw,
    getSliceSagittal, getSliceSagittalRaw,
} from "../services/api";
import "./SliceViewer.css";

const PREFETCH       = 8;
const MAX_CHART_BARS = 200;

// ── Chart bucketing ────────────────────────────────────────────────
function buildChartBuckets(sliceMeta) {
    if (!sliceMeta?.length) return [];
    const n     = sliceMeta.length;
    const nBars = Math.min(n, MAX_CHART_BARS);
    const out   = [];
    for (let b = 0; b < nBars; b++) {
        const s0    = Math.floor((b / nBars) * n);
        const s1    = Math.min(Math.ceil(((b + 1) / nBars) * n), n);
        const chunk = sliceMeta.slice(s0, s1);
        const maxTp = Math.max(...chunk.map(m => m.tumor_pixels));
        const hasTu = chunk.some(m => m.has_tumor);
        const repI  = chunk.reduce((a, x) => x.tumor_pixels > a.tumor_pixels ? x : a, chunk[0]).slice_index;
        out.push({ maxTp, hasTu, repI, s0, s1 });
    }
    return out;
}

// ── Generic panel ─────────────────────────────────────────────────
function ViewerPanel({
    sessionId,
    nSlices,
    fetchOv,
    fetchRaw,
    sliceMeta,
    tumorIndices,
}) {
    const [idx,     setIdx]     = useState(0);
    const [rawSrc,  setRawSrc]  = useState(null);
    const [ovSrc,   setOvSrc]   = useState(null);
    const [loading, setLoading] = useState(true);

    const rawCache = useRef({});
    const ovCache  = useRef({});
    const fetching = useRef(new Set());

    const buckets      = useMemo(() => buildChartBuckets(sliceMeta), [sliceMeta]);
    const maxTp        = useMemo(() => Math.max(...buckets.map(b => b.maxTp), 1), [buckets]);
    const activeBucket = useMemo(
        () => buckets.findIndex(b => idx >= b.s0 && idx < b.s1),
        [buckets, idx]
    );

    // Jump to densest tumour slice on mount
    useEffect(() => {
        if (!sliceMeta?.length || !tumorIndices?.length) return;
        const densest = sliceMeta
            .filter(m => m.has_tumor)
            .reduce((a, b) => a.tumor_pixels > b.tumor_pixels ? a : b);
        setIdx(densest.slice_index);
    }, [sliceMeta, tumorIndices]);

    const fetchBoth = useCallback(async (z) => {
        if (!sessionId || z < 0 || z >= nSlices) return;
        const key = String(z);
        if (fetching.current.has(key) || (rawCache.current[z] && ovCache.current[z])) return;
        fetching.current.add(key);
        try {
            const [raw, ov] = await Promise.all([
                rawCache.current[z] ?? fetchRaw(sessionId, z),
                ovCache.current[z]  ?? fetchOv(sessionId, z),
            ]);
            rawCache.current[z] = raw;
            ovCache.current[z]  = ov;
        } catch (err) {
            console.error(`Slice ${z} error:`, err);
        } finally {
            fetching.current.delete(key);
        }
    }, [sessionId, nSlices, fetchRaw, fetchOv]);

    // Warm up first 20 + tumour slices
    useEffect(() => {
        if (!sessionId) return;
        for (let z = 0; z < Math.min(20, nSlices); z++) fetchBoth(z);
        tumorIndices?.slice(0, 10).forEach(z => fetchBoth(z));
    }, [sessionId, nSlices, fetchBoth, tumorIndices]);

    // Load current slice + prefetch neighbours
    useEffect(() => {
        if (!sessionId) return;
        let cancelled = false;
        const load = async () => {
            if (rawCache.current[idx] && ovCache.current[idx]) {
                setRawSrc(rawCache.current[idx]);
                setOvSrc(ovCache.current[idx]);
                setLoading(false);
            } else {
                setLoading(true);
                await fetchBoth(idx);
                if (cancelled) return;
                if (rawCache.current[idx] && ovCache.current[idx]) {
                    setRawSrc(rawCache.current[idx]);
                    setOvSrc(ovCache.current[idx]);
                }
                setLoading(false);
            }
            for (let d = 1; d <= PREFETCH; d++) {
                fetchBoth(idx + d);
                fetchBoth(idx - d);
            }
        };
        load();
        return () => { cancelled = true; };
    }, [idx, sessionId, fetchBoth]);

    // Keyboard nav
    useEffect(() => {
        const h = (e) => {
            if (e.key === "ArrowRight" || e.key === "ArrowDown")
                setIdx(i => Math.min(i + 1, nSlices - 1));
            if (e.key === "ArrowLeft"  || e.key === "ArrowUp")
                setIdx(i => Math.max(i - 1, 0));
        };
        window.addEventListener("keydown", h);
        return () => window.removeEventListener("keydown", h);
    }, [nSlices]);

    // Cleanup blob URLs on unmount
    useEffect(() => () => {
        Object.values(rawCache.current).forEach(u => URL.revokeObjectURL(u));
        Object.values(ovCache.current).forEach(u => URL.revokeObjectURL(u));
    }, []);

    const jumpToTumour = useCallback(() => {
        if (!sliceMeta) return;
        const d = sliceMeta.filter(m => m.has_tumor)
            .reduce((a, b) => a.tumor_pixels > b.tumor_pixels ? a : b, null);
        if (d) setIdx(d.slice_index);
    }, [sliceMeta]);

    const meta      = sliceMeta?.find(m => m.slice_index === idx) ?? sliceMeta?.[idx];
    const hasTumour = meta?.has_tumor ?? false;

    return (
        <>
            {/* Slice label + badges + jump */}
            <div className="sv-panel-toprow">
                <span className="sv-slice-label">
                    Slice <strong>{idx}</strong>
                    <span className="sv-slice-total"> / {nSlices - 1}</span>
                </span>
                <div className="sv-badges">
                    {hasTumour && <span className="sv-badge sv-badge-tumor">Tumour</span>}
                    {(meta?.liver_pixels ?? 0) > 0 &&
                        <span className="sv-badge sv-badge-liver">Liver</span>}
                </div>
                {(tumorIndices?.length ?? 0) > 0 && (
                    <button className="sv-jump-btn" onClick={jumpToTumour}>
                        Jump to tumour
                    </button>
                )}
            </div>

            {/* Dual panels */}
            <div className="sv-panels">
                <div className="sv-panel">
                    <div className="sv-panel-label">
                        <span className="sv-panel-dot sv-dot-gray"/>CT Slice (raw)
                    </div>
                    <div className="sv-img-wrap">
                        {loading && <div className="sv-skeleton"><div className="sv-skeleton-pulse"/></div>}
                        {rawSrc && <img src={rawSrc} alt={`Raw ${idx}`}
                            className={`sv-img ${loading ? "sv-img-hidden" : ""}`}/>}
                    </div>
                </div>
                <div className="sv-panel">
                    <div className="sv-panel-label">
                        <span className="sv-panel-dot sv-dot-accent"/>Segmentation Overlay
                    </div>
                    <div className="sv-img-wrap">
                        {loading && <div className="sv-skeleton"><div className="sv-skeleton-pulse"/></div>}
                        {ovSrc && <img src={ovSrc} alt={`Overlay ${idx}`}
                            className={`sv-img ${loading ? "sv-img-hidden" : ""}`}/>}
                    </div>
                </div>
            </div>

            {/* Slider */}
            <div className="sv-slider-row">
                <span className="sv-slider-num">0</span>
                <input type="range" min={0} max={nSlices - 1} value={idx}
                    onChange={e => setIdx(parseInt(e.target.value))}
                    className="sv-slider" aria-label="Slice navigation"/>
                <span className="sv-slider-num">{nSlices - 1}</span>
            </div>

            {/* Tumour chart — shown for any plane that has sliceMeta */}
            {sliceMeta && maxTp > 0 && buckets.length > 0 && (
                <div className="sv-chart">
                    <p className="sv-chart-label">
                        Tumour pixels per slice
                        {sliceMeta.length > MAX_CHART_BARS && (
                            <span className="sv-chart-note">
                                &nbsp;(grouped into {buckets.length} bands)
                            </span>
                        )}
                    </p>
                    <div className="sv-chart-bars">
                        {buckets.map((b, i) => (
                            <div key={i}
                                className={`sv-bar ${i === activeBucket ? "sv-bar-active" : ""} ${b.hasTu ? "sv-bar-tumor" : "sv-bar-empty"}`}
                                style={{ height: `${Math.max(Math.round((b.maxTp / maxTp) * 100), b.hasTu ? 6 : 2)}%` }}
                                onClick={() => setIdx(b.repI)}
                                title={`Slices ${b.s0}–${b.s1 - 1}: max ${b.maxTp} px`}
                            />
                        ))}
                    </div>
                </div>
            )}

            {/* Stats */}
            <div className="sv-stats-row">
                <span className="sv-stat">
                    <span className="sv-stat-dot sv-dot-liver"/>
                    Liver: {(meta?.liver_pixels ?? 0).toLocaleString()} px
                </span>
                <span className="sv-stat">
                    <span className="sv-stat-dot sv-dot-tumor"/>
                    Tumour: {(meta?.tumor_pixels ?? 0).toLocaleString()} px
                </span>
                <span className="sv-stat-hint">← → to navigate</span>
            </div>
        </>
    );
}



// ── Main component with tabs ───────────────────────────────────────
export default function SliceViewer({
    sessionId, nSlices, sliceMeta, tumorSliceIndices, volumeName,
    coronalN, coronalSliceMeta, coronalTumorIndices,
    sagittalN, sagittalSliceMeta, sagittalTumorIndices,
}) {
    const [activeView, setActiveView] = useState("axial");

    // Use real dimensions from session-meta, fall back to 512 if not yet loaded
    const views = [
        {
            key: "axial",
            label: "Axial",
            nSlices: nSlices,
            fetchOv: getSlice,
            fetchRaw: getSliceRaw,
            sliceMeta: sliceMeta,
            tumorIndices: tumorSliceIndices,
        },
        {
            key: "coronal",
            label: "Coronal",
            nSlices: coronalN ?? 512,
            fetchOv: getSliceCoronal,
            fetchRaw: getSliceCoronalRaw,
            sliceMeta: coronalSliceMeta ?? null,
            tumorIndices: coronalTumorIndices ?? null,
        },
        {
            key: "sagittal",
            label: "Sagittal",
            nSlices: sagittalN ?? 512,
            fetchOv: getSliceSagittal,
            fetchRaw: getSliceSagittalRaw,
            sliceMeta: sagittalSliceMeta ?? null,
            tumorIndices: sagittalTumorIndices ?? null,
        },
    ];

    const cfg = views.find(v => v.key === activeView);

    if (!sessionId) return (
        <div className="sv-root sv-empty"><p>No session data.</p></div>
    );

    return (
        <div className="sv-root">

            {/* Top bar */}
            <div className="sv-topbar">
                <div className="sv-topbar-left">
                    {volumeName && <span className="sv-volume-name">{volumeName}</span>}
                    <span className="sv-slice-label">
                        <span className="sv-slice-total">
                            {nSlices} axial · {tumorSliceIndices?.length ?? 0} tumour slices
                        </span>
                    </span>
                </div>

            </div>

            {/* Tabs */}
            <div className="sv-tabs">
                {views.map(v => (
                    <button key={v.key}
                        className={`sv-tab ${activeView === v.key ? "sv-tab-active" : ""}`}
                        onClick={() => setActiveView(v.key)}
                    >
                        {v.label}
                        {/* Show tumour count badge on tab if meta is loaded */}
                        {v.key !== "axial" && v.tumorIndices?.length > 0 && (
                            <span style={{
                                marginLeft: 5,
                                fontSize: "0.65em",
                                background: "rgba(255,64,64,.2)",
                                color: "#ff6060",
                                borderRadius: 4,
                                padding: "1px 5px",
                            }}>
                                {v.tumorIndices.length}
                            </span>
                        )}
                    </button>
                ))}
            </div>

            {/* Panel — key forces full remount + cache clear on tab switch */}
            <ViewerPanel
                key={activeView}
                sessionId={sessionId}
                nSlices={cfg.nSlices}
                fetchOv={cfg.fetchOv}
                fetchRaw={cfg.fetchRaw}
                sliceMeta={cfg.sliceMeta}
                tumorIndices={cfg.tumorIndices}
            />

        </div>
    );
}

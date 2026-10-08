import { useState, useEffect, useRef, useCallback } from "react";

/**
 * DemoSliceViewer — offline slice viewer that reads from pre-baked JSON data.
 * Props match SliceViewer so the same parent layout works for both flows.
 *
 * Props:
 *   demoData  — full demo JSON object (slices[], tumor_slice_indices, n_slices, …)
 *   style     — optional extra inline styles for the root wrapper
 */
export default function DemoSliceViewer({ demoData, style }) {
  const [sliceIdx, setSliceIdx] = useState(0);
  const [showOverlay, setShowOverlay] = useState(true);
  const [showTumorOnly, setShowTumorOnly] = useState(false);

  const sliderRef = useRef(null);

  const slices = demoData?.slices ?? [];
  const tumorSet = new Set(demoData?.tumor_slice_indices ?? []);
  const nSlices = demoData?.n_slices ?? slices.length;

  // Jump to first tumor slice on load
  useEffect(() => {
    if (demoData?.tumor_slice_indices?.length > 0) {
      setSliceIdx(demoData.tumor_slice_indices[0]);
    }
  }, [demoData]);

  const visibleSlices = showTumorOnly
    ? Array.from(tumorSet).sort((a, b) => a - b)
    : null; // null = show all

  const currentSlice = slices[sliceIdx] ?? null;

  const handleSliderChange = useCallback((e) => {
    setSliceIdx(Number(e.target.value));
  }, []);

  const step = (dir) => {
    if (showTumorOnly && visibleSlices) {
      const pos = visibleSlices.indexOf(sliceIdx);
      const next = visibleSlices[Math.max(0, Math.min(visibleSlices.length - 1, pos + dir))];
      if (next !== undefined) setSliceIdx(next);
    } else {
      setSliceIdx((i) => Math.max(0, Math.min(nSlices - 1, i + dir)));
    }
  };

  const isTumorSlice = tumorSet.has(sliceIdx);

  return (
    <div className="dsv-root" style={style}>
      {/* ── Header bar ── */}
      <div className="dsv-header">
        <span className="dsv-vol-name">{demoData?.volume_name ?? "Demo"}</span>
        <div className="dsv-controls-row">
          <button
            className={`dsv-btn ${showOverlay ? "active" : ""}`}
            onClick={() => setShowOverlay((v) => !v)}
          >
            {showOverlay ? "Hide Overlay" : "Show Overlay"}
          </button>
          <button
            className={`dsv-btn ${showTumorOnly ? "active" : ""}`}
            onClick={() => setShowTumorOnly((v) => !v)}
            disabled={tumorSet.size === 0}
          >
            Tumour Slices ({tumorSet.size})
          </button>
          {/* No download button here — use Save Results in the main nav */}
        </div>
      </div>

      {/* ── Image panels ── */}
      <div className="dsv-panels">
        {/* Raw CT */}
        <div className="dsv-panel">
          <div className="dsv-panel-label">Raw CT</div>
          {currentSlice?.raw ? (
            <img
              className="dsv-img"
              src={`data:image/png;base64,${currentSlice.raw}`}
              alt={`Raw slice ${sliceIdx}`}
              draggable={false}
            />
          ) : (
            <div className="dsv-placeholder">No data</div>
          )}
        </div>

        {/* Overlay */}
        <div className="dsv-panel">
          <div className="dsv-panel-label">
            Segmentation Overlay
            {isTumorSlice && (
              <span className="dsv-tumor-badge">● Tumour</span>
            )}
          </div>
          {currentSlice?.overlay ? (
            <img
              className="dsv-img"
              src={
                showOverlay
                  ? `data:image/png;base64,${currentSlice.overlay}`
                  : `data:image/png;base64,${currentSlice.raw}`
              }
              alt={`Overlay slice ${sliceIdx}`}
              draggable={false}
            />
          ) : (
            <div className="dsv-placeholder">No data</div>
          )}
        </div>
      </div>

      {/* ── Slider ── */}
      <div className="dsv-slider-wrap">
        <button className="dsv-arrow" onClick={() => step(-1)} disabled={sliceIdx === 0}>
          ‹
        </button>

        <div className="dsv-slider-inner">
          <div className="dsv-tick-row">
            {Array.from(tumorSet).map((t) => (
              <div
                key={t}
                className="dsv-tick"
                style={{ left: `${(t / Math.max(nSlices - 1, 1)) * 100}%` }}
                title={`Tumour slice ${t}`}
              />
            ))}
          </div>
          <input
            ref={sliderRef}
            type="range"
            min={0}
            max={nSlices - 1}
            value={sliceIdx}
            onChange={handleSliderChange}
            className="dsv-slider"
          />
        </div>

        <button
          className="dsv-arrow"
          onClick={() => step(1)}
          disabled={sliceIdx === nSlices - 1}
        >
          ›
        </button>

        <span className="dsv-slice-label">
          Slice {sliceIdx + 1} / {nSlices}
          {isTumorSlice ? " 🔴" : ""}
        </span>
      </div>

      {/* ── Stats bar ── */}
      <div className="dsv-stats">
        <StatPill label="Liver" value={fmt(demoData?.liver_voxels)} unit="vox" color="#4ade80" />
        <StatPill label="Tumour" value={fmt(demoData?.tumor_voxels)} unit="vox" color="#f87171" />
        <StatPill
          label="Detected"
          value={demoData?.tumor_detected ? "Yes" : "No"}
          color={demoData?.tumor_detected ? "#f87171" : "#94a3b8"}
        />
        <StatPill label="Tumour slices" value={tumorSet.size} color="#fb923c" />
      </div>

      <style>{dsvStyles}</style>
    </div>
  );
}

function StatPill({ label, value, unit, color }) {
  return (
    <div className="dsv-stat-pill">
      <span className="dsv-stat-dot" style={{ background: color }} />
      <span className="dsv-stat-label">{label}</span>
      <span className="dsv-stat-val">
        {value}
        {unit ? <span className="dsv-stat-unit"> {unit}</span> : null}
      </span>
    </div>
  );
}

function fmt(n) {
  if (n == null) return "—";
  return Number(n).toLocaleString();
}

const dsvStyles = `
.dsv-root {
  display: flex;
  flex-direction: column;
  gap: 0;
  background: #0d1117;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid #1e2a3a;
  font-family: 'JetBrains Mono', 'Fira Mono', monospace;
  color: #c9d1d9;
  user-select: none;
}

.dsv-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  background: #161b22;
  border-bottom: 1px solid #1e2a3a;
  flex-wrap: wrap;
  gap: 8px;
}

.dsv-vol-name {
  font-size: 12px;
  color: #58a6ff;
  letter-spacing: 0.05em;
  font-weight: 600;
}

.dsv-controls-row {
  display: flex;
  gap: 8px;
}

.dsv-btn {
  padding: 4px 12px;
  border-radius: 6px;
  border: 1px solid #30363d;
  background: #21262d;
  color: #8b949e;
  font-size: 11px;
  cursor: pointer;
  font-family: inherit;
  transition: all 0.15s;
}

.dsv-btn:hover:not(:disabled) {
  border-color: #58a6ff;
  color: #58a6ff;
  background: #1c2e42;
}

.dsv-btn.active {
  background: #1c2e42;
  border-color: #58a6ff;
  color: #58a6ff;
}

.dsv-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.dsv-panels {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1px;
  background: #1e2a3a;
  min-height: 280px;
}

.dsv-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  background: #0d1117;
  padding: 8px;
  gap: 6px;
}

.dsv-panel-label {
  font-size: 10px;
  color: #8b949e;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  display: flex;
  align-items: center;
  gap: 6px;
}

.dsv-tumor-badge {
  color: #f87171;
  font-size: 10px;
  animation: dsv-blink 1.2s ease-in-out infinite;
}

@keyframes dsv-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.dsv-img {
  width: 100%;
  max-width: 420px;
  aspect-ratio: 1;
  object-fit: contain;
  border-radius: 4px;
  image-rendering: pixelated;
}

.dsv-placeholder {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #30363d;
  font-size: 12px;
}

.dsv-slider-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  background: #161b22;
  border-top: 1px solid #1e2a3a;
}

.dsv-slider-inner {
  flex: 1;
  position: relative;
}

.dsv-tick-row {
  position: relative;
  height: 6px;
  margin-bottom: 2px;
}

.dsv-tick {
  position: absolute;
  top: 0;
  width: 2px;
  height: 6px;
  background: #f87171;
  border-radius: 1px;
  transform: translateX(-50%);
  opacity: 0.7;
}

.dsv-slider {
  width: 100%;
  accent-color: #58a6ff;
  cursor: pointer;
  height: 4px;
}

.dsv-arrow {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 1px solid #30363d;
  background: #21262d;
  color: #8b949e;
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
  padding: 0;
  flex-shrink: 0;
}

.dsv-arrow:hover:not(:disabled) {
  border-color: #58a6ff;
  color: #58a6ff;
}

.dsv-arrow:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.dsv-slice-label {
  font-size: 11px;
  color: #8b949e;
  white-space: nowrap;
  min-width: 110px;
}

.dsv-stats {
  display: flex;
  gap: 0;
  border-top: 1px solid #1e2a3a;
  background: #0d1117;
}

.dsv-stat-pill {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border-right: 1px solid #1e2a3a;
  font-size: 11px;
}

.dsv-stat-pill:last-child {
  border-right: none;
}

.dsv-stat-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dsv-stat-label {
  color: #8b949e;
  flex: 1;
}

.dsv-stat-val {
  font-weight: 700;
  color: #c9d1d9;
}

.dsv-stat-unit {
  font-weight: 400;
  color: #6e7681;
  font-size: 10px;
}

`;

// src/components/Upload.jsx
// ------------------------------------------------------------------
// Drag-and-drop NIfTI file uploader with progress bar, validation,
// and animated feedback states.
// ------------------------------------------------------------------

import { useState, useRef, useCallback } from "react";
import { predict } from "../services/api";
import "./Upload.css";

const ACCEPTED_EXTENSIONS = [".nii", ".nii.gz"];

function isValidFile(file) {
    if (!file) return false;
    const name = file.name.toLowerCase();
    return ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext));
}

function formatBytes(bytes) {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

export default function Upload({ onResult }) {
    const [dragOver, setDragOver] = useState(false);
    const [file, setFile] = useState(null);
    const [progress, setProgress] = useState(0);
    const [phase, setPhase] = useState("idle"); // idle | uploading | processing | done | error
    const [error, setError] = useState(null);
    const [processingTime, setProcessingTime] = useState(null);
    const inputRef = useRef(null);

    // ----------------------------------------------------------------
    // File selection
    // ----------------------------------------------------------------
    const handleFileSelect = useCallback((selected) => {
        setError(null);
        if (!isValidFile(selected)) {
            setError("Please upload a valid NIfTI file (.nii or .nii.gz).");
            return;
        }
        setFile(selected);
        setPhase("idle");
        setProgress(0);
    }, []);

    const onDrop = useCallback(
        (e) => {
            e.preventDefault();
            setDragOver(false);
            const dropped = e.dataTransfer.files[0];
            handleFileSelect(dropped);
        },
        [handleFileSelect]
    );

    const onInputChange = (e) => handleFileSelect(e.target.files[0]);

    // ----------------------------------------------------------------
    // Upload + inference
    // ----------------------------------------------------------------
    const handleSubmit = async () => {
        if (!file) return;
        setError(null);
        setPhase("uploading");
        setProgress(0);

        try {
            const result = await predict(file, (pct) => {
                setProgress(pct);
                if (pct === 100) setPhase("processing");
            });

            setProcessingTime(result.processing_time_s);
            setPhase("done");
            onResult(result);
        } catch (err) {
            setPhase("error");
            setError(err.message || "An unexpected error occurred.");
        }
    };

    const reset = () => {
        setFile(null);
        setPhase("idle");
        setProgress(0);
        setError(null);
        setProcessingTime(null);
        if (inputRef.current) inputRef.current.value = "";
    };

    // ----------------------------------------------------------------
    // Render helpers
    // ----------------------------------------------------------------
    const isLoading = phase === "uploading" || phase === "processing";

    const phaseLabel = {
        idle: file ? "Ready to analyse" : "Drop a scan here",
        uploading: `Uploading … ${progress}%`,
        processing: "Model is running inference …",
        done: "Analysis complete",
        error: "Error",
    }[phase];

    return (
        <div className="upload-wrapper">
            {/* Drop zone */}
            <div
                className={`drop-zone ${dragOver ? "drag-over" : ""} ${file ? "has-file" : ""
                    } ${phase === "error" ? "has-error" : ""}`}
                onDragOver={(e) => {
                    e.preventDefault();
                    setDragOver(true);
                }}
                onDragLeave={() => setDragOver(false)}
                onDrop={onDrop}
                onClick={() => !file && inputRef.current?.click()}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
                aria-label="File upload area"
            >
                <input
                    ref={inputRef}
                    type="file"
                    accept=".nii,.nii.gz"
                    className="hidden-input"
                    onChange={onInputChange}
                    aria-hidden="true"
                />

                {/* Icon */}
                <div className="drop-icon">
                    {phase === "done" ? (
                        <CheckIcon />
                    ) : phase === "error" ? (
                        <ErrorIcon />
                    ) : (
                        <ScanIcon active={isLoading} />
                    )}
                </div>

                {/* Labels */}
                <p className="drop-phase-label">{phaseLabel}</p>

                {file && phase === "idle" && (
                    <p className="file-meta">
                        {file.name} &nbsp;·&nbsp; {formatBytes(file.size)}
                    </p>
                )}

                {phase === "done" && processingTime !== null && (
                    <p className="file-meta">
                        Processed in {processingTime.toFixed(1)} s
                    </p>
                )}
            </div>

            {/* Progress bar */}
            {(phase === "uploading" || phase === "processing") && (
                <div className="progress-bar-track">
                    <div
                        className={`progress-bar-fill ${phase === "processing" ? "indeterminate" : ""
                            }`}
                        style={{ width: phase === "uploading" ? `${progress}%` : "100%" }}
                    />
                </div>
            )}

            {/* Error message */}
            {error && (
                <div className="error-banner" role="alert">
                    <ErrorIcon small />
                    <span>{error}</span>
                </div>
            )}

            {/* Action buttons */}
            <div className="upload-actions">
                {file && phase === "idle" && (
                    <button className="btn btn-primary" onClick={handleSubmit}>
                        Run Segmentation
                    </button>
                )}
                {(phase === "done" || phase === "error") && (
                    <button className="btn btn-secondary" onClick={reset}>
                        Upload Another Scan
                    </button>
                )}
                {!file && phase === "idle" && (
                    <button
                        className="btn btn-outline"
                        onClick={() => inputRef.current?.click()}
                    >
                        Browse Files
                    </button>
                )}
            </div>
        </div>
    );
}

// ----------------------------------------------------------------
// Inline SVG icons
// ----------------------------------------------------------------
function ScanIcon({ active }) {
    return (
        <svg
            className={`icon-scan ${active ? "spinning" : ""}`}
            viewBox="0 0 64 64"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
        >
            <rect x="8" y="8" width="48" height="48" rx="6" stroke="currentColor" strokeWidth="2.5" strokeDasharray="8 4" />
            <path d="M20 32h24M32 20v24" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
            <circle cx="32" cy="32" r="5" stroke="currentColor" strokeWidth="2.5" />
        </svg>
    );
}

function CheckIcon() {
    return (
        <svg className="icon-check" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="32" cy="32" r="24" stroke="currentColor" strokeWidth="2.5" />
            <path d="M20 33l9 9 16-18" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
    );
}

function ErrorIcon({ small }) {
    return (
        <svg
            className={small ? "icon-error-small" : "icon-error"}
            viewBox="0 0 64 64"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
        >
            <circle cx="32" cy="32" r="24" stroke="currentColor" strokeWidth="2.5" />
            <path d="M32 20v16M32 42v2" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
        </svg>
    );
}
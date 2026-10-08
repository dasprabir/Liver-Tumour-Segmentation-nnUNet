import { useEffect, useState } from "react";
import { getDemoViewer } from "../services/api";

export default function DemoResult() {

    const [result, setResult] = useState(null);

    const params = new URLSearchParams(window.location.search);
    const caseId = params.get("case");

    useEffect(() => {

        async function load() {

            const r = await fetch(
                `http://localhost:8000/demo/result/${caseId}`
            );

            const data = await r.json();
            setResult(data);
        }

        load();

    }, [caseId]);

    if (!result) return null;

    return (
        <div className="result-page">

            <div className="result-container">

                <iframe
                    src={getDemoViewer(caseId)}
                    className="demo-iframe"
                />

                <div className="result-stats-row">

                    <StatChip
                        label="Liver voxels"
                        value={result.liver_voxels?.toLocaleString()}
                        color="#32dcc8"
                    />

                    <StatChip
                        label="Tumour voxels"
                        value={result.tumor_voxels?.toLocaleString()}
                        color="#ff4040"
                    />

                    <StatChip
                        label="Tumour slices"
                        value={result.tumor_slice_indices?.length}
                        color="#f59e0b"
                    />

                    <StatChip
                        label="Total slices"
                        value={result.n_slices}
                        color="#94a3b8"
                    />

                </div>

            </div>

        </div>
    );
}

function StatChip({ label, value, color }) {
    return (
        <div className="stat-chip">
            <span
                className="stat-chip-dot"
                style={{ background: color }}
            />
            <span className="stat-chip-val">{value}</span>
            <span className="stat-chip-label">{label}</span>
        </div>
    );
}
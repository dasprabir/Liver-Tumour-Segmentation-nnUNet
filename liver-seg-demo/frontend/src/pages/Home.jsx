import { useState } from "react";
import Upload from "../components/Upload";
import SliceViewer from "../components/SliceViewer";
import "../styles/Home.css";

export default function Home() {

    const [view, setView] = useState("upload");
    const [result, setResult] = useState(null);

    const handleResult = (data) => {
        setResult(data);
        setView("result");
    };

    const handleReset = () => {
        setResult(null);
        setView("upload");
    };

    return (
        <div className="home-root">

            <header className="app-header">
                <div className="header-inner">

                    <div className="logo">
                        <span className="logo-text">
                            Liver<span className="logo-accent">Seg</span>
                        </span>
                    </div>

                    {view === "result" && (
                        <button className="nav-btn" onClick={handleReset}>
                            ← New Scan
                        </button>
                    )}

                </div>
            </header>

            {view === "upload" && (
                <main className="home-main">
                    <div className="upload-page">

                        <h1 className="hero-title">
                            Liver Tumour<br />
                            <span className="hero-accent">
                                Segmentation
                            </span>
                        </h1>

                        <div className="upload-card">
                            <Upload onResult={handleResult} />
                        </div>

                    </div>
                </main>
            )}

            {view === "result" && result && (
                <main className="home-main">

                    <div className="result-page">

                        <h2 className="result-title">
                            Segmentation Result
                        </h2>

                        <SliceViewer
                            sessionId={result.session_id}
                            nSlices={result.n_slices}
                            tumorSliceIndices={result.tumor_slice_indices}
                            volumeName={result.volume_name}
                            liverVoxels={result.liver_voxels}
                            tumorVoxels={result.tumor_voxels}
                        />

                    </div>

                </main>
            )}

        </div>
    );
}
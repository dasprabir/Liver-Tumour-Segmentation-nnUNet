import { useState } from "react";
import { uploadDemo, getDemoViewer } from "../services/api";
import "../pages/Home.css";

export default function Demo() {

    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    const handleFile = async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        setError("");
        setLoading(true);

        try {
            const res = await uploadDemo(file);

            // Open the combined tabbed HTML viewer directly
            window.open(
                `http://localhost:8000/demo/viewer/${res.session_id}`,
                "_blank"
            );

            setLoading(false);

        } catch (err) {
            setError(err.message);
            setLoading(false);
        }
    };

    return (
        <div className="home-root">

            <header className="app-header">
                <div className="header-inner">
                    <div className="logo">
                        Liver<span className="logo-accent">Seg</span>
                        <span style={{marginLeft:8,fontSize:"0.7rem"}}>
                            Demo
                        </span>
                    </div>

                    <nav className="header-nav">
                        <a href="/" className="nav-link">
                            Live Mode
                        </a>
                    </nav>
                </div>
            </header>

            <main className="home-main">

                <div className="upload-page">

                    <div className="hero-text">
                        <h1 className="hero-title">
                            Demo Mode<br/>
                            <span className="hero-accent">
                                Upload Sample Case
                            </span>
                        </h1>

                        <p className="hero-sub">
                            Upload a demo CT scan.
                            Results load instantly.
                        </p>
                    </div>

                    <div className="upload-card">

                        <label className="btn btn-primary">
                            {loading ? "Loading..." : "Choose .nii file"}
                            <input
                                type="file"
                                accept=".nii,.nii.gz"
                                onChange={handleFile}
                                style={{ display: "none" }}
                            />
                        </label>

                        {error && (
                            <div className="error-banner">
                                {error}
                            </div>
                        )}

                    </div>

                </div>

            </main>

        </div>
    );
}
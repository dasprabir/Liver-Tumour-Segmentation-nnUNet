import { useRef, useState } from "react";
import { upload } from "../services/api";

export default function Upload({ onResult }) {

    const inputRef = useRef();
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    const handleFile = async (file) => {
        if (!file) return;

        setError("");
        setLoading(true);

        try {
            const res = await upload(file);

            if (res.error) {
                setError(res.error);
                setLoading(false);
                return;
            }

            // use case id directly
            const caseId = res.session_id;

            // fetch JSON
            const r = await fetch(
                `http://localhost:8001/result/${caseId}`
            );

            const data = await r.json();

            // ensure correct session id
            data.session_id = caseId;

            // viewer url
            data.viewer_url =
                `http://localhost:8001/viewer/${caseId}`;

            onResult(data);

        } catch (e) {
            setError("Upload failed");
        }

        setLoading(false);
    };

    const onChange = (e) => {
        const file = e.target.files[0];
        handleFile(file);
    };

    return (
        <div className="upload-box">

            <input
                type="file"
                accept=".nii,.nii.gz"
                ref={inputRef}
                onChange={onChange}
                hidden
            />

            <button
                onClick={() => inputRef.current.click()}
                disabled={loading}
                className="upload-btn"
            >
                {loading ? "Loading..." : "Choose Files"}
            </button>

            {error && (
                <div className="upload-error">
                    {error}
                </div>
            )}

        </div>
    );
}
import { useState } from "react";
import Upload from "../components/Upload";

export default function Demo() {

    const [session, setSession] = useState(null);

    if (!session) {
        return (
            <div className="upload-page">
                <Upload onResult={(r) => setSession(r.session_id)} />
            </div>
        );
    }

    return (
        <iframe
            src={`http://localhost:8001/viewer/${session}`}
            style={{
                width: "100%",
                height: "100vh",
                border: "none"
            }}
        />
    );
}
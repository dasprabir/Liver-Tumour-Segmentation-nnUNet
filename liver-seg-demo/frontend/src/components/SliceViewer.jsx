import "../styles/SliceViewer.css";

export default function SliceViewer({
    sessionId,
    nSlices,
    tumorSliceIndices,
    liverVoxels,
    tumorVoxels
}) {

    const tumorSlices = tumorSliceIndices?.length || 0;

    return (
        <div className="sv-root">

            <iframe
                src={`http://localhost:8001/viewer/${sessionId}`}
                className="sv-iframe"
                title="Demo Viewer"
            />

            <div className="sv-stats">

                <div className="sv-card">
                    <span className="dot liver"></span>
                    {liverVoxels?.toLocaleString()} Liver voxels
                </div>

                <div className="sv-card">
                    <span className="dot tumor"></span>
                    {tumorVoxels?.toLocaleString()} Tumour voxels
                </div>

                <div className="sv-card">
                    <span className="dot slices"></span>
                    {tumorSlices} Tumour slices
                </div>

                <div className="sv-card">
                    <span className="dot total"></span>
                    {nSlices} Total slices
                </div>

            </div>

        </div>
    );
}
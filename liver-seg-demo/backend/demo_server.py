import os
import shutil
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
RESULTS_DIR = os.path.join(BASE_DIR, "resultsTs")
TEMP_DIR = os.path.join(BASE_DIR, "temp")

os.makedirs(TEMP_DIR, exist_ok=True)


# ---------------- upload ----------------
@app.post("/upload")
async def upload(file: UploadFile = File(...)):

    filename = file.filename.lower().strip()

    case = filename.replace(".nii.gz", "").replace(".nii", "")
    case = case.replace("_0000", "")

    json_path = os.path.join(RESULTS_DIR, f"{case}_results.json")
    html_path = os.path.join(RESULTS_DIR, f"{case}_slider.html")

    if not os.path.exists(json_path) or not os.path.exists(html_path):
        return JSONResponse(
            {"error": f"Demo not found for {case}"},
            status_code=404
        )

    return {
        "session_id": case,
        "status": "done"
    }

# ---------------- result json ----------------
@app.get("/result/{case}")
def get_result(case: str):
    path = os.path.join(RESULTS_DIR, f"{case}_results.json")
    return FileResponse(path, media_type="application/json")


# ---------------- viewer html ----------------
@app.get("/viewer/{case}")
def get_viewer(case: str):
    path = os.path.join(RESULTS_DIR, f"{case}_slider.html")

    if not os.path.exists(path):
        return JSONResponse(
            {"error": f"viewer not found for {case}"},
            status_code=404
        )

    return FileResponse(path, media_type="text/html")


# dummy endpoints so frontend doesn't crash
@app.get("/slice/{case}/{z}")
def slice_overlay(case: str, z: int):
    return JSONResponse({"demo": True})


@app.get("/slice-raw/{case}/{z}")
def slice_raw(case: str, z: int):
    return JSONResponse({"demo": True})


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
# LiverSeg — Liver Tumour Segmentation Web App

A web-based liver and tumour segmentation system built using **nnUNet 2D (4-fold ensemble)** with an interactive slice viewer, demo mode, and 3D mesh visualization.

Upload a CT scan (`.nii` / `.nii.gz`) and the system automatically:

* Segments liver and tumour
* Displays dual-panel slice viewer
* Shows tumour statistics
* Generates 3D meshes
* Allows standalone export
* Supports instant demo mode

---

# Features

### Segmentation

* nnUNet v2 2D model
* 4-fold ensemble inference
* Liver + tumour segmentation
* GPU acceleration (optional)

### Viewer

* Dual panel CT slice viewer
* Raw CT + segmentation overlay
* Tumour slice detection
* Slider navigation
* Lazy slice loading

### 3D

* Marching cubes mesh generation
* Three.js interactive viewer
* Liver / tumour toggle
* Opacity control
* Auto rotate

### Demo Mode

* No inference required
* Loads precomputed results
* Works without GPU
* Instant loading

### Export

* Standalone HTML viewer
* Save CT + mask
* JSON metadata

---

# Complete Project Structure

```
liver-seg/
│
├── backend/
│   ├── main.py
│   ├── inference.py
│   ├── mesh_generator.py
│   ├── session_store.py
│   ├── save_demo.py
│   ├── config.py
│   │
│   ├── requirements.txt
│   ├── requirements-demo.txt
│   │
│   ├── run_demo.bat
│   ├── setup_demo.bat
│   │
│   ├── resultsTs/
│   ├── sessions/        (generated)
│   ├── temp/            (generated)
│   │
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Upload.jsx
│   │   │   ├── Upload.css
│   │   │   ├── SliceViewer.jsx
│   │   │   ├── SliceViewer.css
│   │   │   ├── Viewer3D.jsx
│   │   │   └── Viewer3D.css
│   │   │
│   │   ├── pages/
│   │   │   ├── Home.jsx
│   │   │   ├── Home.css
│   │   │   ├── Demo.jsx
│   │   │   ├── DemoResult.jsx
│   │   │   ├── Beta3D.jsx
│   │   │   └── Beta3D.css
│   │   │
│   │   ├── services/
│   │   │   └── api.js
│   │   │
│   │   ├── App.jsx
│   │   ├── App.css
│   │   └── main.jsx
│   │
│   ├── index.html
│   ├── package.json
│   ├── package-lock.json
│   └── vite.config.js
│
├── run.bat
├── setup_full.bat
├── .gitignore
└── README.md
```

---

# How The App Works

### Step 1 — Upload CT

User uploads `.nii.gz` file from UI.

Upload component sends:

POST /predict

---

### Step 2 — Backend receives file

`main.py`

* saves CT
* creates session
* calls inference

---

### Step 3 — nnUNet inference

`inference.py`

Runs:

nnUNetv2_predict

Output labels:
0 = background
1 = liver
2 = tumour

---

### Step 4 — session created

`session_store.py`

Stores:

* ct path
* pred path
* metadata
* slice info
* voxel counts

---

### Step 5 — slice viewer loads

Frontend requests:

GET /slice/{session}/{z}
GET /slice-raw/{session}/{z}

Slices loaded lazily.

---

### Step 6 — mesh generated

`mesh_generator.py`

Uses:

* marching cubes
* smoothing
* mesh cleanup

Returns:

vertices
faces

---

### Step 7 — 3D viewer

Viewer3D.jsx renders:

* liver mesh
* tumour mesh
* orbit controls

---

# Demo Mode

Demo mode loads precomputed results.

No inference.

Workflow:

Upload file
↓
/demo/upload
↓
load saved result
↓
open demo viewer

Instant loading.

---

# Frontend Routes

/
Main segmentation page

/demo
Demo upload page

/demo-result
Demo viewer

/beta-3d
3D viewer page

---

# Backend API

POST /predict

GET /slice/{session}/{z}

GET /slice-raw/{session}/{z}

GET /mesh/{session}

GET /save-results/{session}

Demo:

POST /demo/upload

GET /demo/viewer/{case}

GET /demo/result/{case}

---

# Installation

## Requirements

Python 3.9+
Node.js 18+

Optional:
CUDA GPU

---

# First Time Setup

Run:

setup_full.bat

This installs:

* Python venv
* PyTorch
* nnUNet
* FastAPI
* React deps

---

# Running The App

Run:

run.bat

Frontend:
http://localhost:5173

Backend:
http://localhost:8000

Docs:
http://localhost:8000/docs

---

# Using The App

### Live Mode

1 Upload CT
2 Wait for inference
3 View slices
4 View 3D
5 Save results

---

### Demo Mode

Open:

http://localhost:5173/demo

Upload sample CT

Results load instantly.

---

# 3D Viewer

Open:

View in 3D

or

/beta-3d?session=ID

Controls:

Mouse drag → rotate
Scroll → zoom
Right click → pan

---

# Export Results

Click:

Save Results

Exports:

HTML viewer
CT NIfTI
Mask NIfTI
JSON stats

---

# Model Details

Model: nnUNet v2
Architecture: 2D
Ensemble: 4 fold

Dataset: MSD Task03 Liver

Performance:

Liver Dice: 0.9694
Tumour Dice: 0.8010

---

# Generated Folders

Do not commit:

backend/temp/
backend/sessions/
frontend/node_modules/
venv/

---

# Notes

Research use only
Not for clinical use

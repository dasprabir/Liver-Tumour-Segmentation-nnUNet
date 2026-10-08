# LiverSeg Demo — Liver Tumor Segmentation (Precomputed)

This is a **demo version** of the LiverSeg web application.
It loads **precomputed segmentation results** instead of running model inference, allowing **instant visualization**.

---

# Features

* Upload `.nii` CT volume
* Loads **precomputed segmentation**
* Interactive slice viewer
* Liver + tumor overlay
* Tumor slice navigation
* Zero inference (instant demo)
* Portable (runs without Conda)

---

# Project Structure

```
liver-seg-demo/
│
├── backend/
│   ├── demo_server.py
│   ├── requirements.txt
│   └── venv/ (auto-created)
│
├── frontend/
│   ├── src/
│   ├── package.json
│   └── vite.config.js
│
├── resultsTs/
│   liver_132_results.json
│   liver_132_slider.html
│   ...
│
├── run-demo-setup.bat
├── run-demo-env.bat
└── README.md
```

---

# Requirements

Install before running:

* Python 3.9+
* Node.js 18+
* Windows (bat scripts)

No Conda required.

---

# First-Time Setup

Run once:

```
run-demo-setup.bat
```

This will:

* create Python virtual environment
* install FastAPI dependencies
* install frontend dependencies

---

# Run Demo

After setup:

```
run-demo-env.bat
```

This will start:

* backend (FastAPI)
* frontend (Vite React app)

Open:

```
http://localhost:5174/demo
```

---

# How Demo Works

When you upload:

```
liver_132_0000.nii
```

The demo loads:

```
resultsTs/liver_132_results.json
resultsTs/liver_132_slider.html
```

No model inference is performed.

---

# Supported Demo Files

Filename format must match:

```
<case>_0000.nii
```

Example:

```
liver_132_0000.nii
```

Requires:

```
liver_132_results.json
liver_132_slider.html
```

---

# Backend API

Endpoints:

POST

```
/upload
```

GET

```
/result/{session}
```

GET

```
/slice/{session}/{z}
```

GET

```
/slice-raw/{session}/{z}
```

---

# Notes

* Demo mode only loads saved results
* No GPU required
* No model files required
* Works offline

---

# Troubleshooting

### "Demo not found"

Ensure results exist:

```
resultsTs/liver_XXX_results.json
```

### Python not found

Install Python and restart terminal

### Port already in use

Close existing backend/frontend terminals

---

# Demo Mode vs Full Mode

Demo version:

* loads precomputed results
* instant visualization

Full version:

* runs nnUNet inference
* slower but real prediction

---

# Author

LiverSeg — Liver Tumor Segmentation Viewer

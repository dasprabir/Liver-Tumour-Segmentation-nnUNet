# Liver Segmentation Using Deep Learning

A full-stack web application for automated liver and hepatic tumour segmentation from CT volumes, powered by a four-fold nnU-Net 2D ensemble trained on the Medical Segmentation Decathlon Task03 Liver dataset.

> **Paper:** *Liver Tumor Segmentation Using Deep Learning: A 2.5D U-Net Baseline and nnU-Net 2D Ensemble*

---

## Results

| Model | Liver Dice | Tumour Dice (24 positive cases) |
|---|---|---|
| 2.5D U-Net baseline | 0.8327 | 0.7139 |
| nnU-Net Fold 0 | 0.9586 | 0.6767 |
| Ensemble [0,1] | 0.9668 | 0.7514 |
| Ensemble [0,1,2] | 0.9684 | 0.7839 |
| **Ensemble [0,1,2,3]** | **0.9694** | **0.8010** |
| MSD Challenge median | ~0.95 | ~0.70 |

Trained on a consumer-grade GPU (NVIDIA RTX 4060, 8 GB VRAM, Windows 11).

---

## Project Structure

```
liver-seg-v2/
├── backend/
│   ├── config.py           # Model and app configuration
│   ├── inference.py        # nnU-Net inference pipeline
│   ├── main.py             # FastAPI application entrypoint
│   ├── mesh_generator.py   # 3D mesh generation for viewer
│   ├── save_demo.py        # Demo result saving utility
│   ├── session_store.py    # Session management
│   ├── requirements.txt    # Full dependencies
│   ├── requirements-demo.txt
│   ├── Dockerfile
│   ├── run_demo.bat
│   └── setup_demo.bat
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── SliceViewer.jsx     # 2D axial slice viewer
│   │   │   ├── Viewer3D.jsx        # 3D mesh viewer
│   │   │   ├── Upload.jsx          # CT upload interface
│   │   │   └── DemoSliceViewer.jsx
│   │   ├── pages/
│   │   │   ├── Home.jsx            # Landing page
│   │   │   ├── Demo.jsx            # Demo mode
│   │   │   ├── DemoResult.jsx      # Demo results viewer
│   │   │   └── Beta3D.jsx          # 3D beta viewer
│   │   ├── services/
│   │   │   └── api.js              # Backend API calls
│   │   └── App.jsx
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── notebooks/              # Training & evaluation notebooks
├── run.bat                 # One-click run script
├── setup_full.bat          # Full environment setup
└── README.md
```

---

## Setup & Running

### Prerequisites

- Python 3.10+
- Node.js 18+
- NVIDIA GPU with CUDA (8 GB VRAM recommended)
- Windows 11 or Linux

### Quick Start (Windows)

```bat
# 1. Install all dependencies
setup_full.bat

# 2. Run the app
run.bat
```

The frontend will be available at `http://localhost:5173` and the backend at `http://localhost:8000`.

### Manual Setup

**Backend:**
```bash
cd backend
pip install -r requirements.txt
python main.py
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

---

## Model Weights

Pre-trained nnU-Net 2D fold checkpoints are not included in this repository due to file size.

**Download:** *(add your link here — Google Drive / HuggingFace / Zenodo)*

Place the downloaded weights at:
```
backend/models/nnUNet_results/Dataset003_Liver/nnUNetTrainer__nnUNetPlans__2d/
```

---

## Windows-Specific Notes (nnU-Net)

Running nnU-Net on Windows requires the following environment variables to avoid OOM and multiprocessing crashes:

```bat
set nnUNet_n_proc_DA=2
set NNUNET_COMPILE=0
```

Also set `num_workers=0` in the DataLoader config. These are not documented in the official nnU-Net repo but are required on Windows 11 with PyTorch 2.x.

---

## Architecture

**2.5D U-Net baseline** — three stacked axial slices as input, four encoder stages (64→512), dropout bottleneck, Focal + Dice loss, trained for 100 epochs.

**nnU-Net 2D ensemble** — 8-stage PlainConvUNet with InstanceNorm and LeakyReLU, 512×512 patches, four cross-validation folds trained for 500 epochs each. Inference averages softmax probabilities across all four folds.

---

## Dataset

[Medical Segmentation Decathlon — Task03 Liver](http://medicaldecathlon.com/)

- 131 labelled + 70 unlabelled contrast-enhanced CT volumes
- Labels: background (0), liver (1), tumour (2)
- Background-to-tumour voxel ratio: ~2500:1

---

## Citation

If you use this work, please cite:

```
@article{liver_seg_2026,
  title   = {Liver Tumor Segmentation Using Deep Learning: A 2.5D U-Net Baseline and nnU-Net 2D Ensemble},
  year    = {2026}
}
```

---

## License

MIT License

# Revela - Video & Image to 3D Reconstruction Platform

A modular, device-agnostic 3D reconstruction platform that converts video streams and image sets into high-quality 3D models using neural rendering (NeRFs and 3D Gaussian Splatting).

## What It Does

Revela accepts **video files** and/or **image sets** from consumer devices (iPhones, cameras) and professional medical devices (endoscopes, laparoscopes) and produces 3D reconstructions using Nerfstudio-based pipelines.

**Pipeline:**
```
Video / Images
    |
[Preprocessing] --> Frame extraction (video) or quality filtering (images)
    |
[COLMAP] ----------> Camera pose estimation (SfM)
    |
[Nerfstudio] ------> NeRF or 3D Gaussian Splatting training
    |
3D Outputs (PLY point clouds, meshes, splats)
```

## Project Status

### Phase 1: Core Engine -- In Progress

| Component | Status | Notes |
|-----------|--------|-------|
| Configuration system | Done | YAML + Pydantic, env var overrides |
| Reconstruction engine | Done | Nerfstudio wrapper (nerfacto, splatfacto) |
| Video preprocessing | Done | FFmpeg extraction, quality filtering |
| Image ingestion | Done | Direct image set input with quality filtering |
| COLMAP pose estimation | Done | SfM with mock-pose fallback |
| E2E test script | Done | `test_reconstruction.py` |
| FastAPI service | Not started | Planned |
| Celery job queue | Not started | Planned |
| MinIO / Postgres storage | Not started | Planned |

### Phase 2: API & Workers (Planned)
- FastAPI REST/WebSocket endpoints
- Celery async job processing
- PostgreSQL job metadata, Redis queue
- MinIO object storage

### Phase 3: Frontend (Planned)
- React + TypeScript UI
- Three.js 3D viewer
- Video/image upload interface
- Measurement tools

### Phase 4: Production (Planned)
- Docker Compose orchestration
- Multi-GPU support, streaming mode
- HIPAA-aligned security, monitoring

## Tech Stack

**Backend:** Python 3.11+, PyTorch 2.0+, Nerfstudio, COLMAP, OpenCV, FFmpeg
**Config:** YAML + Pydantic validation
**Planned:** FastAPI, Celery + Redis, PostgreSQL, MinIO, React + Three.js

## Quick Start

```bash
# 1. Setup
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install nerfstudio
conda install -c conda-forge colmap

# 2. Verify
python test_imports.py

# 3. Reconstruct from video
python test_reconstruction.py --video path/to/video.mp4 --quick

# 4. Or reconstruct from images
python test_reconstruction.py --image-dir path/to/images/ --quick
```

Results are saved to `data/cache/job_<id>/exports/`.

View `.ply` files with [CloudCompare](https://www.cloudcompare.org/), [MeshLab](https://www.meshlab.net/), or Blender.

## Input Requirements

### Video
- 5-30 seconds, 720p+, smooth camera motion
- Circle around the subject for 360 coverage
- Good lighting, textured surfaces

### Images
- 20-300 images with significant overlap between views
- Consistent lighting and resolution
- Supported formats: `.jpg`, `.jpeg`, `.png`, `.tiff`, `.bmp`

## Project Structure

```
revela/
├── backend/
│   ├── config/
│   │   ├── default.yaml             # All configuration
│   │   └── config_loader.py         # Pydantic config management
│   ├── engine/
│   │   ├── base.py                  # Abstract interfaces & data models
│   │   └── nerfstudio_wrapper.py    # Nerfstudio integration
│   ├── preprocessing/
│   │   ├── video_processor.py       # Video frame extraction
│   │   ├── image_processor.py       # Image set ingestion
│   │   ├── colmap_estimator.py      # COLMAP pose estimation
│   │   ├── colmap_wrapper.py        # COLMAP wrapper (used by test script)
│   │   └── base.py                  # Shared types
│   ├── storage/                     # Storage interfaces (stub)
│   ├── test_imports.py              # Import validation
│   ├── test_reconstruction.py       # E2E pipeline test
│   └── requirements.txt
├── data/
│   ├── uploads/                     # Input videos/images
│   ├── outputs/                     # Generated 3D models
│   └── cache/                       # Intermediate processing
├── docs/
│   ├── SETUP.md                     # Detailed installation guide
│   └── USAGE.md                     # Detailed usage guide
└── quickstart.ps1                   # Windows setup helper
```

## Configuration

All settings live in `backend/config/default.yaml`:

```yaml
reconstruction:
  default_method: "splatfacto"   # or "nerfacto"
  max_iterations: 30000
  resolution: 1024

preprocessing:
  frame_extraction:
    fps: 10
    max_frames: 300
  image_ingestion:
    supported_formats: [".jpg", ".jpeg", ".png", ".tiff", ".bmp"]
    max_images: 500
  quality_filter:
    enabled: true
    min_sharpness: 10.0
```

Override any setting via environment variables: `VIDEO3D_RECONSTRUCTION_MAX_ITERATIONS=5000`.

## Key Design Decisions

1. **Modular engine** -- Abstract `ReconstructionEngine` base class allows swapping Nerfstudio for custom models
2. **Dual input** -- Accepts both video files and pre-captured image sets
3. **COLMAP with fallback** -- Uses real SfM when available, mock poses for development
4. **Configuration-driven** -- YAML config, no hardcoded values, environment overrides

## Documentation

- [Setup Guide](docs/SETUP.md) -- Detailed installation for all platforms
- [Usage Guide](docs/USAGE.md) -- Workflows, configuration tuning, troubleshooting

## Hardware Requirements

- NVIDIA GPU with 8GB+ VRAM (tested on RTX 3070 Ti)
- 16GB+ RAM, 50GB+ storage
- CUDA 11.8+, Python 3.11+, FFmpeg

## References

- [Nerfstudio](https://docs.nerf.studio/)
- [COLMAP](https://colmap.github.io/)
- [3D Gaussian Splatting (Kerbl et al., SIGGRAPH 2023)](https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/)
- [NeRF (Mildenhall et al., ECCV 2020)](https://www.matthewtancik.com/nerf)

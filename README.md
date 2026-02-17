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

### Phase 1: Core Engine -- Done

| Component | Status |
|-----------|--------|
| Configuration system (YAML + Pydantic) | Done |
| Reconstruction engine (Nerfstudio nerfacto/splatfacto) | Done |
| Video preprocessing (FFmpeg, quality filtering) | Done |
| Image ingestion (direct image set input) | Done |
| COLMAP pose estimation (SfM) | Done |
| E2E test script | Done |

### Phase 2: API & Workers -- Done

| Component | Status |
|-----------|--------|
| FastAPI REST API (upload, status, download) | Done |
| Celery async worker (GPU task queue) | Done |
| Job metadata store (SQLite, swappable to Postgres) | Done |
| File store (local filesystem, upload/output management) | Done |
| Docker Compose (Redis + API + GPU Worker) | Done |
| Dockerfile (CUDA 11.8 + Nerfstudio) | Done |

### Phase 3: Frontend (Planned)
- React + TypeScript UI
- Three.js 3D viewer
- Video/image upload interface
- Measurement tools

### Phase 4: Production Hardening (Planned)
- Multi-GPU support, streaming mode
- HIPAA-aligned security, monitoring
- Postgres migration, MinIO object storage

## Tech Stack

**Backend:** Python 3.11+, PyTorch 2.0+, Nerfstudio, COLMAP, OpenCV, FFmpeg
**API:** FastAPI, Celery + Redis, SQLite
**Infrastructure:** Docker, Docker Compose, NVIDIA CUDA

## Quick Start

### Option A: Local Development

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install nerfstudio
conda install -c conda-forge colmap

# Verify
python test_imports.py

# Reconstruct from video
python test_reconstruction.py --video path/to/video.mp4 --quick

# Or from images
python test_reconstruction.py --image-dir path/to/images/ --quick
```

### Option B: API Server (requires Redis)

```bash
# Start Redis
docker run -d -p 6379:6379 redis:7-alpine

# Start API server
cd backend
uvicorn api.main:app --reload --port 8000

# Start worker (separate terminal)
cd backend
celery -A workers.celery_app worker --loglevel=info -Q gpu --concurrency=1
```

Then upload via the API:
```bash
# Upload video and create job
curl -X POST http://localhost:8000/api/jobs \
  -F "video=@my_video.mp4" \
  -F "method=splatfacto"

# Check status
curl http://localhost:8000/api/jobs/{job_id}

# List outputs
curl http://localhost:8000/api/jobs/{job_id}/outputs

# Download result
curl -O http://localhost:8000/api/jobs/{job_id}/outputs/pointcloud.ply
```

### Option C: Docker Compose

```bash
docker compose up -d
# API at http://localhost:8000
# Health check: http://localhost:8000/health
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/api/jobs` | Create job (upload video/images) |
| `GET` | `/api/jobs` | List all jobs |
| `GET` | `/api/jobs/{id}` | Get job status |
| `DELETE` | `/api/jobs/{id}` | Delete job and files |
| `GET` | `/api/jobs/{id}/outputs` | List output files |
| `GET` | `/api/jobs/{id}/outputs/{file}` | Download output file |

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
│   ├── api/
│   │   ├── main.py                  # FastAPI application
│   │   └── routes.py                # REST endpoints
│   ├── workers/
│   │   ├── celery_app.py            # Celery configuration
│   │   └── tasks.py                 # Reconstruction task
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
│   │   └── colmap_wrapper.py        # COLMAP wrapper
│   ├── storage/
│   │   └── __init__.py              # JobStore (SQLite) + FileStore
│   ├── test_imports.py
│   ├── test_reconstruction.py
│   └── requirements.txt
├── data/                            # Uploads, outputs, cache, SQLite DB
├── docs/
│   ├── SETUP.md                     # Installation guide
│   └── USAGE.md                     # Usage guide
├── Dockerfile                       # CUDA + Nerfstudio image
├── docker-compose.yml               # Redis + API + Worker
└── .dockerignore
```

## Configuration

All settings live in `backend/config/default.yaml`. Key sections:

- `reconstruction` -- method, iterations, resolution
- `preprocessing` -- FPS, max frames, image ingestion, quality filters
- `colmap` -- feature detector, matching method
- `api` -- port, CORS, upload limits
- `celery` -- broker URL, concurrency

Override via environment variables: `VIDEO3D_RECONSTRUCTION_MAX_ITERATIONS=5000`

## Documentation

- [Setup Guide](docs/SETUP.md) -- Installation for all platforms
- [Usage Guide](docs/USAGE.md) -- Workflows, configuration, troubleshooting

## Hardware Requirements

- NVIDIA GPU with 8GB+ VRAM (tested on RTX 3070 Ti)
- 16GB+ RAM, 50GB+ storage
- CUDA 11.8+, Python 3.11+, FFmpeg

## References

- [Nerfstudio](https://docs.nerf.studio/)
- [COLMAP](https://colmap.github.io/)
- [3D Gaussian Splatting (Kerbl et al., SIGGRAPH 2023)](https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/)
- [NeRF (Mildenhall et al., ECCV 2020)](https://www.matthewtancik.com/nerf)

# Video-to-3D Reconstruction Platform

A modular, device-agnostic 3D reconstruction platform that converts video streams into high-quality 3D models using neural rendering (NeRFs and 3D Gaussian Splatting).

## Overview

This platform enables:
- **Batch reconstruction** from uploaded videos (phones, cameras, medical devices)
- **Near-real-time preview** for streaming scenarios (future)
- **Medical-grade** robustness for endoscopy/laparoscopy video
- **Device-agnostic** ingestion from multiple sources

## Architecture

```
video-3d-reconstruction/
├── backend/
│   ├── api/              # FastAPI REST/WebSocket endpoints
│   ├── workers/          # Celery workers for async reconstruction
│   ├── engine/           # Nerfstudio wrapper & reconstruction core
│   ├── preprocessing/    # Video ingestion, COLMAP, SLAM
│   ├── storage/          # MinIO/S3 and Postgres interfaces
│   └── config/           # Configuration management
├── frontend/
│   ├── src/
│   │   ├── components/   # React UI components
│   │   ├── pages/        # Upload, Jobs, Viewer pages
│   │   └── viewer/       # Three.js 3D visualization
├── data/
│   ├── uploads/          # Uploaded videos
│   ├── outputs/          # Generated 3D models
│   └── cache/            # Intermediate processing data
├── docs/                 # Additional documentation
└── tests/                # Unit and integration tests
```

## Tech Stack

### Backend
- **Python 3.11**: Core language
- **FastAPI**: REST API and WebSocket server
- **Celery + Redis**: Async job queue
- **PostgreSQL**: Job metadata and configuration
- **MinIO**: S3-compatible object storage

### Reconstruction
- **PyTorch**: Deep learning framework
- **Nerfstudio**: NeRF and 3D Gaussian Splatting pipelines
- **COLMAP**: Structure-from-Motion for pose estimation
- **OpenCV**: Video processing
- **FFmpeg**: Video decoding and frame extraction

### Frontend
- **React + TypeScript**: UI framework
- **Three.js**: WebGL-based 3D rendering
- **Vite**: Build tool

## Prerequisites

### Hardware
- **GPU**: NVIDIA GPU with 8GB+ VRAM (tested on RTX 3070 Ti)
- **RAM**: 16GB+ recommended
- **Storage**: 50GB+ for videos and outputs

### Software
- **Python 3.11+**
- **Docker & Docker Compose**
- **CUDA 11.8+** (for GPU acceleration)
- **Node.js 18+** (for frontend)
- **FFmpeg** (for video processing)

### Python Dependencies
- Nerfstudio (with CUDA support)
- PyTorch 2.0+
- COLMAP (can be conda-installed)

## Quick Start

### 1. Clone and Setup

```bash
git clone <repository>
cd video-3d-reconstruction
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Test Reconstruction Engine

```bash
# Run a test reconstruction on a sample video
python -m engine.test_reconstruction --video data/uploads/sample.mp4
```

### 4. Start Services (Docker)

```bash
# Start infrastructure (Redis, Postgres, MinIO)
docker-compose up -d

# Start API server
cd backend
uvicorn api.main:app --reload

# Start worker (in another terminal)
celery -A workers.celery_app worker --loglevel=info
```

### 5. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Access the application at `http://localhost:5173`

## Development Workflow

### Phase 1: Core Engine (Current)
1. ✅ Project structure
2. 🔄 Reconstruction engine wrapper
3. 🔄 Video preprocessing pipeline
4. 🔄 COLMAP integration
5. ⏳ End-to-end test script

### Phase 2: API & Workers
1. FastAPI endpoints (upload, status, download)
2. Celery worker integration
3. Job queue management
4. Storage integration (MinIO + Postgres)

### Phase 3: Frontend
1. Video upload UI
2. Job status dashboard
3. Three.js 3D viewer
4. Measurement tools

### Phase 4: Dockerization
1. Multi-stage Docker builds
2. Docker Compose orchestration
3. Production configurations

## Key Components

### Reconstruction Engine (`backend/engine/`)
Wraps Nerfstudio to provide a consistent API for training and exporting 3D models.

**Key classes:**
- `ReconstructionEngine`: Main interface for submitting jobs
- `NerfstudioWrapper`: Handles nerfacto/splatfacto pipelines
- `ModelExporter`: Exports meshes, point clouds, depth maps

### Preprocessing (`backend/preprocessing/`)
Handles video ingestion and camera pose estimation.

**Pipeline:**
1. Frame extraction (FFmpeg)
2. Quality filtering (blur detection, exposure check)
3. Pose estimation (COLMAP)
4. Camera calibration/undistortion

### API (`backend/api/`)
FastAPI service providing REST and WebSocket endpoints.

**Endpoints:**
- `POST /api/upload`: Upload video
- `GET /api/jobs/{id}`: Job status
- `GET /api/jobs/{id}/result`: Download 3D model
- `WS /api/stream`: Streaming preview (future)

## Configuration

Configuration is managed through environment variables and YAML files:

```yaml
# config/default.yaml
reconstruction:
  default_method: "splatfacto"  # or "nerfacto"
  max_iterations: 30000
  resolution: 1024
  
preprocessing:
  frame_extraction:
    fps: 10  # Extract 10 frames per second
    max_frames: 300
  colmap:
    matcher: "sequential"
```

## Testing

```bash
# Run unit tests
pytest tests/

# Run reconstruction engine tests
pytest tests/test_engine.py

# Test with sample video
python scripts/test_end_to_end.py --video samples/test.mp4
```

## Troubleshooting

### GPU Out of Memory
- Reduce `max_iterations` in config
- Lower `resolution` setting
- Process shorter videos or fewer frames

### COLMAP Pose Estimation Fails
- Check video has sufficient camera motion
- Ensure scene has textured features (not blank walls)
- Try adjusting `frame_extraction.fps` (more/fewer frames)

### Nerfstudio Import Errors
```bash
# Verify Nerfstudio installation
ns-install-cli
python -c "import nerfstudio; print(nerfstudio.__version__)"
```

## Project Status

- ✅ Architecture defined
- 🔄 Core engine implementation (in progress)
- ⏳ API service (planned)
- ⏳ Frontend UI (planned)
- ⏳ Docker deployment (planned)

## Documentation

- [Architecture Overview](docs/architecture.md)
- [API Documentation](docs/api.md)
- [Reconstruction Engine](docs/engine.md)
- [Development Guide](docs/development.md)

## License

[TBD - Specify license]

## Contact

[TBD - Add contact information]

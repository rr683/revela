# Setup Guide

## Prerequisites

### Hardware
- NVIDIA GPU with 8GB+ VRAM (tested on RTX 3070 Ti)
- 16GB+ RAM
- 50GB+ free disk space

### Software
- Python 3.11+
- CUDA 11.8+
- FFmpeg
- Git

## Installation

### Option A: Existing Nerfstudio Environment

If you already have Nerfstudio installed:

```bash
conda activate nerfstudio

# Install COLMAP
conda install -c conda-forge colmap

# Install additional dependencies
cd backend
pip install pyyaml pydantic fastapi uvicorn celery redis minio sqlalchemy alembic

# Verify
python test_imports.py
```

### Option B: Fresh Setup

```bash
# Create environment
conda create -n revela python=3.11
conda activate revela

# Install PyTorch with CUDA
pip install torch==2.1.2 torchvision==0.16.2 --index-url https://download.pytorch.org/whl/cu118

# Verify CUDA
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"

# Install Nerfstudio
pip install nerfstudio

# Install COLMAP
conda install -c conda-forge colmap

# Install project dependencies
cd backend
pip install -r requirements.txt

# Verify
python test_imports.py
```

### FFmpeg

```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Windows (via conda)
conda install -c conda-forge ffmpeg
```

## Verify Installation

```bash
cd backend
python test_imports.py
```

Expected output:
```
✓ Importing config...
✓ Importing engine...
✓ Importing preprocessing...
  - COLMAP installed: True

All imports successful!
```

## Configuration

Edit `backend/config/default.yaml` to customize settings. Key sections:

- `reconstruction` -- method, iterations, resolution
- `preprocessing` -- FPS, max frames, quality filters, image ingestion
- `colmap` -- feature detector, matching method
- `storage` -- paths for uploads, outputs, cache

## Troubleshooting

### CUDA not available in PyTorch
```bash
nvidia-smi                  # Check GPU is detected
pip uninstall torch torchvision
pip install torch==2.1.2 torchvision==0.16.2 --index-url https://download.pytorch.org/whl/cu118
```

### COLMAP not found
```bash
conda install -c conda-forge colmap
# Or download pre-built binaries: https://github.com/colmap/colmap/releases
```

### FFmpeg errors
Ensure `ffmpeg` is on your PATH: `ffmpeg -version`

### GPU Out of Memory
Reduce settings in `backend/config/default.yaml`:
```yaml
reconstruction:
  max_iterations: 10000
  resolution: 512
preprocessing:
  frame_extraction:
    max_frames: 100
```

### Nerfstudio import errors
```bash
pip show nerfstudio          # Check it's installed
pip install --upgrade nerfstudio
ns-train --help              # Verify CLI works
```

## Performance Reference (RTX 3070 Ti, 8GB VRAM)

| Stage | Quick Mode | Full Quality |
|-------|-----------|--------------|
| Frame Extraction | ~30s | ~1min |
| COLMAP Pose Estimation | ~2min | ~5min |
| Training (splatfacto) | ~10min | ~30min |
| Export | ~1min | ~3min |
| **Total** | **~15min** | **~40min** |

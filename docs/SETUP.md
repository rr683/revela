# Setup Guide

This guide will walk you through setting up the Video-to-3D Reconstruction Platform on your Windows system with RTX 3070 Ti.

## Prerequisites

### System Requirements
- ✅ Windows 10/11
- ✅ NVIDIA RTX 3070 Ti (8GB VRAM)
- ✅ 16GB+ RAM
- ✅ 50GB+ free disk space

### Software Requirements
1. **Python 3.11**: [Download](https://www.python.org/downloads/)
2. **CUDA 11.8+**: [Download](https://developer.nvidia.com/cuda-downloads)
3. **FFmpeg**: [Download](https://ffmpeg.org/download.html)
4. **Docker Desktop**: [Download](https://www.docker.com/products/docker-desktop/)
5. **Git**: [Download](https://git-scm.com/downloads)

## Installation Steps

### 1. Install System Dependencies

#### Install CUDA Toolkit
```bash
# Download CUDA 11.8 or later
# https://developer.nvidia.com/cuda-downloads
# Follow installer instructions
```

#### Install FFmpeg
```bash
# Option 1: Using Chocolatey (recommended)
choco install ffmpeg

# Option 2: Manual installation
# Download from https://ffmpeg.org/download.html
# Add to PATH
```

#### Verify installations
```bash
python --version  # Should show 3.11.x
nvcc --version    # Should show CUDA version
ffmpeg -version   # Should show FFmpeg version
```

### 2. Set Up Python Environment

```bash
# Navigate to project
cd video-3d-reconstruction/backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate

# Upgrade pip
python -m pip install --upgrade pip
```

### 3. Install Python Dependencies

```bash
# Install base requirements
pip install -r requirements.txt

# Install PyTorch with CUDA 11.8 support
pip install torch==2.1.2 torchvision==0.16.2 --index-url https://download.pytorch.org/whl/cu118

# Verify PyTorch CUDA
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
# Should print: CUDA available: True
```

### 4. Install Nerfstudio

Nerfstudio requires special installation:

```bash
# Install Nerfstudio
pip install nerfstudio

# Install COLMAP (for pose estimation)
# Option 1: Using conda (recommended)
conda install -c conda-forge colmap

# Option 2: Build from source (advanced)
# See: https://colmap.github.io/install.html

# Verify installations
ns-train --help
colmap --version
```

### 5. Install Additional Tools (Optional)

```bash
# Install Jupyter for interactive development
pip install jupyter

# Install development tools
pip install black flake8 mypy isort
```

## Configuration

### 1. Create Data Directories

```bash
# From project root
mkdir -p data/uploads data/outputs data/cache
```

### 2. Test Configuration

```bash
cd backend
python -c "from config.config_loader import get_config; c = get_config(); print('Config loaded successfully!')"
```

## Quick Test

### 1. Prepare Test Video

Place a test video (5-30 seconds, iPhone or similar) in `data/uploads/test.mp4`

### 2. Run Test

```bash
cd backend

# Quick test (5000 iterations, ~10-15 minutes)
python test_reconstruction.py --video ../data/uploads/test.mp4 --quick

# Full test (30000 iterations, ~30-60 minutes)
python test_reconstruction.py --video ../data/uploads/test.mp4
```

Expected output:
```
================================================================================
Video-to-3D Reconstruction - End-to-End Test
================================================================================

📋 Loading configuration...
   Reconstruction method: splatfacto
   Max iterations: 5000
   Max frames: 100

🎥 Validating video...
   ✓ Valid video

🔑 Job ID: job_abc123def456
📁 Working directory: data/cache/job_abc123def456

================================================================================
Stage 1: Video Preprocessing
================================================================================
[========================================] 100.0% - Preprocessing complete

✓ Preprocessing complete
   Extracted: 100 frames
   Filtered: 95 frames
   Processed: 95 frames
   Video: 1920x1080 @ 30.0 fps

================================================================================
Stage 2: Camera Pose Estimation (COLMAP)
================================================================================
[========================================] 100.0% - Pose estimation complete

✓ Pose estimation complete
   Estimated 95 camera poses
   Camera: 1920x1080
   Focal length: fx=1500.0, fy=1500.0
   Principal point: cx=960.0, cy=540.0

================================================================================
Stage 3: 3D Reconstruction (Nerfstudio)
================================================================================
[========================================] 100.0% - Completed

✓ Reconstruction complete
   Status: completed
   Duration: 600.5 seconds

📦 Output Files:
   ply: data/cache/job_abc123def456/exports/pointcloud.ply (25.3 MB)
   mesh: data/cache/job_abc123def456/exports/mesh.ply (18.7 MB)

📊 Quality Metrics:
   Overall score: 85.0/100
   Coverage: 95.0%
   Pose confidence: 75.0/100
   Frames used: 90/95

💾 Result summary saved: data/cache/job_abc123def456/result_summary.json

================================================================================
Test Complete
================================================================================
✅ Test PASSED
```

## Troubleshooting

### Issue: CUDA not available in PyTorch

```bash
# Check CUDA installation
nvidia-smi

# Reinstall PyTorch with correct CUDA version
pip uninstall torch torchvision
pip install torch==2.1.2 torchvision==0.16.2 --index-url https://download.pytorch.org/whl/cu118
```

### Issue: COLMAP not found

```bash
# Install via conda
conda install -c conda-forge colmap

# Or download pre-built binaries
# https://github.com/colmap/colmap/releases
```

### Issue: FFmpeg errors

```bash
# Verify FFmpeg is in PATH
ffmpeg -version

# If not found, reinstall and add to PATH
```

### Issue: Out of Memory (OOM)

Edit `backend/config/default.yaml`:
```yaml
reconstruction:
  max_iterations: 10000  # Reduce from 30000
  
preprocessing:
  frame_extraction:
    max_frames: 100  # Reduce from 300
    fps: 5  # Reduce from 10
```

### Issue: Nerfstudio command not found

```bash
# Ensure virtual environment is activated
venv\Scripts\activate

# Reinstall nerfstudio
pip uninstall nerfstudio
pip install nerfstudio

# Verify
ns-train --help
```

## Next Steps

Once the test passes:

1. **Test with your own videos**: Try different video types (object scans, room captures)
2. **Tune parameters**: Experiment with different settings in `config/default.yaml`
3. **Explore outputs**: View `.ply` files in MeshLab, CloudCompare, or Blender
4. **Build the API**: Move to Phase 2 - FastAPI service and web UI

## Viewing Results

### Point Clouds (.ply)

Option 1: **CloudCompare** (Free)
- Download: https://www.cloudcompare.org/
- Open → Select .ply file

Option 2: **MeshLab** (Free)
- Download: https://www.meshlab.net/
- File → Import Mesh → Select .ply file

Option 3: **Blender** (Free)
- Download: https://www.blender.org/
- File → Import → PLY

### Gaussian Splats (.splat)

Use online viewers:
- https://antimatter15.com/splat/
- Upload your .splat file

## Performance Benchmarks

Expected performance on RTX 3070 Ti:

| Stage | Time | Memory |
|-------|------|--------|
| Frame Extraction (100 frames) | ~30s | <2GB |
| COLMAP Pose Estimation | ~2-5min | ~4GB |
| Nerfstudio Training (5k iter) | ~10-15min | ~6GB VRAM |
| Nerfstudio Training (30k iter) | ~30-60min | ~6GB VRAM |
| Export (PLY + Mesh) | ~2-5min | ~4GB |

**Total (Quick Test)**: ~15-25 minutes  
**Total (Full Quality)**: ~40-80 minutes

## Support

If you encounter issues:

1. Check logs: `backend/reconstruction_test.log`
2. Review error messages carefully
3. Consult documentation:
   - Nerfstudio: https://docs.nerf.studio/
   - COLMAP: https://colmap.github.io/
4. Ask questions with full error traces

## Additional Resources

- **Nerfstudio Documentation**: https://docs.nerf.studio/
- **COLMAP Tutorial**: https://colmap.github.io/tutorial.html
- **PyTorch CUDA Setup**: https://pytorch.org/get-started/locally/
- **FFmpeg Documentation**: https://ffmpeg.org/documentation.html

# Setup and Installation Guide

## Quick Start (Windows with Nerfstudio Already Installed)

Since you already have Nerfstudio installed, you just need to:

### 1. Install COLMAP

```powershell
# Activate your nerfstudio environment
conda activate nerfstudio

# Install COLMAP
conda install -c conda-forge colmap
```

### 2. Install Additional Dependencies

```powershell
# Navigate to the backend directory
cd backend

# Install Python dependencies (most are already installed with Nerfstudio)
pip install pyyaml pydantic fastapi uvicorn celery redis minio sqlalchemy alembic
```

### 3. Verify Installation

```powershell
# Test imports
python test_imports.py
```

You should see:
```
✓ Importing config...
✓ Importing engine...
✓ Importing preprocessing...
  - COLMAP installed: True

✅ All imports successful!
```

### 4. Test with a Video

```powershell
# Run reconstruction on a test video (adjust iterations for speed)
python test_reconstruction.py --video path\to\your\video.mp4 --iterations 5000
```

## Detailed Installation (Fresh Setup)

If you need to set up from scratch:

### Prerequisites
- **Python 3.8-3.10** (Nerfstudio requires this range)
- **CUDA 11.8+** (for GPU support)
- **NVIDIA GPU** with 8GB+ VRAM
- **Conda** (Miniconda or Anaconda)

### Step 1: Create Environment

```powershell
# Create conda environment
conda create -n video3d python=3.8

# Activate environment
conda activate video3d
```

### Step 2: Install PyTorch

```powershell
# Install PyTorch with CUDA 11.8
pip install torch==2.1.2 torchvision==0.16.2 --index-url https://download.pytorch.org/whl/cu118
```

### Step 3: Install Nerfstudio

```powershell
# Install Nerfstudio
pip install nerfstudio

# Test installation
ns-train --help
```

### Step 4: Install COLMAP

```powershell
conda install -c conda-forge colmap
```

### Step 5: Install Project Dependencies

```powershell
cd backend
pip install -r requirements.txt
```

## Testing

### Test 1: Import Test
```powershell
python test_imports.py
```

### Test 2: Quick Reconstruction Test (5-10 seconds)
```powershell
# Use a short video and low iterations for quick testing
python test_reconstruction.py --video test.mp4 --iterations 1000 --method splatfacto
```

### Test 3: Full Quality Reconstruction (30+ minutes)
```powershell
# Full quality with default iterations
python test_reconstruction.py --video video.mp4 --iterations 30000
```

## Configuration

Edit `backend/config/default.yaml` to customize:

- **Reconstruction settings**: method, iterations, resolution
- **Preprocessing**: FPS, max frames, quality filters
- **COLMAP**: feature detector, matching method
- **Storage**: paths for uploads, outputs, cache

## Troubleshooting

### COLMAP Not Found
**Error**: `colmap: command not found` or `COLMAP is not installed`

**Fix**: Install COLMAP via conda:
```powershell
conda install -c conda-forge colmap
```

### GPU Out of Memory
**Error**: `CUDA out of memory`

**Fix**: Reduce iterations or resolution in config:
```yaml
reconstruction:
  max_iterations: 10000  # Reduce from 30000
  resolution: 512        # Reduce from 1024
```

### Nerfstudio Import Errors
**Error**: `ModuleNotFoundError: No module named 'nerfstudio'`

**Fix**: 
1. Verify Nerfstudio installation: `pip show nerfstudio`
2. Reinstall if needed: `pip install --upgrade nerfstudio`

### FFmpeg Not Found
**Error**: `ffmpeg: command not found`

**Fix**: Install FFmpeg:
```powershell
# Windows (via conda)
conda install -c conda-forge ffmpeg

# Or download from: https://ffmpeg.org/download.html
```

### COLMAP Feature Extraction Fails
**Error**: Feature extraction returns no features

**Fix**: Check that:
1. Video has textured content (not blank walls)
2. Frames have sufficient motion
3. Video quality is good (not too dark/blurry)

Try adjusting preprocessing:
```yaml
preprocessing:
  frame_extraction:
    fps: 5  # Extract fewer frames
  quality_filter:
    min_sharpness: 5.0  # Lower threshold
```

## Expected Performance

### Hardware: RTX 3070 Ti (8GB VRAM)

| Phase | Time |
|-------|------|
| Frame Extraction (300 frames) | ~30 seconds |
| COLMAP Pose Estimation | 2-5 minutes |
| Splatfacto Training (10k iter) | 10-15 minutes |
| Nerfacto Training (10k iter) | 15-20 minutes |
| Export (mesh + point cloud) | 2-5 minutes |

**Total for quick test**: ~15-25 minutes
**Total for full quality**: 45-90 minutes

### Tips for Faster Testing

1. **Reduce iterations**: Use `--iterations 5000` for quick tests
2. **Use splatfacto**: Generally 2x faster than nerfacto
3. **Extract fewer frames**: Modify config `max_frames: 150`
4. **Lower resolution**: Modify config `resolution: 512`

## Next Steps

Once basic reconstruction works:

1. **API Server**: Set up FastAPI server for web interface
2. **Worker Queue**: Add Celery for async job processing
3. **Frontend**: Build React UI for uploads and viewing
4. **Docker**: Containerize for deployment

See `docs/` directory for additional documentation.

## Support

- Check logs in `reconstruction_test.log`
- Enable debug logging: modify `logging.level: "DEBUG"` in config
- Review Nerfstudio docs: https://docs.nerf.studio/

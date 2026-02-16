# Quick Start Guide

Get started with video-to-3D reconstruction in 5 minutes!

## Prerequisites

Make sure you've completed the [Setup Guide](SETUP.md) first.

## Basic Usage

### 1. Prepare Your Video

Requirements for best results:
- **Duration**: 5-30 seconds
- **Resolution**: 720p or higher
- **Frame rate**: 24-60 fps
- **Subject**: Stationary object or scene with camera moving around it
- **Lighting**: Good, consistent lighting
- **Motion**: Smooth camera movement, avoid rapid motion

**Tips for good captures:**
- Circle around the object slowly
- Keep the object in frame at all times
- Avoid reflective or transparent surfaces
- Film in good lighting (avoid backlighting)
- Use landscape orientation

### 2. Run Reconstruction

```bash
cd backend

# Activate virtual environment
venv\Scripts\activate  # Windows
source venv/bin/activate  # Mac/Linux

# Basic reconstruction
python test_reconstruction.py --video path/to/video.mp4

# Quick mode (faster, lower quality)
python test_reconstruction.py --video path/to/video.mp4 --quick

# With specific method
python test_reconstruction.py --video path/to/video.mp4 --method splatfacto
```

### 3. View Results

Outputs are saved in: `data/cache/job_<id>/`

```
job_abc123/
├── preprocessing/
│   ├── processed_frames/  # Extracted frames
│   └── metadata.json      # Video metadata
├── colmap/
│   └── sparse/            # Camera poses
├── outputs/
│   └── exports/
│       ├── pointcloud.ply  # 3D point cloud
│       └── mesh.ply        # 3D mesh
└── result_summary.json     # Quality metrics
```

**View 3D models:**
- CloudCompare: Open → Select .ply file
- MeshLab: File → Import Mesh
- Blender: File → Import → PLY

## Configuration

### Adjust Quality vs Speed

Edit `backend/config/default.yaml`:

```yaml
# Fast (5-10 minutes)
reconstruction:
  max_iterations: 5000
preprocessing:
  frame_extraction:
    max_frames: 100
    fps: 5

# Balanced (15-30 minutes)
reconstruction:
  max_iterations: 15000
preprocessing:
  frame_extraction:
    max_frames: 200
    fps: 8

# High Quality (30-60 minutes)
reconstruction:
  max_iterations: 30000
preprocessing:
  frame_extraction:
    max_frames: 300
    fps: 10
```

### Choose Reconstruction Method

```yaml
reconstruction:
  # Fast, high quality (recommended)
  default_method: "splatfacto"  # 3D Gaussian Splatting
  
  # Or slower, more stable
  # default_method: "nerfacto"  # NeRF
```

## Common Workflows

### Object Scanning

Scan a small object (toy, statue, etc.):

1. Place object on a turntable or fixed surface
2. Record video while moving around it in a circle
3. Keep object centered in frame
4. Capture 360° coverage

```bash
python test_reconstruction.py --video object_scan.mp4 --method splatfacto
```

### Room Reconstruction

Capture an indoor space:

1. Walk slowly through the room
2. Pan camera to capture all walls and features
3. Avoid rapid movements
4. Film in good lighting

```bash
python test_reconstruction.py --video room_scan.mp4 --quick
```

### Outdoor Scene

Capture outdoor environments:

1. Choose a clear, well-lit day
2. Move steadily through the scene
3. Avoid moving objects (people, cars)
4. Capture overlapping views

```bash
python test_reconstruction.py --video outdoor.mp4
```

## Troubleshooting

### Poor Quality Results

**Symptoms**: Blurry, incomplete, or noisy reconstruction

**Solutions:**
1. **Improve video quality**:
   - Film in better lighting
   - Move camera more slowly
   - Increase overlap between frames

2. **Adjust settings**:
   ```yaml
   preprocessing:
     frame_extraction:
       fps: 15  # Increase frame density
       max_frames: 400  # Use more frames
   ```

3. **Use more iterations**:
   ```yaml
   reconstruction:
     max_iterations: 50000  # Increase training time
   ```

### COLMAP Fails

**Symptoms**: "Pose estimation failed" or "No reconstructions found"

**Causes:**
- Not enough camera motion
- Scene lacks texture (blank walls)
- Too much motion blur

**Solutions:**
1. Re-film with more camera movement
2. Ensure scene has textured features
3. Reduce FPS to avoid blur:
   ```yaml
   preprocessing:
     frame_extraction:
       fps: 5  # Lower FPS for smoother extraction
   ```

### Out of Memory

**Symptoms**: CUDA out of memory errors

**Solutions:**
1. Reduce batch size:
   ```yaml
   reconstruction:
     max_batch_size: 2048  # Lower from 4096
   ```

2. Use fewer frames:
   ```yaml
   preprocessing:
     frame_extraction:
       max_frames: 150  # Lower from 300
   ```

3. Lower resolution:
   ```yaml
   preprocessing:
     image_processing:
       max_dimension: 1280  # Lower from 1920
   ```

## Performance Tips

### Speed Up Reconstruction

1. **Use quick mode**: `--quick` flag
2. **Reduce iterations**: Lower `max_iterations`
3. **Use fewer frames**: Lower `max_frames`
4. **Use splatfacto**: Generally faster than nerfacto

### Improve Quality

1. **Increase iterations**: Higher `max_iterations` (30k-50k)
2. **Use more frames**: Higher `max_frames` (300-500)
3. **Better video**: Higher resolution, better lighting
4. **Slower camera movement**: More overlap between frames

## Advanced Options

### Custom Configuration

Create a custom config file:

```yaml
# custom_config.yaml
reconstruction:
  default_method: "splatfacto"
  max_iterations: 20000

preprocessing:
  frame_extraction:
    fps: 12
    max_frames: 250
```

Use it:
```bash
python test_reconstruction.py --video video.mp4 --config custom_config.yaml
```

### Verbose Logging

See detailed logs:
```bash
python test_reconstruction.py --video video.mp4 --verbose
```

Check log file:
```bash
cat reconstruction_test.log
```

## Example Videos

Good test subjects:
- ✅ Toys, figurines, statues
- ✅ Furniture, plants
- ✅ Room interiors
- ✅ Building exteriors
- ✅ Gardens, landscapes

Difficult subjects:
- ❌ Mirrors, glass
- ❌ Very thin objects (wires, chains)
- ❌ Uniform colors (blank walls)
- ❌ Moving objects (people, animals)
- ❌ Very dark or bright scenes

## Next Steps

Once you're comfortable with basic reconstruction:

1. **Experiment with settings**: Try different configurations
2. **Test different scenes**: Objects, rooms, outdoor spaces
3. **Build the API**: Set up FastAPI service (Phase 2)
4. **Create the UI**: Build React frontend (Phase 3)

## Getting Help

- Check logs: `reconstruction_test.log`
- Review [Setup Guide](SETUP.md)
- See [Troubleshooting](#troubleshooting) section
- Consult Nerfstudio docs: https://docs.nerf.studio/

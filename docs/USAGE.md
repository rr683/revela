# Usage Guide

## Input Types

Revela accepts two types of input for 3D reconstruction:

### Video Files
Supported formats: `.mp4`, `.mov`, `.avi`, `.mkv`, `.webm`

```bash
python test_reconstruction.py --video path/to/video.mp4
```

### Image Sets
Supported formats: `.jpg`, `.jpeg`, `.png`, `.tiff`, `.bmp`

Provide a directory containing images with overlapping views of the scene:

```bash
python test_reconstruction.py --image-dir path/to/images/
```

You can also combine both -- provide a video plus supplementary images for extra coverage.

## Running Reconstructions

### Quick Test (5-15 minutes)
```bash
python test_reconstruction.py --video sample.mp4 --quick
```

### Full Quality (30-60 minutes)
```bash
python test_reconstruction.py --video sample.mp4
```

### Specific Method
```bash
# 3D Gaussian Splatting (faster, recommended)
python test_reconstruction.py --video sample.mp4 --method splatfacto

# NeRF (slower, more flexible)
python test_reconstruction.py --video sample.mp4 --method nerfacto
```

### Custom Config
```bash
python test_reconstruction.py --video sample.mp4 --config custom.yaml
```

## Output Structure

```
data/cache/job_<id>/
├── preprocessing/
│   ├── processed_frames/      # Extracted/filtered frames
│   └── metadata.json          # Video/image metadata
├── colmap/
│   └── sparse/                # Camera poses
├── outputs/exports/
│   ├── pointcloud.ply         # 3D point cloud
│   └── mesh.ply               # 3D mesh
└── result_summary.json        # Quality metrics
```

## Viewing Results

- **CloudCompare** (free): Open -> select `.ply` file
- **MeshLab** (free): File -> Import Mesh
- **Blender** (free): File -> Import -> PLY
- **Gaussian splat viewers**: [antimatter15 splat viewer](https://antimatter15.com/splat/)

## Configuration Tuning

Edit `backend/config/default.yaml`:

### Fast Preview
```yaml
reconstruction:
  max_iterations: 5000
  resolution: 512
preprocessing:
  frame_extraction:
    max_frames: 100
    fps: 5
```

### Balanced
```yaml
reconstruction:
  max_iterations: 15000
  resolution: 1024
preprocessing:
  frame_extraction:
    max_frames: 200
    fps: 8
```

### Maximum Quality
```yaml
reconstruction:
  max_iterations: 30000
  resolution: 1024
preprocessing:
  frame_extraction:
    max_frames: 300
    fps: 10
```

## Capture Tips

### Video
- 5-30 seconds, landscape orientation
- Circle slowly around the subject
- Keep subject centered in frame
- Consistent lighting, avoid backlighting
- Avoid rapid motion or shaking

### Images
- 20-300 images with 60-80% overlap between adjacent views
- Cover the subject from multiple angles
- Consistent exposure and white balance
- Avoid motion blur -- use a tripod if possible

### What Works Well
- Toys, figurines, statues
- Furniture, plants
- Room interiors, building exteriors

### What's Difficult
- Mirrors, glass, transparent objects
- Uniform/textureless surfaces
- Moving objects
- Very thin structures (wires, chains)

## Troubleshooting

### COLMAP Fails ("No reconstructions found")
- Video/images need more camera motion variety
- Scene needs textured features (not blank walls)
- Try `exhaustive` matching instead of `sequential` in config

### Poor Quality Results
- Increase `max_iterations` (30k-50k)
- Use more frames/images
- Improve lighting and camera stability

### GPU Out of Memory
- Reduce `max_iterations`, `max_frames`, `resolution`
- Use `--quick` flag
- splatfacto generally uses less memory than nerfacto

### Verbose Logging
```bash
python test_reconstruction.py --video sample.mp4 --verbose
# Logs written to reconstruction_test.log
```

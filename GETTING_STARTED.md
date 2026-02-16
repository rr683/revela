# Getting Started - Your First Reconstruction

Get from code to working 3D reconstruction in **30 minutes**.

## Quick Start

```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
pip install nerfstudio

# Test with your video
python test_reconstruction.py --video path/to/video.mp4 --quick
```

## Prerequisites

- Python 3.11+
- CUDA 11.8+ (for GPU)
- FFmpeg
- Nerfstudio
- COLMAP

See [SETUP.md](docs/SETUP.md) for detailed installation.

## Your First Reconstruction

1. **Get a test video** (10-30 seconds, filming an object while moving around it)
2. **Run reconstruction**: `python test_reconstruction.py --video test.mp4 --quick`
3. **View results**: Open `.ply` files in CloudCompare or MeshLab

Outputs saved to: `data/cache/job_<id>/exports/`

## Next Steps

- Read [USAGE.md](docs/USAGE.md) for detailed usage
- See [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) for architecture
- Tune settings in `config/default.yaml`
- Build Phase 2: API + Frontend

## Troubleshooting

**COLMAP fails**: Video needs more camera movement or textured features  
**Out of memory**: Use `--quick` flag or reduce `max_frames` in config  
**Poor quality**: Better lighting, slower movement, more iterations

Full guide: [SETUP.md](docs/SETUP.md)

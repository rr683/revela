#!/usr/bin/env python3
"""
Simple test to verify all modules can be imported.

Run this first to check if the environment is set up correctly.
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

print("Testing imports...")
print()

try:
    print("✓ Importing config...")
    from config import get_config
    config = get_config()
    print(f"  - Loaded config: reconstruction method = {config.reconstruction.default_method}")
    
    print("✓ Importing engine...")
    from engine import (
        NerfstudioWrapper,
        ReconstructionInput,
        ReconstructionMethod,
        generate_job_id
    )
    print(f"  - Generated test job ID: {generate_job_id()}")
    
    print("✓ Importing preprocessing...")
    from preprocessing import (
        VideoPreprocessor,
        COLMAPPoseEstimator,
        check_colmap_installed
    )
    colmap_available = check_colmap_installed()
    print(f"  - COLMAP installed: {colmap_available}")
    
    print()
    print("=" * 60)
    print("✅ All imports successful!")
    print("=" * 60)
    print()
    
    if not colmap_available:
        print("⚠️  WARNING: COLMAP is not installed")
        print("   Install with: conda install -c conda-forge colmap")
        print("   The system will use mock poses for testing")
        print()
    
    print("Next steps:")
    print("1. Install COLMAP (if not already installed)")
    print("2. Prepare a test video (mp4, mov, etc.)")
    print("3. Run: python test_reconstruction.py --video path/to/video.mp4")
    print()
    
    sys.exit(0)
    
except ImportError as e:
    print(f"❌ Import failed: {e}")
    print()
    print("Make sure you have installed dependencies:")
    print("  pip install -r requirements.txt")
    print()
    sys.exit(1)
    
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)

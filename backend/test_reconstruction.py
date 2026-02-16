#!/usr/bin/env python3
"""
End-to-End Reconstruction Test

Tests the complete pipeline:
1. Video preprocessing (frame extraction)
2. COLMAP pose estimation
3. Nerfstudio reconstruction
4. Output validation

Usage:
    python test_reconstruction.py --video <path_to_video.mp4>
    
    # With custom config
    python test_reconstruction.py --video <path> --config config/custom.yaml
    
    # Quick test (fewer iterations)
    python test_reconstruction.py --video <path> --quick
"""

import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime
import json

# Add backend to Python path
sys.path.insert(0, str(Path(__file__).parent))

from config.config_loader import ConfigLoader
from preprocessing.video_processor import VideoPreprocessor, validate_video
from preprocessing.colmap_wrapper import COLMAPWrapper, validate_colmap_reconstruction
from engine.base import (
    ReconstructionInput,
    ReconstructionMethod,
    OutputFormat,
    generate_job_id
)
from engine.nerfstudio_wrapper import NerfstudioWrapper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('reconstruction_test.log')
    ]
)

logger = logging.getLogger(__name__)


def progress_callback(message: str, progress: float):
    """Progress callback for pipeline stages."""
    bar_length = 40
    filled = int(bar_length * progress)
    bar = '=' * filled + '-' * (bar_length - filled)
    print(f'\r[{bar}] {progress*100:.1f}% - {message}', end='', flush=True)
    if progress >= 1.0:
        print()  # New line when complete


def test_reconstruction(
    video_path: Path,
    config_file: Path = None,
    quick: bool = False
):
    """
    Test full reconstruction pipeline.
    
    Args:
        video_path: Path to input video
        config_file: Optional custom config file
        quick: If True, use reduced iterations for faster testing
    """
    print("=" * 80)
    print("Video-to-3D Reconstruction - End-to-End Test")
    print("=" * 80)
    print()
    
    # Load configuration
    print("📋 Loading configuration...")
    config = ConfigLoader.load(config_file)
    
    if quick:
        print("⚡ Quick mode: reducing iterations for faster testing")
        config.reconstruction.max_iterations = 5000
        config.preprocessing.frame_extraction.max_frames = 100
    
    print(f"   Reconstruction method: {config.reconstruction.default_method}")
    print(f"   Max iterations: {config.reconstruction.max_iterations}")
    print(f"   Max frames: {config.preprocessing.frame_extraction.max_frames}")
    print()
    
    # Validate video
    print("🎥 Validating video...")
    valid, message = validate_video(video_path, config.api.allowed_video_formats)
    if not valid:
        logger.error(f"Video validation failed: {message}")
        return False
    print(f"   ✓ {message}")
    print()
    
    # Create job
    job_id = generate_job_id()
    job_dir = Path(config.storage.cache_dir) / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"🔑 Job ID: {job_id}")
    print(f"📁 Working directory: {job_dir}")
    print()
    
    # Stage 1: Preprocess video
    print("=" * 80)
    print("Stage 1: Video Preprocessing")
    print("=" * 80)
    
    preprocessor = VideoPreprocessor(config.preprocessing.model_dump())
    
    try:
        frame_paths, metadata = preprocessor.process_video(
            video_path,
            job_dir / "preprocessing",
            progress_callback=progress_callback
        )
        
        print(f"\n✓ Preprocessing complete")
        print(f"   Extracted: {metadata['num_extracted_frames']} frames")
        print(f"   Filtered: {metadata['num_filtered_frames']} frames")
        print(f"   Processed: {metadata['num_processed_frames']} frames")
        print(f"   Video: {metadata['width']}x{metadata['height']} @ {metadata['fps']:.1f} fps")
        print()
        
    except Exception as e:
        logger.error(f"Preprocessing failed: {e}", exc_info=True)
        return False
    
    # Stage 2: Estimate camera poses with COLMAP
    print("=" * 80)
    print("Stage 2: Camera Pose Estimation (COLMAP)")
    print("=" * 80)
    
    colmap_wrapper = COLMAPWrapper(config.colmap.model_dump())
    
    try:
        poses, intrinsics = colmap_wrapper.estimate_poses(
            job_dir / "preprocessing" / "processed_frames",
            job_dir / "colmap",
            progress_callback=progress_callback
        )
        
        print(f"\n✓ Pose estimation complete")
        print(f"   Estimated {len(poses)} camera poses")
        print(f"   Camera: {intrinsics.width}x{intrinsics.height}")
        print(f"   Focal length: fx={intrinsics.fx:.1f}, fy={intrinsics.fy:.1f}")
        print(f"   Principal point: cx={intrinsics.cx:.1f}, cy={intrinsics.cy:.1f}")
        print()
        
        # Validate COLMAP output
        valid, message = validate_colmap_reconstruction(job_dir / "colmap" / "sparse")
        if not valid:
            logger.error(f"COLMAP validation failed: {message}")
            return False
        
    except Exception as e:
        logger.error(f"COLMAP pose estimation failed: {e}", exc_info=True)
        return False
    
    # Stage 3: 3D Reconstruction with Nerfstudio
    print("=" * 80)
    print("Stage 3: 3D Reconstruction (Nerfstudio)")
    print("=" * 80)
    
    # Prepare reconstruction input
    recon_input = ReconstructionInput(
        job_id=job_id,
        frame_paths=frame_paths,
        camera_poses=poses,
        camera_intrinsics=intrinsics,
        method=ReconstructionMethod(config.reconstruction.default_method),
        max_iterations=config.reconstruction.max_iterations,
        output_formats=[OutputFormat.PLY, OutputFormat.MESH],
        output_dir=job_dir / "outputs"
    )
    
    # Run reconstruction
    nerfstudio = NerfstudioWrapper(
        workspace_dir=job_dir / "nerfstudio",
        config=config.reconstruction.model_dump()
    )
    
    try:
        result = nerfstudio.reconstruct(
            recon_input,
            progress_callback=progress_callback
        )
        
        print(f"\n✓ Reconstruction complete")
        print(f"   Status: {result.status.value}")
        print(f"   Duration: {result.duration_seconds:.1f} seconds")
        print()
        
        # Display outputs
        print("📦 Output Files:")
        for format_type, path in result.output_files.items():
            size_mb = path.stat().st_size / (1024 * 1024)
            print(f"   {format_type.value}: {path} ({size_mb:.1f} MB)")
        print()
        
        # Display quality metrics
        if result.quality_metrics:
            print("📊 Quality Metrics:")
            metrics = result.quality_metrics
            print(f"   Overall score: {metrics.overall_score:.1f}/100")
            print(f"   Coverage: {metrics.coverage_percentage:.1f}%")
            print(f"   Pose confidence: {metrics.pose_confidence:.1f}/100")
            print(f"   Frames used: {metrics.num_valid_poses}/{metrics.num_frames}")
            
            if metrics.warnings:
                print("\n⚠️  Warnings:")
                for warning in metrics.warnings:
                    print(f"   - {warning}")
            
            if metrics.errors:
                print("\n❌ Errors:")
                for error in metrics.errors:
                    print(f"   - {error}")
        print()
        
        # Save result summary
        summary_path = job_dir / "result_summary.json"
        with open(summary_path, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)
        print(f"💾 Result summary saved: {summary_path}")
        print()
        
        return True
        
    except Exception as e:
        logger.error(f"Reconstruction failed: {e}", exc_info=True)
        return False
    
    finally:
        print("=" * 80)
        print("Test Complete")
        print("=" * 80)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test end-to-end video-to-3D reconstruction pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic test
  python test_reconstruction.py --video sample.mp4
  
  # Quick test (fewer iterations, faster)
  python test_reconstruction.py --video sample.mp4 --quick
  
  # With custom config
  python test_reconstruction.py --video sample.mp4 --config custom.yaml
  
  # Specify method
  python test_reconstruction.py --video sample.mp4 --method nerfacto
        """
    )
    
    parser.add_argument(
        '--video',
        type=Path,
        required=True,
        help='Path to input video file'
    )
    
    parser.add_argument(
        '--config',
        type=Path,
        default=None,
        help='Path to custom configuration file (optional)'
    )
    
    parser.add_argument(
        '--method',
        type=str,
        choices=['nerfacto', 'splatfacto'],
        default=None,
        help='Reconstruction method (overrides config)'
    )
    
    parser.add_argument(
        '--quick',
        action='store_true',
        help='Quick test mode (fewer iterations, fewer frames)'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Run test
    try:
        success = test_reconstruction(
            video_path=args.video,
            config_file=args.config,
            quick=args.quick
        )
        
        if success:
            print("✅ Test PASSED")
            sys.exit(0)
        else:
            print("❌ Test FAILED")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        print(f"\n❌ Test FAILED: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

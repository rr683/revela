#!/usr/bin/env python3
"""
End-to-End Reconstruction Test

Tests the complete pipeline from video and/or images to 3D model:
1. Video preprocessing (frame extraction) and/or image ingestion
2. COLMAP pose estimation
3. Nerfstudio reconstruction
4. Output validation

Usage:
    python test_reconstruction.py --video <path_to_video.mp4>
    python test_reconstruction.py --image-dir <path_to_images/>
    python test_reconstruction.py --video <path> --image-dir <path>  # combined
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
from preprocessing.image_processor import ImageProcessor, validate_image_directory
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
    video_path: Path = None,
    image_dir: Path = None,
    config_file: Path = None,
    quick: bool = False
):
    """
    Test full reconstruction pipeline.

    Args:
        video_path: Path to input video (optional if image_dir provided)
        image_dir: Path to directory of images (optional if video_path provided)
        config_file: Optional custom config file
        quick: If True, use reduced iterations for faster testing
    """
    print("=" * 80)
    print("Revela - 3D Reconstruction End-to-End Test")
    print("=" * 80)
    print()

    # Load configuration
    print("Loading configuration...")
    config = ConfigLoader.load(config_file)

    if quick:
        print("Quick mode: reducing iterations for faster testing")
        config.reconstruction.max_iterations = 5000
        config.preprocessing.frame_extraction.max_frames = 100

    print(f"   Reconstruction method: {config.reconstruction.default_method}")
    print(f"   Max iterations: {config.reconstruction.max_iterations}")
    print()

    # Validate inputs
    if video_path:
        print("Validating video...")
        valid, message = validate_video(video_path, config.api.allowed_video_formats)
        if not valid:
            logger.error(f"Video validation failed: {message}")
            return False
        print(f"   Video: {message}")

    if image_dir:
        print("Validating image directory...")
        valid, message = validate_image_directory(image_dir)
        if not valid:
            logger.error(f"Image validation failed: {message}")
            return False
        print(f"   Images: {message}")

    print()

    # Create job
    job_id = generate_job_id()
    job_dir = Path(config.storage.cache_dir) / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    print(f"Job ID: {job_id}")
    print(f"Working directory: {job_dir}")
    print()

    # Stage 1: Preprocessing
    all_frame_paths = []

    if video_path:
        print("=" * 80)
        print("Stage 1a: Video Preprocessing")
        print("=" * 80)

        preprocessor = VideoPreprocessor(config.preprocessing.model_dump())

        try:
            frame_paths, metadata = preprocessor.process_video(
                video_path,
                job_dir / "preprocessing_video",
                progress_callback=progress_callback
            )

            print(f"\nVideo preprocessing complete")
            print(f"   Extracted: {metadata['num_extracted_frames']} frames")
            print(f"   Filtered: {metadata['num_filtered_frames']} frames")
            print(f"   Processed: {metadata['num_processed_frames']} frames")
            print(f"   Video: {metadata['width']}x{metadata['height']} @ {metadata['fps']:.1f} fps")
            print()

            all_frame_paths.extend(frame_paths)

        except Exception as e:
            logger.error(f"Video preprocessing failed: {e}", exc_info=True)
            return False

    if image_dir:
        print("=" * 80)
        print("Stage 1b: Image Ingestion")
        print("=" * 80)

        image_processor = ImageProcessor(config.preprocessing.model_dump())

        try:
            image_paths, img_metadata = image_processor.process_images(
                image_dir,
                job_dir / "preprocessing_images",
                progress_callback=progress_callback
            )

            print(f"\nImage ingestion complete")
            print(f"   Discovered: {img_metadata['num_discovered_images']} images")
            print(f"   Filtered: {img_metadata['num_filtered_images']} images")
            print(f"   Processed: {img_metadata['num_processed_images']} images")
            print()

            all_frame_paths.extend(image_paths)

        except Exception as e:
            logger.error(f"Image ingestion failed: {e}", exc_info=True)
            return False

    if not all_frame_paths:
        logger.error("No frames available for reconstruction")
        return False

    print(f"Total frames for reconstruction: {len(all_frame_paths)}")
    print()

    # If we have frames from both sources, consolidate into one directory
    if video_path and image_dir:
        import shutil
        combined_dir = job_dir / "preprocessing" / "processed_frames"
        combined_dir.mkdir(parents=True, exist_ok=True)
        consolidated = []
        for i, p in enumerate(all_frame_paths):
            dest = combined_dir / f"frame_{i:05d}.png"
            shutil.copy(p, dest)
            consolidated.append(dest)
        all_frame_paths = consolidated
    else:
        # Ensure processed_frames directory exists at expected location
        source_dir = all_frame_paths[0].parent
        target_dir = job_dir / "preprocessing" / "processed_frames"
        if source_dir != target_dir:
            target_dir.mkdir(parents=True, exist_ok=True)
            import shutil
            consolidated = []
            for i, p in enumerate(all_frame_paths):
                dest = target_dir / f"frame_{i:05d}.png"
                shutil.copy(p, dest)
                consolidated.append(dest)
            all_frame_paths = consolidated

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

        print(f"\nPose estimation complete")
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
        video_path=video_path,
        image_dir=image_dir,
        frame_paths=all_frame_paths,
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

        print(f"\nReconstruction complete")
        print(f"   Status: {result.status.value}")
        print(f"   Duration: {result.duration_seconds:.1f} seconds")
        print()

        # Display outputs
        print("Output Files:")
        for format_type, path in result.output_files.items():
            size_mb = path.stat().st_size / (1024 * 1024)
            print(f"   {format_type.value}: {path} ({size_mb:.1f} MB)")
        print()

        # Display quality metrics
        if result.quality_metrics:
            print("Quality Metrics:")
            metrics = result.quality_metrics
            print(f"   Overall score: {metrics.overall_score:.1f}/100")
            print(f"   Coverage: {metrics.coverage_percentage:.1f}%")
            print(f"   Pose confidence: {metrics.pose_confidence:.1f}/100")
            print(f"   Frames used: {metrics.num_valid_poses}/{metrics.num_frames}")

            if metrics.warnings:
                print("\n   Warnings:")
                for warning in metrics.warnings:
                    print(f"   - {warning}")

            if metrics.errors:
                print("\n   Errors:")
                for error in metrics.errors:
                    print(f"   - {error}")
        print()

        # Save result summary
        summary_path = job_dir / "result_summary.json"
        with open(summary_path, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)
        print(f"Result summary saved: {summary_path}")
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
        description="Test end-to-end 3D reconstruction pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # From video
  python test_reconstruction.py --video sample.mp4

  # From images
  python test_reconstruction.py --image-dir ./photos/

  # Combined video + images
  python test_reconstruction.py --video sample.mp4 --image-dir ./extra_photos/

  # Quick test (fewer iterations)
  python test_reconstruction.py --video sample.mp4 --quick
        """
    )

    parser.add_argument(
        '--video',
        type=Path,
        default=None,
        help='Path to input video file'
    )

    parser.add_argument(
        '--image-dir',
        type=Path,
        default=None,
        help='Path to directory containing input images'
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

    if not args.video and not args.image_dir:
        parser.error("At least one of --video or --image-dir is required")

    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Run test
    try:
        success = test_reconstruction(
            video_path=args.video,
            image_dir=args.image_dir,
            config_file=args.config,
            quick=args.quick
        )

        if success:
            print("Test PASSED")
            sys.exit(0)
        else:
            print("Test FAILED")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        print(f"\nTest FAILED: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

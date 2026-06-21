"""
Celery tasks for reconstruction jobs.

Each task wraps the existing reconstruction pipeline and updates
job status in the JobStore as it progresses.
"""

import logging
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from workers.celery_app import app
from config.config_loader import get_config
from engine.base import (
    OutputFormat,
    ReconstructionInput,
    ReconstructionMethod,
    ReconstructionStatus,
    generate_job_id,
)
from engine.nerfstudio_wrapper import NerfstudioWrapper
from preprocessing.video_processor import VideoPreprocessor
from preprocessing.image_processor import ImageProcessor
from preprocessing.colmap_wrapper import COLMAPWrapper
from storage import JobStore, FileStore
from api.ws import publish_job_update

logger = logging.getLogger(__name__)


def _get_stores():
    """Create storage instances from config."""
    config = get_config()
    data_dir = Path(config.storage.cache_dir).parent  # data/
    db_path = data_dir / "revela.db"
    return JobStore(db_path), FileStore(data_dir)


def _update_and_notify(job_store: JobStore, job_id: str, status: str, **kwargs):
    """Update job status in DB and publish via Redis for WebSocket clients."""
    job_store.update_status(job_id, status, **kwargs)
    job = job_store.get_job(job_id)
    if job:
        publish_job_update(job)


@app.task(bind=True, name="workers.tasks.run_reconstruction")
def run_reconstruction(self, job_id: str):
    """
    Run the full reconstruction pipeline for a job.

    Reads job config from the JobStore, processes the input
    (video and/or images), runs COLMAP + Nerfstudio, and
    saves results back to the stores.
    """
    job_store, file_store = _get_stores()
    config = get_config()

    job = job_store.get_job(job_id)
    if not job:
        logger.error(f"Job {job_id} not found")
        return {"error": "Job not found"}

    try:
        # -- Stage 1: Preprocessing --
        _update_and_notify(job_store, job_id, ReconstructionStatus.PREPROCESSING.value)

        preprocessing_config = config.preprocessing.model_dump()
        cache_dir = file_store.get_cache_dir(job_id)
        all_frames = []

        # Video input
        if job.get("input_video"):
            video_path = Path(job["input_video"])
            logger.info(f"[{job_id}] Processing video: {video_path}")

            preprocessor = VideoPreprocessor(preprocessing_config)
            frames, metadata = preprocessor.process_video(
                video_path, cache_dir / "preprocessing_video"
            )
            all_frames.extend(frames)
            logger.info(f"[{job_id}] Extracted {len(frames)} frames from video")

        # Image input
        if job.get("input_image_dir"):
            image_dir = Path(job["input_image_dir"])
            logger.info(f"[{job_id}] Processing images: {image_dir}")

            image_proc = ImageProcessor(preprocessing_config)
            images, img_meta = image_proc.process_images(
                image_dir, cache_dir / "preprocessing_images"
            )
            all_frames.extend(images)
            logger.info(f"[{job_id}] Processed {len(images)} images")

        if not all_frames:
            raise ValueError("No frames produced from input")

        # Consolidate frames into single directory for COLMAP
        frames_dir = cache_dir / "preprocessing" / "processed_frames"
        frames_dir.mkdir(parents=True, exist_ok=True)
        consolidated = []
        for i, p in enumerate(all_frames):
            dest = frames_dir / f"frame_{i:05d}.png"
            shutil.copy(p, dest)
            consolidated.append(dest)

        # -- Stage 2: Pose estimation --
        _update_and_notify(job_store, job_id, ReconstructionStatus.POSE_ESTIMATION.value)
        logger.info(f"[{job_id}] Running COLMAP on {len(consolidated)} frames")

        colmap = COLMAPWrapper(config.colmap.model_dump())
        poses, intrinsics = colmap.estimate_poses(
            frames_dir, cache_dir / "colmap"
        )
        logger.info(f"[{job_id}] Estimated {len(poses)} poses")

        # -- Stage 3: Reconstruction --
        _update_and_notify(job_store, job_id, ReconstructionStatus.TRAINING.value)

        method = job.get("method", config.reconstruction.default_method)
        job_config = job.get("config_json") or {}
        max_iter = job_config.get(
            "max_iterations", config.reconstruction.max_iterations
        )

        recon_input = ReconstructionInput(
            job_id=job_id,
            frame_paths=consolidated,
            camera_poses=poses,
            camera_intrinsics=intrinsics,
            method=ReconstructionMethod(method),
            max_iterations=max_iter,
            output_formats=[OutputFormat.PLY, OutputFormat.MESH],
            output_dir=file_store.get_output_dir(job_id),
        )

        nerfstudio = NerfstudioWrapper(
            workspace_dir=cache_dir / "nerfstudio",
            config=config.reconstruction.model_dump(),
        )

        result = nerfstudio.reconstruct(recon_input)

        # -- Save results --
        if result.status == ReconstructionStatus.COMPLETED:
            result_dict = {
                "output_files": {
                    k.value: str(v) for k, v in result.output_files.items()
                },
            }
            quality_dict = (
                result.quality_metrics.to_dict() if result.quality_metrics else None
            )

            job_store.save_result(
                job_id,
                result=result_dict,
                quality=quality_dict,
                num_frames=len(consolidated),
                duration_seconds=result.duration_seconds,
            )
            _update_and_notify(
                job_store, job_id, ReconstructionStatus.COMPLETED.value
            )

            logger.info(
                f"[{job_id}] Reconstruction complete in "
                f"{result.duration_seconds:.1f}s"
            )
            return {"status": "completed", "job_id": job_id}
        else:
            raise RuntimeError(
                result.error_message or "Reconstruction returned non-completed status"
            )

    except Exception as e:
        logger.error(f"[{job_id}] Failed: {e}", exc_info=True)
        _update_and_notify(
            job_store, job_id,
            ReconstructionStatus.FAILED.value,
            error_message=str(e),
        )
        return {"status": "failed", "job_id": job_id, "error": str(e)}

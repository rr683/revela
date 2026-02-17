"""
API routes for job management and file upload/download.

Endpoints:
    POST   /api/jobs              -- Create a new reconstruction job (upload video/images)
    GET    /api/jobs              -- List all jobs
    GET    /api/jobs/{id}         -- Get job status and details
    DELETE /api/jobs/{id}         -- Delete a job and its files
    GET    /api/jobs/{id}/outputs -- List output files
    GET    /api/jobs/{id}/outputs/{filename} -- Download an output file
"""

import logging
import os
import shutil
import sys
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.config_loader import get_config
from engine.base import ReconstructionStatus, generate_job_id
from storage import FileStore, JobStore

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_stores():
    config = get_config()
    data_dir = Path(config.storage.cache_dir).parent
    db_path = data_dir / "revela.db"
    return JobStore(db_path), FileStore(data_dir)


# --- Pydantic response models ---


class JobResponse(BaseModel):
    id: str
    status: str
    method: str
    created_at: str
    updated_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    input_video: Optional[str] = None
    input_image_dir: Optional[str] = None
    num_frames: Optional[int] = None
    duration_seconds: Optional[float] = None
    quality: Optional[dict] = None
    outputs: Optional[dict] = None


class JobListResponse(BaseModel):
    jobs: List[JobResponse]
    total: int


class OutputFileResponse(BaseModel):
    name: str
    path: str
    size_bytes: int
    suffix: str


# --- Routes ---


@router.post("/jobs", response_model=JobResponse, status_code=201)
async def create_job(
    video: Optional[UploadFile] = File(None),
    images: Optional[List[UploadFile]] = File(None),
    method: str = Form("splatfacto"),
    max_iterations: Optional[int] = Form(None),
):
    """
    Create a new reconstruction job.

    Upload a video file, a set of images, or both. The job will be
    queued for processing by a Celery worker.
    """
    if not video and not images:
        raise HTTPException(
            status_code=400,
            detail="At least one of 'video' or 'images' must be provided",
        )

    config = get_config()
    job_store, file_store = _get_stores()
    job_id = generate_job_id()

    input_video = None
    input_image_dir = None

    # Save uploaded video
    if video:
        allowed = config.api.allowed_video_formats
        suffix = Path(video.filename).suffix.lower()
        if suffix not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported video format '{suffix}'. Allowed: {allowed}",
            )
        content = await video.read()
        size_mb = len(content) / (1024 * 1024)
        if size_mb > config.api.max_upload_size_mb:
            raise HTTPException(
                status_code=413,
                detail=f"Video too large ({size_mb:.0f}MB). Max: {config.api.max_upload_size_mb}MB",
            )
        saved = file_store.save_upload(job_id, video.filename, content)
        input_video = str(saved)

    # Save uploaded images
    if images:
        image_formats = set(
            config.preprocessing.image_ingestion.supported_formats
        )
        upload_dir = file_store.get_upload_dir(job_id) / "images"
        upload_dir.mkdir(parents=True, exist_ok=True)

        saved_count = 0
        for img in images:
            suffix = Path(img.filename).suffix.lower()
            if suffix not in image_formats:
                logger.warning(f"Skipping unsupported image: {img.filename}")
                continue
            content = await img.read()
            dest = upload_dir / img.filename
            dest.write_bytes(content)
            saved_count += 1

        if saved_count == 0:
            raise HTTPException(
                status_code=400,
                detail=f"No valid images uploaded. Supported: {sorted(image_formats)}",
            )

        input_image_dir = str(upload_dir)
        logger.info(f"Saved {saved_count} images for job {job_id}")

    # Build job config overrides
    job_config = {}
    if max_iterations:
        job_config["max_iterations"] = max_iterations

    # Create job record
    job = job_store.create_job(
        job_id=job_id,
        method=method,
        input_video=input_video,
        input_image_dir=input_image_dir,
        config=job_config if job_config else None,
    )

    # Enqueue Celery task
    try:
        from workers.tasks import run_reconstruction

        run_reconstruction.delay(job_id)
        logger.info(f"Enqueued reconstruction job {job_id}")
    except Exception as e:
        logger.error(f"Failed to enqueue job {job_id}: {e}")
        job_store.update_status(
            job_id, ReconstructionStatus.FAILED.value, error_message=str(e)
        )

    return _job_to_response(job)


@router.get("/jobs", response_model=JobListResponse)
async def list_jobs(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    """List reconstruction jobs, optionally filtered by status."""
    job_store, _ = _get_stores()
    jobs = job_store.list_jobs(status=status, limit=limit, offset=offset)
    return JobListResponse(
        jobs=[_job_to_response(j) for j in jobs],
        total=len(jobs),
    )


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str):
    """Get details for a specific job."""
    job_store, _ = _get_stores()
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_to_response(job)


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a job and all associated files."""
    job_store, file_store = _get_stores()
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Don't delete running jobs
    if job["status"] in (
        ReconstructionStatus.PREPROCESSING.value,
        ReconstructionStatus.POSE_ESTIMATION.value,
        ReconstructionStatus.TRAINING.value,
        ReconstructionStatus.EXPORTING.value,
    ):
        raise HTTPException(
            status_code=409, detail="Cannot delete a job that is currently running"
        )

    file_store.delete_job_files(job_id)
    job_store.delete_job(job_id)
    return {"detail": f"Job {job_id} deleted"}


@router.get("/jobs/{job_id}/outputs", response_model=List[OutputFileResponse])
async def list_outputs(job_id: str):
    """List output files for a completed job."""
    job_store, file_store = _get_stores()
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    files = file_store.list_outputs(job_id)
    return files


@router.get("/jobs/{job_id}/outputs/{filename}")
async def download_output(job_id: str, filename: str):
    """Download a specific output file."""
    job_store, file_store = _get_stores()
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    path = file_store.get_output_path(job_id, filename)
    if not path:
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found")

    return FileResponse(
        path=str(path),
        filename=filename,
        media_type="application/octet-stream",
    )


def _job_to_response(job: dict) -> JobResponse:
    """Convert a raw job dict to a response model."""
    return JobResponse(
        id=job["id"],
        status=job["status"],
        method=job["method"],
        created_at=job["created_at"],
        updated_at=job["updated_at"],
        started_at=job.get("started_at"),
        completed_at=job.get("completed_at"),
        error_message=job.get("error_message"),
        input_video=job.get("input_video"),
        input_image_dir=job.get("input_image_dir"),
        num_frames=job.get("num_frames"),
        duration_seconds=job.get("duration_seconds"),
        quality=job.get("quality_json"),
        outputs=job.get("result_json"),
    )

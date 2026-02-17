"""Tests for the storage module (JobStore + FileStore)."""

import json
import sqlite3
import time
from pathlib import Path

import pytest

from storage import FileStore, JobStore
from engine.base import ReconstructionStatus


# =============================================================================
# JobStore tests
# =============================================================================


class TestJobStoreCreate:
    """Test job creation."""

    def test_create_job_minimal(self, job_store):
        job = job_store.create_job("job-001")
        assert job["id"] == "job-001"
        assert job["status"] == "pending"
        assert job["method"] == "splatfacto"
        assert job["created_at"] is not None
        assert job["updated_at"] is not None
        assert job["started_at"] is None
        assert job["completed_at"] is None
        assert job["error_message"] is None

    def test_create_job_with_video(self, job_store):
        job = job_store.create_job("job-002", input_video="/path/to/video.mp4")
        assert job["input_video"] == "/path/to/video.mp4"
        assert job["input_image_dir"] is None

    def test_create_job_with_images(self, job_store):
        job = job_store.create_job("job-003", input_image_dir="/path/to/images")
        assert job["input_image_dir"] == "/path/to/images"
        assert job["input_video"] is None

    def test_create_job_with_method(self, job_store):
        job = job_store.create_job("job-004", method="nerfacto")
        assert job["method"] == "nerfacto"

    def test_create_job_with_config(self, job_store):
        cfg = {"max_iterations": 5000, "resolution": 512}
        job = job_store.create_job("job-005", config=cfg)
        assert job["config_json"] == cfg

    def test_create_duplicate_job_raises(self, job_store):
        job_store.create_job("job-dup")
        with pytest.raises(Exception):
            job_store.create_job("job-dup")


class TestJobStoreGet:
    """Test job retrieval."""

    def test_get_existing_job(self, job_store):
        job_store.create_job("job-get-1")
        job = job_store.get_job("job-get-1")
        assert job is not None
        assert job["id"] == "job-get-1"

    def test_get_nonexistent_job(self, job_store):
        job = job_store.get_job("does-not-exist")
        assert job is None


class TestJobStoreList:
    """Test job listing."""

    def test_list_empty(self, job_store):
        jobs = job_store.list_jobs()
        assert jobs == []

    def test_list_multiple(self, job_store):
        for i in range(5):
            job_store.create_job(f"job-list-{i}")
        jobs = job_store.list_jobs()
        assert len(jobs) == 5

    def test_list_with_status_filter(self, job_store):
        job_store.create_job("job-a")
        job_store.create_job("job-b")
        job_store.update_status("job-a", ReconstructionStatus.TRAINING.value)

        pending = job_store.list_jobs(status="pending")
        assert len(pending) == 1
        assert pending[0]["id"] == "job-b"

        training = job_store.list_jobs(status="training")
        assert len(training) == 1
        assert training[0]["id"] == "job-a"

    def test_list_with_limit(self, job_store):
        for i in range(10):
            job_store.create_job(f"job-lim-{i}")
        jobs = job_store.list_jobs(limit=3)
        assert len(jobs) == 3

    def test_list_with_offset(self, job_store):
        for i in range(5):
            job_store.create_job(f"job-off-{i}")
        all_jobs = job_store.list_jobs()
        offset_jobs = job_store.list_jobs(offset=2)
        assert len(offset_jobs) == 3
        assert offset_jobs[0]["id"] == all_jobs[2]["id"]

    def test_list_ordered_by_created_at_desc(self, job_store):
        job_store.create_job("job-first")
        job_store.create_job("job-second")
        job_store.create_job("job-third")
        jobs = job_store.list_jobs()
        # Most recent first
        assert jobs[0]["id"] == "job-third"
        assert jobs[2]["id"] == "job-first"


class TestJobStoreUpdateStatus:
    """Test status transitions."""

    def test_update_to_preprocessing(self, job_store):
        job_store.create_job("job-s1")
        job_store.update_status("job-s1", ReconstructionStatus.PREPROCESSING.value)
        job = job_store.get_job("job-s1")
        assert job["status"] == "preprocessing"
        assert job["started_at"] is not None

    def test_started_at_set_only_once(self, job_store):
        job_store.create_job("job-s2")
        job_store.update_status("job-s2", ReconstructionStatus.PREPROCESSING.value)
        started = job_store.get_job("job-s2")["started_at"]

        job_store.update_status("job-s2", ReconstructionStatus.TRAINING.value)
        job = job_store.get_job("job-s2")
        assert job["started_at"] == started  # Unchanged

    def test_update_to_completed(self, job_store):
        job_store.create_job("job-s3")
        job_store.update_status("job-s3", ReconstructionStatus.COMPLETED.value)
        job = job_store.get_job("job-s3")
        assert job["status"] == "completed"
        assert job["completed_at"] is not None

    def test_update_to_failed_with_error(self, job_store):
        job_store.create_job("job-s4")
        job_store.update_status(
            "job-s4",
            ReconstructionStatus.FAILED.value,
            error_message="Out of GPU memory",
        )
        job = job_store.get_job("job-s4")
        assert job["status"] == "failed"
        assert job["error_message"] == "Out of GPU memory"
        assert job["completed_at"] is not None

    def test_update_to_cancelled(self, job_store):
        job_store.create_job("job-s5")
        job_store.update_status("job-s5", ReconstructionStatus.CANCELLED.value)
        job = job_store.get_job("job-s5")
        assert job["status"] == "cancelled"

    def test_updated_at_changes(self, job_store):
        job_store.create_job("job-s6")
        t1 = job_store.get_job("job-s6")["updated_at"]
        job_store.update_status("job-s6", ReconstructionStatus.PREPROCESSING.value)
        t2 = job_store.get_job("job-s6")["updated_at"]
        assert t2 >= t1


class TestJobStoreSaveResult:
    """Test saving results and quality metrics."""

    def test_save_result(self, job_store):
        job_store.create_job("job-r1")
        result = {"output_files": {"ply": "/outputs/job-r1/model.ply"}}
        quality = {"psnr": 28.5, "ssim": 0.92}

        job_store.save_result(
            "job-r1",
            result=result,
            quality=quality,
            num_frames=150,
            duration_seconds=345.6,
        )
        job = job_store.get_job("job-r1")
        assert job["result_json"] == result
        assert job["quality_json"] == quality
        assert job["num_frames"] == 150
        assert job["duration_seconds"] == pytest.approx(345.6)

    def test_save_result_without_quality(self, job_store):
        job_store.create_job("job-r2")
        job_store.save_result("job-r2", result={"foo": "bar"})
        job = job_store.get_job("job-r2")
        assert job["result_json"] == {"foo": "bar"}
        assert job["quality_json"] is None


class TestJobStoreDelete:
    """Test job deletion."""

    def test_delete_existing(self, job_store):
        job_store.create_job("job-del")
        assert job_store.delete_job("job-del") is True
        assert job_store.get_job("job-del") is None

    def test_delete_nonexistent(self, job_store):
        assert job_store.delete_job("nope") is False

    def test_delete_removes_from_list(self, job_store):
        job_store.create_job("job-del-2")
        job_store.create_job("job-keep")
        job_store.delete_job("job-del-2")
        jobs = job_store.list_jobs()
        assert len(jobs) == 1
        assert jobs[0]["id"] == "job-keep"


class TestJobStoreJsonParsing:
    """Test that JSON fields are properly serialized/deserialized."""

    def test_nested_config_roundtrip(self, job_store):
        config = {
            "max_iterations": 5000,
            "nested": {"a": [1, 2, 3], "b": True},
        }
        job_store.create_job("job-json", config=config)
        job = job_store.get_job("job-json")
        assert job["config_json"] == config
        assert job["config_json"]["nested"]["a"] == [1, 2, 3]

    def test_null_json_fields(self, job_store):
        job_store.create_job("job-null")
        job = job_store.get_job("job-null")
        assert job["config_json"] is None
        assert job["result_json"] is None
        assert job["quality_json"] is None


# =============================================================================
# FileStore tests
# =============================================================================


class TestFileStoreDirectories:
    """Test directory management."""

    def test_creates_base_dirs_on_init(self, file_store):
        assert file_store.uploads_dir.exists()
        assert file_store.cache_dir.exists()
        assert file_store.outputs_dir.exists()

    def test_get_upload_dir_creates_job_dir(self, file_store):
        d = file_store.get_upload_dir("job-001")
        assert d.exists()
        assert d.name == "job-001"
        assert d.parent == file_store.uploads_dir

    def test_get_cache_dir_creates_job_dir(self, file_store):
        d = file_store.get_cache_dir("job-001")
        assert d.exists()
        assert d.parent == file_store.cache_dir

    def test_get_output_dir_creates_job_dir(self, file_store):
        d = file_store.get_output_dir("job-001")
        assert d.exists()
        assert d.parent == file_store.outputs_dir

    def test_idempotent_dir_creation(self, file_store):
        d1 = file_store.get_upload_dir("job-idem")
        d2 = file_store.get_upload_dir("job-idem")
        assert d1 == d2


class TestFileStoreSaveUpload:
    """Test file upload saving."""

    def test_save_upload(self, file_store):
        content = b"fake video content"
        path = file_store.save_upload("job-up1", "video.mp4", content)
        assert path.exists()
        assert path.read_bytes() == content
        assert path.name == "video.mp4"

    def test_save_upload_preserves_filename(self, file_store):
        path = file_store.save_upload("job-up2", "my scene.mov", b"data")
        assert path.name == "my scene.mov"

    def test_save_multiple_uploads(self, file_store):
        file_store.save_upload("job-up3", "a.png", b"aaa")
        file_store.save_upload("job-up3", "b.png", b"bbb")
        upload_dir = file_store.get_upload_dir("job-up3")
        files = list(upload_dir.iterdir())
        assert len(files) == 2


class TestFileStoreOutputs:
    """Test output file listing and retrieval."""

    def test_list_outputs_empty(self, file_store):
        files = file_store.list_outputs("job-empty")
        assert files == []

    def test_list_outputs_with_files(self, file_store):
        output_dir = file_store.get_output_dir("job-out1")
        (output_dir / "model.ply").write_bytes(b"ply data")
        (output_dir / "mesh.obj").write_bytes(b"obj data")

        files = file_store.list_outputs("job-out1")
        assert len(files) == 2
        names = {f["name"] for f in files}
        assert names == {"model.ply", "mesh.obj"}

    def test_list_outputs_includes_metadata(self, file_store):
        output_dir = file_store.get_output_dir("job-out2")
        (output_dir / "model.ply").write_bytes(b"x" * 100)

        files = file_store.list_outputs("job-out2")
        assert files[0]["size_bytes"] == 100
        assert files[0]["suffix"] == ".ply"
        assert files[0]["name"] == "model.ply"

    def test_list_outputs_recursive(self, file_store):
        output_dir = file_store.get_output_dir("job-out3")
        subdir = output_dir / "renders"
        subdir.mkdir()
        (subdir / "frame_000.png").write_bytes(b"png")
        (output_dir / "model.ply").write_bytes(b"ply")

        files = file_store.list_outputs("job-out3")
        assert len(files) == 2

    def test_get_output_path_found(self, file_store):
        output_dir = file_store.get_output_dir("job-path1")
        (output_dir / "model.ply").write_bytes(b"data")

        path = file_store.get_output_path("job-path1", "model.ply")
        assert path is not None
        assert path.name == "model.ply"

    def test_get_output_path_not_found(self, file_store):
        file_store.get_output_dir("job-path2")  # Create dir but no files
        path = file_store.get_output_path("job-path2", "missing.ply")
        assert path is None

    def test_get_output_path_in_subdir(self, file_store):
        output_dir = file_store.get_output_dir("job-path3")
        subdir = output_dir / "exports"
        subdir.mkdir()
        (subdir / "mesh.obj").write_bytes(b"data")

        path = file_store.get_output_path("job-path3", "mesh.obj")
        assert path is not None


class TestFileStoreCleanup:
    """Test file cleanup."""

    def test_cleanup_removes_cache_and_uploads(self, file_store):
        # Create files in all dirs
        file_store.save_upload("job-clean", "v.mp4", b"video")
        cache = file_store.get_cache_dir("job-clean")
        (cache / "temp.bin").write_bytes(b"tmp")
        output = file_store.get_output_dir("job-clean")
        (output / "model.ply").write_bytes(b"ply")

        file_store.cleanup_job("job-clean", keep_outputs=True)

        assert not (file_store.uploads_dir / "job-clean").exists()
        assert not (file_store.cache_dir / "job-clean").exists()
        assert (file_store.outputs_dir / "job-clean").exists()  # Kept

    def test_cleanup_removes_outputs_when_requested(self, file_store):
        output = file_store.get_output_dir("job-clean2")
        (output / "model.ply").write_bytes(b"ply")

        file_store.cleanup_job("job-clean2", keep_outputs=False)
        assert not (file_store.outputs_dir / "job-clean2").exists()

    def test_delete_job_files_removes_everything(self, file_store):
        file_store.save_upload("job-del", "v.mp4", b"vid")
        cache = file_store.get_cache_dir("job-del")
        (cache / "t.bin").write_bytes(b"tmp")
        output = file_store.get_output_dir("job-del")
        (output / "model.ply").write_bytes(b"ply")

        file_store.delete_job_files("job-del")

        assert not (file_store.uploads_dir / "job-del").exists()
        assert not (file_store.cache_dir / "job-del").exists()
        assert not (file_store.outputs_dir / "job-del").exists()

    def test_cleanup_nonexistent_job_is_safe(self, file_store):
        # Should not raise
        file_store.cleanup_job("never-existed")
        file_store.delete_job_files("never-existed")


class TestJobStoreWalMode:
    """Test SQLite WAL mode is enabled."""

    def test_wal_mode(self, tmp_path):
        db_path = tmp_path / "wal_test.db"
        store = JobStore(db_path)
        conn = sqlite3.connect(str(db_path))
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.close()
        assert mode == "wal"

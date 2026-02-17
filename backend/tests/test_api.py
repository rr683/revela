"""Tests for FastAPI endpoints.

Uses HTTPX TestClient with patched storage. The Celery task import
in create_job is wrapped in try/except, so it gracefully handles
the worker being unavailable in tests.
"""

import io
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient

from storage import FileStore, JobStore
from engine.base import ReconstructionStatus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def _patch_stores(tmp_path):
    """Patch _get_stores in routes to use temp directories."""
    db_path = tmp_path / "test_api.db"
    data_dir = tmp_path / "data"
    job_store = JobStore(db_path)
    file_store = FileStore(data_dir)

    with patch("api.routes._get_stores", return_value=(job_store, file_store)):
        yield job_store, file_store


@pytest.fixture
def client(_patch_stores):
    """Provide a TestClient with patched storage."""
    from api.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture
def stores(_patch_stores):
    return _patch_stores


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


class TestHealth:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# POST /api/jobs
# ---------------------------------------------------------------------------


class TestCreateJob:
    def test_create_job_with_video(self, client):
        video = io.BytesIO(b"fake video content")
        resp = client.post(
            "/api/jobs",
            files={"video": ("test.mp4", video, "video/mp4")},
            data={"method": "splatfacto"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pending"
        assert data["method"] == "splatfacto"
        assert data["id"] is not None

    def test_create_job_with_images(self, client):
        images = [
            ("images", ("img1.png", io.BytesIO(b"png1"), "image/png")),
            ("images", ("img2.jpg", io.BytesIO(b"jpg2"), "image/jpeg")),
        ]
        resp = client.post("/api/jobs", files=images)
        assert resp.status_code == 201

    def test_create_job_with_video_and_images(self, client):
        files = [
            ("video", ("test.mp4", io.BytesIO(b"video"), "video/mp4")),
            ("images", ("img1.png", io.BytesIO(b"png1"), "image/png")),
        ]
        resp = client.post("/api/jobs", files=files)
        assert resp.status_code == 201

    def test_create_job_no_input_returns_400(self, client):
        resp = client.post("/api/jobs", data={"method": "splatfacto"})
        assert resp.status_code == 400 or resp.status_code == 422

    def test_create_job_unsupported_video_format(self, client):
        video = io.BytesIO(b"not a real video")
        resp = client.post(
            "/api/jobs",
            files={"video": ("test.flv", video, "video/x-flv")},
        )
        assert resp.status_code == 400
        assert "Unsupported video format" in resp.json()["detail"]

    def test_create_job_with_nerfacto_method(self, client):
        video = io.BytesIO(b"fake video")
        resp = client.post(
            "/api/jobs",
            files={"video": ("test.mp4", video, "video/mp4")},
            data={"method": "nerfacto"},
        )
        assert resp.status_code == 201
        assert resp.json()["method"] == "nerfacto"

    def test_create_job_with_max_iterations(self, client):
        video = io.BytesIO(b"fake video")
        resp = client.post(
            "/api/jobs",
            files={"video": ("test.mp4", video, "video/mp4")},
            data={"method": "splatfacto", "max_iterations": "5000"},
        )
        assert resp.status_code == 201

    def test_create_job_saves_uploaded_file(self, client, stores):
        _, file_store = stores
        video = io.BytesIO(b"actual video bytes here")
        resp = client.post(
            "/api/jobs",
            files={"video": ("my_scene.mp4", video, "video/mp4")},
        )
        job_id = resp.json()["id"]
        upload_dir = file_store.uploads_dir / job_id
        assert upload_dir.exists()
        saved_files = list(upload_dir.rglob("*"))
        assert any(f.name == "my_scene.mp4" for f in saved_files)

    def test_create_job_returns_unique_ids(self, client):
        ids = set()
        for _ in range(5):
            video = io.BytesIO(b"v")
            resp = client.post(
                "/api/jobs",
                files={"video": ("a.mp4", video, "video/mp4")},
            )
            ids.add(resp.json()["id"])
        assert len(ids) == 5


# ---------------------------------------------------------------------------
# GET /api/jobs
# ---------------------------------------------------------------------------


class TestListJobs:
    def test_list_empty(self, client):
        resp = client.get("/api/jobs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["jobs"] == []
        assert data["total"] == 0

    def test_list_after_create(self, client):
        video = io.BytesIO(b"vid")
        client.post(
            "/api/jobs",
            files={"video": ("a.mp4", video, "video/mp4")},
        )
        resp = client.get("/api/jobs")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_list_with_status_filter(self, client, stores):
        job_store, _ = stores
        job_store.create_job("manual-1")
        job_store.create_job("manual-2")
        job_store.update_status("manual-1", ReconstructionStatus.COMPLETED.value)

        resp = client.get("/api/jobs?status=completed")
        assert resp.status_code == 200
        jobs = resp.json()["jobs"]
        assert len(jobs) == 1
        assert jobs[0]["id"] == "manual-1"

    def test_list_with_limit(self, client, stores):
        job_store, _ = stores
        for i in range(5):
            job_store.create_job(f"lim-{i}")

        resp = client.get("/api/jobs?limit=2")
        assert resp.status_code == 200
        assert len(resp.json()["jobs"]) == 2


# ---------------------------------------------------------------------------
# GET /api/jobs/{job_id}
# ---------------------------------------------------------------------------


class TestGetJob:
    def test_get_existing(self, client, stores):
        job_store, _ = stores
        job_store.create_job("get-me")

        resp = client.get("/api/jobs/get-me")
        assert resp.status_code == 200
        assert resp.json()["id"] == "get-me"

    def test_get_nonexistent_returns_404(self, client):
        resp = client.get("/api/jobs/no-such-job")
        assert resp.status_code == 404

    def test_get_shows_updated_status(self, client, stores):
        job_store, _ = stores
        job_store.create_job("status-job")
        job_store.update_status("status-job", ReconstructionStatus.TRAINING.value)

        resp = client.get("/api/jobs/status-job")
        assert resp.json()["status"] == "training"

    def test_get_shows_result_after_completion(self, client, stores):
        job_store, _ = stores
        job_store.create_job("result-job")
        job_store.save_result(
            "result-job",
            result={"output_files": {"ply": "/out/model.ply"}},
            quality={"psnr": 30.0},
            num_frames=100,
            duration_seconds=60.0,
        )
        job_store.update_status("result-job", ReconstructionStatus.COMPLETED.value)

        resp = client.get("/api/jobs/result-job")
        data = resp.json()
        assert data["status"] == "completed"
        assert data["outputs"]["output_files"]["ply"] == "/out/model.ply"
        assert data["quality"]["psnr"] == 30.0
        assert data["num_frames"] == 100


# ---------------------------------------------------------------------------
# DELETE /api/jobs/{job_id}
# ---------------------------------------------------------------------------


class TestDeleteJob:
    def test_delete_pending_job(self, client, stores):
        job_store, _ = stores
        job_store.create_job("del-me")

        resp = client.delete("/api/jobs/del-me")
        assert resp.status_code == 200

        resp = client.get("/api/jobs/del-me")
        assert resp.status_code == 404

    def test_delete_completed_job(self, client, stores):
        job_store, _ = stores
        job_store.create_job("del-done")
        job_store.update_status("del-done", ReconstructionStatus.COMPLETED.value)

        resp = client.delete("/api/jobs/del-done")
        assert resp.status_code == 200

    def test_delete_failed_job(self, client, stores):
        job_store, _ = stores
        job_store.create_job("del-fail")
        job_store.update_status(
            "del-fail", ReconstructionStatus.FAILED.value, error_message="boom"
        )

        resp = client.delete("/api/jobs/del-fail")
        assert resp.status_code == 200

    def test_delete_running_job_returns_409(self, client, stores):
        job_store, _ = stores
        job_store.create_job("del-running")
        job_store.update_status("del-running", ReconstructionStatus.TRAINING.value)

        resp = client.delete("/api/jobs/del-running")
        assert resp.status_code == 409

    def test_delete_preprocessing_job_returns_409(self, client, stores):
        job_store, _ = stores
        job_store.create_job("del-pre")
        job_store.update_status("del-pre", ReconstructionStatus.PREPROCESSING.value)

        resp = client.delete("/api/jobs/del-pre")
        assert resp.status_code == 409

    def test_delete_nonexistent_returns_404(self, client):
        resp = client.delete("/api/jobs/ghost")
        assert resp.status_code == 404

    def test_delete_cleans_up_files(self, client, stores):
        job_store, file_store = stores
        job_store.create_job("del-files")
        file_store.save_upload("del-files", "v.mp4", b"data")
        output_dir = file_store.get_output_dir("del-files")
        (output_dir / "model.ply").write_bytes(b"ply")

        resp = client.delete("/api/jobs/del-files")
        assert resp.status_code == 200

        assert not (file_store.uploads_dir / "del-files").exists()
        assert not (file_store.outputs_dir / "del-files").exists()


# ---------------------------------------------------------------------------
# GET /api/jobs/{job_id}/outputs
# ---------------------------------------------------------------------------


class TestListOutputs:
    def test_list_outputs_empty(self, client, stores):
        job_store, _ = stores
        job_store.create_job("out-empty")

        resp = client.get("/api/jobs/out-empty/outputs")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_outputs_with_files(self, client, stores):
        job_store, file_store = stores
        job_store.create_job("out-files")
        output_dir = file_store.get_output_dir("out-files")
        (output_dir / "model.ply").write_bytes(b"ply data")
        (output_dir / "mesh.obj").write_bytes(b"obj data")

        resp = client.get("/api/jobs/out-files/outputs")
        assert resp.status_code == 200
        files = resp.json()
        assert len(files) == 2

    def test_list_outputs_nonexistent_job(self, client):
        resp = client.get("/api/jobs/no-job/outputs")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/jobs/{job_id}/outputs/{filename}
# ---------------------------------------------------------------------------


class TestDownloadOutput:
    def test_download_existing_file(self, client, stores):
        job_store, file_store = stores
        job_store.create_job("dl-job")
        output_dir = file_store.get_output_dir("dl-job")
        (output_dir / "model.ply").write_bytes(b"ply binary data")

        resp = client.get("/api/jobs/dl-job/outputs/model.ply")
        assert resp.status_code == 200
        assert resp.content == b"ply binary data"

    def test_download_missing_file_returns_404(self, client, stores):
        job_store, _ = stores
        job_store.create_job("dl-miss")

        resp = client.get("/api/jobs/dl-miss/outputs/missing.ply")
        assert resp.status_code == 404

    def test_download_from_nonexistent_job(self, client):
        resp = client.get("/api/jobs/no-job/outputs/file.ply")
        assert resp.status_code == 404

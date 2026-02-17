"""Shared fixtures for all tests."""

import importlib.util
import sys
from pathlib import Path

import pytest

backend_dir = str(Path(__file__).parent.parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Pre-load engine.base directly (bypasses engine/__init__.py which
# imports NerfstudioWrapper -> torch, unavailable in test env).
_base_path = Path(__file__).parent.parent / "engine" / "base.py"
_base_spec = importlib.util.spec_from_file_location("engine.base", str(_base_path))
_base_mod = importlib.util.module_from_spec(_base_spec)
_base_spec.loader.exec_module(_base_mod)
sys.modules["engine.base"] = _base_mod

# Also pre-load engine.gltf_converter directly (no torch dependency).
_gltf_path = Path(__file__).parent.parent / "engine" / "gltf_converter.py"
_gltf_spec = importlib.util.spec_from_file_location("engine.gltf_converter", str(_gltf_path))
_gltf_mod = importlib.util.module_from_spec(_gltf_spec)
_gltf_spec.loader.exec_module(_gltf_mod)
sys.modules["engine.gltf_converter"] = _gltf_mod

from storage import FileStore, JobStore


@pytest.fixture
def tmp_dir(tmp_path):
    """Provide a clean temp directory."""
    return tmp_path


@pytest.fixture
def job_store(tmp_path):
    """Provide a fresh JobStore backed by a temp SQLite DB."""
    db_path = tmp_path / "test.db"
    return JobStore(db_path)


@pytest.fixture
def file_store(tmp_path):
    """Provide a fresh FileStore backed by a temp directory."""
    return FileStore(tmp_path / "data")

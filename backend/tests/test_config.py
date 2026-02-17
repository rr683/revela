"""Tests for configuration loading."""

import os
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.config_loader import Config, ConfigLoader


@pytest.fixture(autouse=True)
def reset_config():
    """Reset the singleton config between tests."""
    ConfigLoader._instance = None
    yield
    ConfigLoader._instance = None


class TestConfigDefaults:
    """Test that default config loads and has sane values."""

    def test_load_default(self):
        config = ConfigLoader.load()
        assert isinstance(config, Config)

    def test_reconstruction_defaults(self):
        config = ConfigLoader.load()
        assert config.reconstruction.default_method == "splatfacto"
        assert config.reconstruction.max_iterations == 30000
        assert config.reconstruction.resolution == 1024

    def test_preprocessing_defaults(self):
        config = ConfigLoader.load()
        assert config.preprocessing.frame_extraction.fps == 10
        assert config.preprocessing.frame_extraction.max_frames == 300
        assert ".png" in config.preprocessing.image_ingestion.supported_formats

    def test_colmap_defaults(self):
        config = ConfigLoader.load()
        assert config.colmap.feature_extraction.detector == "sift"

    def test_api_defaults(self):
        config = ConfigLoader.load()
        assert config.api.port == 8000
        assert config.api.max_upload_size_mb == 2048
        assert ".mp4" in config.api.allowed_video_formats

    def test_celery_defaults(self):
        config = ConfigLoader.load()
        assert "redis" in config.celery.broker_url
        assert config.celery.task_serializer == "json"

    def test_storage_defaults(self):
        config = ConfigLoader.load()
        assert config.storage.cache_dir == "data/cache"


class TestConfigSingleton:
    """Test that the config loader is a singleton."""

    def test_returns_same_instance(self):
        c1 = ConfigLoader.load()
        c2 = ConfigLoader.load()
        assert c1 is c2

    def test_reload_creates_new_instance(self):
        c1 = ConfigLoader.load()
        c2 = ConfigLoader.reload()
        assert c1 is not c2


class TestConfigFromCustomFile:
    """Test loading from a custom YAML file."""

    def test_custom_yaml(self, tmp_path):
        custom = tmp_path / "custom.yaml"
        custom.write_text(yaml.dump({
            "reconstruction": {"default_method": "nerfacto", "max_iterations": 100},
            "api": {"port": 9999},
        }))

        config = ConfigLoader.reload(str(custom))
        assert config.reconstruction.default_method == "nerfacto"
        assert config.reconstruction.max_iterations == 100
        assert config.api.port == 9999

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            ConfigLoader.reload("/nonexistent/path.yaml")

    def test_partial_yaml_uses_defaults(self, tmp_path):
        partial = tmp_path / "partial.yaml"
        partial.write_text(yaml.dump({"reconstruction": {"max_iterations": 42}}))

        config = ConfigLoader.reload(str(partial))
        assert config.reconstruction.max_iterations == 42
        assert config.reconstruction.default_method == "splatfacto"  # default


class TestEnvOverrides:
    """Test that environment variables override config values."""

    def test_env_overrides_int(self, monkeypatch, tmp_path):
        cfg_file = tmp_path / "env.yaml"
        cfg_file.write_text(yaml.dump({"api": {"port": 8000}}))

        monkeypatch.setenv("VIDEO3D_API_PORT", "9090")
        config = ConfigLoader.reload(str(cfg_file))
        assert config.api.port == 9090

    def test_env_overrides_bool(self, monkeypatch, tmp_path):
        cfg_file = tmp_path / "env2.yaml"
        cfg_file.write_text(yaml.dump({"development": {"debug": True}}))

        monkeypatch.setenv("VIDEO3D_DEVELOPMENT_DEBUG", "false")
        config = ConfigLoader.reload(str(cfg_file))

    def test_env_overrides_string(self, monkeypatch, tmp_path):
        cfg_file = tmp_path / "env3.yaml"
        cfg_file.write_text(yaml.dump({
            "celery": {"timezone": "UTC"}
        }))

        monkeypatch.setenv("VIDEO3D_CELERY_TIMEZONE", "US/Eastern")
        config = ConfigLoader.reload(str(cfg_file))
        assert config.celery.timezone == "US/Eastern"


class TestConfigModelDump:
    """Test that config models can be serialized."""

    def test_reconstruction_model_dump(self):
        config = ConfigLoader.load()
        d = config.reconstruction.model_dump()
        assert isinstance(d, dict)
        assert "default_method" in d

    def test_preprocessing_model_dump(self):
        config = ConfigLoader.load()
        d = config.preprocessing.model_dump()
        assert "frame_extraction" in d
        assert "image_ingestion" in d

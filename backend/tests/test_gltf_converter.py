"""Tests for the glTF/GLB converter module."""

import pytest
from pathlib import Path
from engine.base import OutputFormat


class TestOutputFormatEnum:
    """Verify the GLTF format is properly registered."""

    def test_gltf_in_output_formats(self):
        assert OutputFormat.GLTF == "gltf"
        assert OutputFormat.GLTF.value == "gltf"

    def test_all_formats_present(self):
        expected = {"ply", "mesh", "splat", "gltf", "depth", "video"}
        actual = {f.value for f in OutputFormat}
        assert expected == actual

    def test_default_output_includes_mesh(self):
        """ReconstructionInput defaults should include mesh format."""
        from engine.base import ReconstructionInput

        ri = ReconstructionInput(job_id="test")
        format_values = {f.value for f in ri.output_formats}
        assert "ply" in format_values
        assert "mesh" in format_values


class TestGltfConverterImport:
    """Test that the converter module is importable and has correct API."""

    def test_import_ply_to_gltf(self):
        from engine.gltf_converter import ply_to_gltf
        assert callable(ply_to_gltf)

    def test_ply_to_gltf_requires_trimesh(self, tmp_path):
        """If trimesh is missing, should raise ImportError with helpful message."""
        from engine.gltf_converter import ply_to_gltf

        # Only run this test if trimesh is NOT installed
        try:
            import trimesh  # noqa: F401
            pytest.skip("trimesh is installed -- cannot test missing import path")
        except ImportError:
            with pytest.raises(ImportError, match="trimesh"):
                ply_to_gltf(tmp_path / "in.ply", tmp_path / "out.glb")


class TestGltfConverterWithTrimesh:
    """Integration tests that require trimesh to be installed."""

    @pytest.fixture
    def sample_ply(self, tmp_path):
        """Create a minimal valid PLY file with a cube mesh."""
        try:
            import trimesh
        except ImportError:
            pytest.skip("trimesh not installed")

        mesh = trimesh.creation.box()
        ply_path = tmp_path / "test.ply"
        mesh.export(str(ply_path))
        return ply_path

    def test_convert_ply_mesh_to_glb(self, sample_ply, tmp_path):
        from engine.gltf_converter import ply_to_gltf

        output = tmp_path / "output.glb"
        result = ply_to_gltf(sample_ply, output)

        assert result == output
        assert output.exists()
        assert output.stat().st_size > 0

    def test_convert_with_simplification(self, sample_ply, tmp_path):
        from engine.gltf_converter import ply_to_gltf

        output = tmp_path / "simplified.glb"
        result = ply_to_gltf(sample_ply, output, simplify_ratio=0.5)

        assert result == output
        assert output.exists()

    def test_creates_parent_directories(self, sample_ply, tmp_path):
        from engine.gltf_converter import ply_to_gltf

        output = tmp_path / "nested" / "dir" / "model.glb"
        result = ply_to_gltf(sample_ply, output)

        assert result.exists()

    def test_pointcloud_ply_to_glb(self, tmp_path):
        """Convert a point cloud (no faces) to GLB."""
        try:
            import trimesh
            import numpy as np
        except ImportError:
            pytest.skip("trimesh/numpy not installed")

        from engine.gltf_converter import ply_to_gltf

        # Create a point cloud PLY (no faces)
        points = np.random.rand(100, 3).astype(np.float32)
        cloud = trimesh.PointCloud(points)
        ply_path = tmp_path / "cloud.ply"
        cloud.export(str(ply_path))

        output = tmp_path / "cloud.glb"
        result = ply_to_gltf(ply_path, output)

        assert result.exists()
        assert result.stat().st_size > 0

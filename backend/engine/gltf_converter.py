"""
glTF/GLB Converter

Converts PLY point clouds and meshes to glTF 2.0 / GLB format for
use in game engines (Unity, Unreal), web viewers, and asset marketplaces.

Uses trimesh for conversion. Supports:
- PLY point cloud -> GLB mesh (via ball-pivoting or Poisson reconstruction)
- PLY mesh -> GLB (direct conversion with materials)
- OBJ mesh -> GLB
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def ply_to_gltf(
    input_path: Path,
    output_path: Path,
    simplify_ratio: Optional[float] = None,
) -> Path:
    """
    Convert a PLY file (point cloud or mesh) to GLB format.

    Args:
        input_path: Path to source .ply file
        output_path: Path for output .glb file
        simplify_ratio: If set (0.0-1.0), decimate mesh to this fraction of faces.
                        Useful for generating game-ready LODs.

    Returns:
        Path to the exported .glb file

    Raises:
        ImportError: If trimesh is not installed
        ValueError: If the input file cannot be loaded
    """
    try:
        import trimesh
    except ImportError:
        raise ImportError(
            "trimesh is required for glTF export. Install with: pip install trimesh[easy]"
        )

    logger.info(f"Converting {input_path} -> {output_path}")

    loaded = trimesh.load(str(input_path))

    # trimesh.load returns different types depending on the file
    if isinstance(loaded, trimesh.PointCloud):
        mesh = _pointcloud_to_mesh(loaded)
    elif isinstance(loaded, trimesh.Scene):
        mesh = loaded.to_geometry()
        if isinstance(mesh, trimesh.PointCloud):
            mesh = _pointcloud_to_mesh(mesh)
    elif isinstance(loaded, trimesh.Trimesh):
        mesh = loaded
    else:
        raise ValueError(f"Unexpected trimesh type: {type(loaded)}")

    # Optional decimation for game-ready assets
    if simplify_ratio is not None and 0 < simplify_ratio < 1.0:
        target_faces = int(len(mesh.faces) * simplify_ratio)
        if target_faces > 0:
            mesh = mesh.simplify_quadric_decimation(target_faces)
            logger.info(
                f"Simplified mesh to {len(mesh.faces)} faces "
                f"({simplify_ratio:.0%} of original)"
            )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(str(output_path), file_type="glb")

    logger.info(f"Exported GLB: {output_path} ({output_path.stat().st_size / 1024:.0f} KB)")
    return output_path


def _pointcloud_to_mesh(cloud: "trimesh.PointCloud") -> "trimesh.Trimesh":
    """
    Convert a point cloud to a mesh via ball-pivoting or convex hull fallback.

    For production quality, COLMAP/Poisson reconstruction is preferred,
    but this works as a quick conversion path.
    """
    import trimesh
    import numpy as np

    points = np.array(cloud.vertices)

    # Try open3d ball-pivoting if available (better quality)
    try:
        import open3d as o3d

        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(points)
        pcd.estimate_normals()

        distances = pcd.compute_nearest_neighbor_distance()
        avg_dist = np.mean(distances)
        radii = [avg_dist * 1.5, avg_dist * 3.0, avg_dist * 6.0]

        o3d_mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_ball_pivoting(
            pcd, o3d.utility.DoubleVector(radii)
        )

        vertices = np.asarray(o3d_mesh.vertices)
        faces = np.asarray(o3d_mesh.triangles)

        mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
        if hasattr(cloud, "colors") and cloud.colors is not None:
            mesh.visual.vertex_colors = cloud.colors
        return mesh

    except ImportError:
        logger.warning("open3d not available, falling back to convex hull")

    # Fallback: Delaunay / convex hull (fast, lower quality)
    mesh = trimesh.Trimesh(vertices=points)
    mesh = mesh.convex_hull
    return mesh

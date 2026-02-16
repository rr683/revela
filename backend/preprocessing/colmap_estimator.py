"""
COLMAP Integration

Handles camera pose estimation using COLMAP Structure-from-Motion.

Pipeline:
1. Feature extraction from frames
2. Feature matching (sequential or exhaustive)
3. Sparse reconstruction (bundle adjustment)
4. Export camera poses and intrinsics

Falls back to mock poses if COLMAP is not installed (for development).
"""

import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple
import sys

import numpy as np

from .base import CameraIntrinsics, CameraPose, PoseEstimationError

logger = logging.getLogger(__name__)


def check_colmap_installed() -> bool:
    """Check if COLMAP is installed and available."""
    try:
        result = subprocess.run(
            ['colmap', '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


class COLMAPPoseEstimator:
    """
    Estimates camera poses from image sequences using COLMAP.
    
    COLMAP performs:
    1. Feature extraction (SIFT by default)
    2. Feature matching (sequential for video)
    3. Sparse reconstruction (Structure-from-Motion)
    4. Bundle adjustment to refine poses
    """
    
    def __init__(self, config: dict):
        """
        Initialize COLMAP pose estimator.
        
        Args:
            config: Configuration dict from config.colmap
        """
        self.config = config
        self.feature_config = config.get('feature_extraction', {})
        self.matching_config = config.get('matching', {})
        self.ba_config = config.get('bundle_adjustment', {})
        
        # Check if COLMAP is installed
        self.colmap_available = check_colmap_installed()
        
        if not self.colmap_available:
            logger.warning(
                "COLMAP is not installed. Install with: conda install -c conda-forge colmap\n"
                "Falling back to mock pose generation for testing."
            )
        else:
            logger.info("COLMAP is available")
    
    def estimate_poses(
        self,
        frame_paths: List[Path],
        workspace_dir: Path,
        progress_callback: Optional[callable] = None
    ) -> Tuple[List[CameraPose], CameraIntrinsics]:
        """
        Estimate camera poses for a sequence of frames.
        
        Args:
            frame_paths: List of image file paths
            workspace_dir: Directory for COLMAP database and outputs
            progress_callback: Optional callback(message, progress)
        
        Returns:
            Tuple of (camera_poses, camera_intrinsics)
        
        Raises:
            PoseEstimationError: If pose estimation fails
        """
        if not self.colmap_available:
            logger.warning("Using mock poses (COLMAP not installed)")
            return self._generate_mock_poses(frame_paths)
        
        logger.info(f"Estimating poses for {len(frame_paths)} frames")
        
        workspace_dir = Path(workspace_dir)
        workspace_dir.mkdir(parents=True, exist_ok=True)
        
        # Create COLMAP workspace structure
        database_path = workspace_dir / "database.db"
        sparse_dir = workspace_dir / "sparse"
        sparse_dir.mkdir(exist_ok=True)
        
        try:
            # Step 1: Feature extraction
            if progress_callback:
                progress_callback("Extracting features", 0.2)
            
            self._extract_features(frame_paths, database_path, workspace_dir)
            logger.info("Feature extraction complete")
            
            # Step 2: Feature matching
            if progress_callback:
                progress_callback("Matching features", 0.4)
            
            self._match_features(database_path)
            logger.info("Feature matching complete")
            
            # Step 3: Sparse reconstruction
            if progress_callback:
                progress_callback("Running sparse reconstruction", 0.6)
            
            self._sparse_reconstruction(database_path, sparse_dir, workspace_dir)
            logger.info("Sparse reconstruction complete")
            
            # Step 4: Parse results
            if progress_callback:
                progress_callback("Parsing results", 0.9)
            
            poses, intrinsics = self._parse_colmap_output(sparse_dir, frame_paths)
            logger.info(f"Extracted {len(poses)} camera poses")
            
            return poses, intrinsics
            
        except Exception as e:
            logger.error(f"COLMAP pose estimation failed: {e}")
            raise PoseEstimationError(f"Pose estimation failed: {e}")
    
    def _extract_features(
        self,
        frame_paths: List[Path],
        database_path: Path,
        workspace_dir: Path
    ):
        """Extract features from images using COLMAP."""
        
        # COLMAP expects images in a specific directory
        image_dir = workspace_dir / "images"
        image_dir.mkdir(exist_ok=True)
        
        # Create symlinks or copy images
        for frame_path in frame_paths:
            link_path = image_dir / frame_path.name
            if not link_path.exists():
                try:
                    # Try symlink first (faster)
                    link_path.symlink_to(frame_path.absolute())
                except (OSError, NotImplementedError):
                    # Fall back to copy (Windows may require admin for symlinks)
                    shutil.copy(frame_path, link_path)
        
        # Build COLMAP feature extraction command
        cmd = [
            'colmap', 'feature_extractor',
            '--database_path', str(database_path),
            '--image_path', str(image_dir),
        ]
        
        # Add configuration options
        detector = self.feature_config.get('detector', 'sift').upper()
        if detector == 'SIFT':
            cmd.extend([
                '--SiftExtraction.max_num_features',
                str(self.feature_config.get('max_features', 8192))
            ])
        
        if self.feature_config.get('use_gpu', True):
            cmd.extend(['--SiftExtraction.use_gpu', '1'])
        else:
            cmd.extend(['--SiftExtraction.use_gpu', '0'])
        
        logger.info(f"Running: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"COLMAP feature extraction failed:\n{result.stderr}")
            raise PoseEstimationError(f"Feature extraction failed: {result.stderr}")
    
    def _match_features(self, database_path: Path):
        """Match features between images."""
        
        method = self.matching_config.get('method', 'sequential')
        
        if method == 'sequential':
            # Sequential matching for video (faster, assumes ordered frames)
            cmd = [
                'colmap', 'sequential_matcher',
                '--database_path', str(database_path),
                '--SequentialMatching.overlap',
                str(self.matching_config.get('overlap', 10))
            ]
        elif method == 'exhaustive':
            # Exhaustive matching (slower but more robust)
            cmd = [
                'colmap', 'exhaustive_matcher',
                '--database_path', str(database_path)
            ]
        else:
            raise ValueError(f"Unknown matching method: {method}")
        
        if self.matching_config.get('use_gpu', True):
            cmd.extend(['--SiftMatching.use_gpu', '1'])
        else:
            cmd.extend(['--SiftMatching.use_gpu', '0'])
        
        logger.info(f"Running: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"COLMAP feature matching failed:\n{result.stderr}")
            raise PoseEstimationError(f"Feature matching failed: {result.stderr}")
    
    def _sparse_reconstruction(
        self,
        database_path: Path,
        sparse_dir: Path,
        workspace_dir: Path
    ):
        """Run sparse reconstruction (Structure-from-Motion)."""
        
        output_dir = sparse_dir / "0"
        output_dir.mkdir(exist_ok=True)
        
        cmd = [
            'colmap', 'mapper',
            '--database_path', str(database_path),
            '--image_path', str(workspace_dir / "images"),
            '--output_path', str(sparse_dir)
        ]
        
        # Bundle adjustment settings
        if not self.ba_config.get('refine_focal_length', True):
            cmd.extend(['--Mapper.ba_refine_focal_length', '0'])
        
        if not self.ba_config.get('refine_principal_point', True):
            cmd.extend(['--Mapper.ba_refine_principal_point', '0'])
        
        if not self.ba_config.get('refine_extra_params', True):
            cmd.extend(['--Mapper.ba_refine_extra_params', '0'])
        
        logger.info(f"Running: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
        if result.returncode != 0:
            logger.error(f"COLMAP mapper failed:\n{result.stderr}")
            raise PoseEstimationError(f"Sparse reconstruction failed: {result.stderr}")
    
    def _parse_colmap_output(
        self,
        sparse_dir: Path,
        frame_paths: List[Path]
    ) -> Tuple[List[CameraPose], CameraIntrinsics]:
        """
        Parse COLMAP output to extract poses and intrinsics.
        
        COLMAP stores results in:
        - cameras.txt: Camera intrinsics
        - images.txt: Image poses
        - points3D.txt: 3D points (not used here)
        """
        # Find reconstruction directory (usually sparse/0)
        recon_dirs = list(sparse_dir.glob("*/"))
        if not recon_dirs:
            raise PoseEstimationError("No COLMAP reconstruction found")
        
        recon_dir = recon_dirs[0]
        
        # Convert binary to text format (easier to parse)
        self._export_colmap_text(recon_dir)
        
        # Parse cameras.txt
        cameras_file = recon_dir / "cameras.txt"
        images_file = recon_dir / "images.txt"
        
        if not cameras_file.exists() or not images_file.exists():
            raise PoseEstimationError("COLMAP output files not found")
        
        # Read camera intrinsics
        intrinsics = self._read_cameras_txt(cameras_file)
        
        # Read camera poses
        poses = self._read_images_txt(images_file, frame_paths)
        
        return poses, intrinsics
    
    def _export_colmap_text(self, recon_dir: Path):
        """Convert COLMAP binary output to text format."""
        cmd = [
            'colmap', 'model_converter',
            '--input_path', str(recon_dir),
            '--output_path', str(recon_dir),
            '--output_type', 'TXT'
        ]
        
        subprocess.run(cmd, capture_output=True, text=True, check=True)
    
    def _read_cameras_txt(self, cameras_file: Path) -> CameraIntrinsics:
        """Parse cameras.txt to extract intrinsics."""
        with open(cameras_file, 'r') as f:
            lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        
        if not lines:
            raise PoseEstimationError("No cameras found in COLMAP output")
        
        # Parse first camera (assume single camera)
        # Format: CAMERA_ID MODEL WIDTH HEIGHT PARAMS
        parts = lines[0].split()
        camera_id = int(parts[0])
        model = parts[1]
        width = int(parts[2])
        height = int(parts[3])
        params = [float(p) for p in parts[4:]]
        
        # Extract focal length and principal point based on model
        if model in ['PINHOLE', 'SIMPLE_PINHOLE']:
            if model == 'SIMPLE_PINHOLE':
                # f, cx, cy
                fx = fy = params[0]
                cx, cy = params[1], params[2]
                distortion = None
            else:
                # fx, fy, cx, cy
                fx, fy, cx, cy = params[:4]
                distortion = None
        elif model in ['RADIAL', 'SIMPLE_RADIAL']:
            # f, cx, cy, k1, [k2]
            fx = fy = params[0]
            cx, cy = params[1], params[2]
            distortion = params[3:] if len(params) > 3 else None
        elif model == 'OPENCV':
            # fx, fy, cx, cy, k1, k2, p1, p2
            fx, fy, cx, cy = params[:4]
            distortion = params[4:8] if len(params) >= 8 else None
        else:
            logger.warning(f"Unknown camera model: {model}, using default parsing")
            fx = fy = params[0] if params else width
            cx, cy = width / 2, height / 2
            distortion = None
        
        return CameraIntrinsics(
            width=width,
            height=height,
            fx=fx,
            fy=fy,
            cx=cx,
            cy=cy,
            distortion=distortion
        )
    
    def _read_images_txt(
        self,
        images_file: Path,
        frame_paths: List[Path]
    ) -> List[CameraPose]:
        """Parse images.txt to extract camera poses."""
        with open(images_file, 'r') as f:
            lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        
        # images.txt has paired lines:
        # Line 1: IMAGE_ID QW QX QY QZ TX TY TZ CAMERA_ID NAME
        # Line 2: POINTS2D[] as (X, Y, POINT3D_ID)
        
        poses = []
        image_name_to_path = {p.name: p for p in frame_paths}
        
        for i in range(0, len(lines), 2):
            if i + 1 >= len(lines):
                break
            
            # Parse image line
            parts = lines[i].split()
            image_id = int(parts[0])
            
            # Quaternion (qw, qx, qy, qz)
            qw, qx, qy, qz = map(float, parts[1:5])
            
            # Translation (tx, ty, tz)
            tx, ty, tz = map(float, parts[5:8])
            
            camera_id = int(parts[8])
            image_name = parts[9]
            
            # Convert quaternion to rotation matrix
            rotation = self._quat_to_rotation_matrix(qw, qx, qy, qz)
            
            # COLMAP uses world-to-camera transformation
            # We want camera-to-world, so invert
            rotation = rotation.T
            position = -rotation @ np.array([tx, ty, tz])
            
            # Find corresponding frame
            if image_name in image_name_to_path:
                frame_path = image_name_to_path[image_name]
                frame_id = frame_paths.index(frame_path)
            else:
                logger.warning(f"Image {image_name} not found in frame paths")
                continue
            
            pose = CameraPose(
                frame_id=frame_id,
                timestamp=frame_id / 30.0,  # Assume 30 FPS
                position=position.tolist(),
                rotation=rotation.tolist(),
                confidence=1.0  # COLMAP doesn't provide per-pose confidence
            )
            
            poses.append(pose)
        
        # Sort by frame_id
        poses.sort(key=lambda p: p.frame_id)
        
        return poses
    
    @staticmethod
    def _quat_to_rotation_matrix(qw: float, qx: float, qy: float, qz: float) -> np.ndarray:
        """Convert quaternion to 3x3 rotation matrix."""
        # Normalize quaternion
        norm = np.sqrt(qw**2 + qx**2 + qy**2 + qz**2)
        qw, qx, qy, qz = qw/norm, qx/norm, qy/norm, qz/norm
        
        # Compute rotation matrix
        R = np.array([
            [1 - 2*(qy**2 + qz**2), 2*(qx*qy - qw*qz), 2*(qx*qz + qw*qy)],
            [2*(qx*qy + qw*qz), 1 - 2*(qx**2 + qz**2), 2*(qy*qz - qw*qx)],
            [2*(qx*qz - qw*qy), 2*(qy*qz + qw*qx), 1 - 2*(qx**2 + qy**2)]
        ])
        
        return R
    
    def _generate_mock_poses(
        self,
        frame_paths: List[Path]
    ) -> Tuple[List[CameraPose], CameraIntrinsics]:
        """
        Generate mock camera poses for testing when COLMAP is not available.
        
        Creates a simple circular trajectory around the origin.
        """
        logger.warning("Generating mock poses - NOT suitable for production use!")
        
        num_frames = len(frame_paths)
        poses = []
        
        # Simple circular trajectory
        radius = 2.0
        for i, frame_path in enumerate(frame_paths):
            angle = (i / num_frames) * 2 * np.pi
            
            # Camera position
            x = radius * np.cos(angle)
            y = radius * np.sin(angle)
            z = 0.5
            
            # Look at origin
            forward = np.array([0, 0, 0]) - np.array([x, y, z])
            forward = forward / np.linalg.norm(forward)
            
            # Compute rotation matrix (simple version)
            up = np.array([0, 0, 1])
            right = np.cross(forward, up)
            right = right / np.linalg.norm(right)
            up = np.cross(right, forward)
            
            rotation = np.column_stack([right, up, -forward])
            
            pose = CameraPose(
                frame_id=i,
                timestamp=i / 30.0,
                position=[x, y, z],
                rotation=rotation.tolist(),
                confidence=0.5  # Low confidence for mock data
            )
            poses.append(pose)
        
        # Mock intrinsics (assume 1920x1080 with typical focal length)
        intrinsics = CameraIntrinsics(
            width=1920,
            height=1080,
            fx=1000.0,
            fy=1000.0,
            cx=960.0,
            cy=540.0,
            distortion=None
        )
        
        return poses, intrinsics

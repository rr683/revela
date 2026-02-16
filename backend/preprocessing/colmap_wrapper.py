"""
COLMAP Integration

Wraps COLMAP (Structure-from-Motion) for camera pose estimation.

Pipeline:
1. Feature extraction from frames
2. Feature matching (sequential, exhaustive, or vocab tree)
3. Sparse reconstruction (bundle adjustment)
4. Extract camera intrinsics and poses

COLMAP documentation: https://colmap.github.io/
"""

import logging
import subprocess
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
import json

from ..engine.base import CameraIntrinsics, CameraPose

logger = logging.getLogger(__name__)


class COLMAPWrapper:
    """
    Wrapper for COLMAP Structure-from-Motion.
    
    Estimates camera poses and intrinsics from a set of images.
    """
    
    def __init__(self, config: dict):
        """
        Initialize COLMAP wrapper.
        
        Args:
            config: Configuration dict from config.colmap
        """
        self.config = config
        self.feature_config = config.get('feature_extraction', {})
        self.matching_config = config.get('matching', {})
        self.ba_config = config.get('bundle_adjustment', {})
        
        # Verify COLMAP is installed
        if not self._check_colmap_installed():
            raise RuntimeError(
                "COLMAP not found. Install with: conda install -c conda-forge colmap"
            )
        
        logger.info("Initialized COLMAPWrapper")
    
    def _check_colmap_installed(self) -> bool:
        """Check if COLMAP is available."""
        try:
            subprocess.run(
                ['colmap', '--version'],
                capture_output=True,
                check=True
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def estimate_poses(
        self,
        image_dir: Path,
        output_dir: Path,
        progress_callback: Optional[callable] = None
    ) -> Tuple[List[CameraPose], CameraIntrinsics]:
        """
        Estimate camera poses from images using COLMAP.
        
        Args:
            image_dir: Directory containing input images
            output_dir: Directory for COLMAP outputs
            progress_callback: Optional callback(message, progress)
        
        Returns:
            Tuple of (poses, intrinsics)
        
        Raises:
            RuntimeError: If COLMAP fails
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create COLMAP workspace
        database_path = output_dir / "database.db"
        sparse_dir = output_dir / "sparse"
        sparse_dir.mkdir(exist_ok=True)
        
        logger.info(f"Running COLMAP on {image_dir}")
        
        # Step 1: Feature extraction
        if progress_callback:
            progress_callback("Extracting features", 0.2)
        
        self._run_feature_extraction(image_dir, database_path)
        logger.info("Feature extraction complete")
        
        # Step 2: Feature matching
        if progress_callback:
            progress_callback("Matching features", 0.4)
        
        self._run_feature_matching(database_path)
        logger.info("Feature matching complete")
        
        # Step 3: Sparse reconstruction (SfM + bundle adjustment)
        if progress_callback:
            progress_callback("Reconstructing cameras", 0.6)
        
        self._run_mapper(database_path, image_dir, sparse_dir)
        logger.info("Sparse reconstruction complete")
        
        # Step 4: Extract poses and intrinsics
        if progress_callback:
            progress_callback("Extracting poses", 0.9)
        
        poses, intrinsics = self._extract_poses_and_intrinsics(sparse_dir)
        logger.info(f"Extracted {len(poses)} camera poses")
        
        if progress_callback:
            progress_callback("Pose estimation complete", 1.0)
        
        return poses, intrinsics
    
    def _run_feature_extraction(self, image_dir: Path, database_path: Path):
        """
        Run COLMAP feature extraction.
        
        Extracts SIFT features (or other detector) from images.
        """
        detector = self.feature_config.get('detector', 'sift')
        max_features = self.feature_config.get('max_features', 8192)
        use_gpu = self.feature_config.get('use_gpu', True)
        
        cmd = [
            'colmap', 'feature_extractor',
            '--database_path', str(database_path),
            '--image_path', str(image_dir),
            '--ImageReader.single_camera', '1',  # Assume single camera
            '--SiftExtraction.max_num_features', str(max_features),
        ]
        
        if use_gpu:
            cmd.extend(['--SiftExtraction.use_gpu', '1'])
        else:
            cmd.extend(['--SiftExtraction.use_gpu', '0'])
        
        logger.info(f"Running: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            logger.debug(result.stdout)
        except subprocess.CalledProcessError as e:
            logger.error(f"COLMAP feature extraction failed: {e.stderr}")
            raise RuntimeError(f"Feature extraction failed: {e}")
    
    def _run_feature_matching(self, database_path: Path):
        """
        Run COLMAP feature matching.
        
        Matches features between image pairs.
        """
        method = self.matching_config.get('method', 'sequential')
        overlap = self.matching_config.get('overlap', 10)
        use_gpu = self.matching_config.get('use_gpu', True)
        
        if method == 'sequential':
            matcher_cmd = 'sequential_matcher'
            extra_args = ['--SequentialMatching.overlap', str(overlap)]
        elif method == 'exhaustive':
            matcher_cmd = 'exhaustive_matcher'
            extra_args = []
        elif method == 'vocab_tree':
            matcher_cmd = 'vocab_tree_matcher'
            extra_args = []
        else:
            raise ValueError(f"Unknown matching method: {method}")
        
        cmd = [
            'colmap', matcher_cmd,
            '--database_path', str(database_path),
        ] + extra_args
        
        if use_gpu:
            cmd.extend(['--SiftMatching.use_gpu', '1'])
        else:
            cmd.extend(['--SiftMatching.use_gpu', '0'])
        
        logger.info(f"Running: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            logger.debug(result.stdout)
        except subprocess.CalledProcessError as e:
            logger.error(f"COLMAP feature matching failed: {e.stderr}")
            raise RuntimeError(f"Feature matching failed: {e}")
    
    def _run_mapper(self, database_path: Path, image_dir: Path, output_dir: Path):
        """
        Run COLMAP mapper (sparse reconstruction + bundle adjustment).
        
        This performs incremental SfM and optimizes camera poses.
        """
        cmd = [
            'colmap', 'mapper',
            '--database_path', str(database_path),
            '--image_path', str(image_dir),
            '--output_path', str(output_dir),
        ]
        
        # Bundle adjustment options
        if self.ba_config.get('refine_focal_length', True):
            cmd.extend(['--Mapper.ba_refine_focal_length', '1'])
        
        if self.ba_config.get('refine_principal_point', True):
            cmd.extend(['--Mapper.ba_refine_principal_point', '1'])
        
        if self.ba_config.get('refine_extra_params', True):
            cmd.extend(['--Mapper.ba_refine_extra_params', '1'])
        
        logger.info(f"Running: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=600  # 10 minute timeout
            )
            logger.debug(result.stdout)
        except subprocess.CalledProcessError as e:
            logger.error(f"COLMAP mapper failed: {e.stderr}")
            raise RuntimeError(f"Sparse reconstruction failed: {e}")
        except subprocess.TimeoutExpired:
            raise RuntimeError("COLMAP mapper timed out (>10 minutes)")
    
    def _extract_poses_and_intrinsics(
        self,
        sparse_dir: Path
    ) -> Tuple[List[CameraPose], CameraIntrinsics]:
        """
        Extract camera poses and intrinsics from COLMAP output.
        
        COLMAP stores results in binary format in sparse/0/ directory.
        We'll use COLMAP's model_converter to export to text, then parse.
        """
        # Find reconstruction (COLMAP may create multiple reconstructions)
        reconstructions = sorted(sparse_dir.glob("*/"))
        
        if not reconstructions:
            raise RuntimeError("No COLMAP reconstructions found")
        
        # Use the first (usually best) reconstruction
        recon_dir = reconstructions[0]
        logger.info(f"Using COLMAP reconstruction: {recon_dir}")
        
        # Convert binary to text format for easier parsing
        text_dir = sparse_dir / "text"
        text_dir.mkdir(exist_ok=True)
        
        cmd = [
            'colmap', 'model_converter',
            '--input_path', str(recon_dir),
            '--output_path', str(text_dir),
            '--output_type', 'TXT'
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Model conversion failed: {e.stderr}")
            raise RuntimeError(f"Failed to convert COLMAP model: {e}")
        
        # Parse cameras.txt for intrinsics
        intrinsics = self._parse_cameras(text_dir / "cameras.txt")
        
        # Parse images.txt for poses
        poses = self._parse_images(text_dir / "images.txt")
        
        return poses, intrinsics
    
    def _parse_cameras(self, cameras_file: Path) -> CameraIntrinsics:
        """
        Parse COLMAP cameras.txt file.
        
        Format:
        # CAMERA_ID, MODEL, WIDTH, HEIGHT, PARAMS[]
        1 PINHOLE 1920 1080 1500.0 1500.0 960.0 540.0
        """
        with open(cameras_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                parts = line.split()
                camera_id = int(parts[0])
                model = parts[1]
                width = int(parts[2])
                height = int(parts[3])
                
                # Parse parameters based on model
                if model == 'PINHOLE':
                    # fx, fy, cx, cy
                    fx, fy, cx, cy = map(float, parts[4:8])
                    distortion = None
                elif model == 'OPENCV':
                    # fx, fy, cx, cy, k1, k2, p1, p2
                    fx, fy, cx, cy = map(float, parts[4:8])
                    distortion = list(map(float, parts[8:12]))
                elif model == 'RADIAL':
                    # f, cx, cy, k1, k2
                    f, cx, cy = map(float, parts[4:7])
                    fx = fy = f
                    distortion = list(map(float, parts[7:9]))
                else:
                    logger.warning(f"Unknown camera model: {model}, using default")
                    fx = fy = max(width, height)
                    cx = width / 2
                    cy = height / 2
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
        
        raise RuntimeError("No cameras found in cameras.txt")
    
    def _parse_images(self, images_file: Path) -> List[CameraPose]:
        """
        Parse COLMAP images.txt file.
        
        Format (two lines per image):
        # IMAGE_ID, QW, QX, QY, QZ, TX, TY, TZ, CAMERA_ID, NAME
        # POINTS2D[] as (X, Y, POINT3D_ID)
        1 0.9 0.1 0.2 0.3 1.0 2.0 3.0 1 image_001.jpg
        0.5 0.5 100 0.6 0.6 101 ...
        """
        poses = []
        
        with open(images_file, 'r') as f:
            lines = f.readlines()
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            if not line or line.startswith('#'):
                i += 1
                continue
            
            # Parse image line
            parts = line.split()
            image_id = int(parts[0])
            qw, qx, qy, qz = map(float, parts[1:5])
            tx, ty, tz = map(float, parts[5:8])
            camera_id = int(parts[8])
            image_name = parts[9]
            
            # Convert quaternion to rotation matrix
            rotation_matrix = self._quat_to_rotation_matrix(qw, qx, qy, qz)
            
            # Create pose
            # Note: COLMAP uses world-to-camera transform
            # We might need to invert this for Nerfstudio (camera-to-world)
            pose = CameraPose(
                frame_id=image_id - 1,  # 0-indexed
                timestamp=0.0,  # No timestamp in COLMAP
                position=[tx, ty, tz],
                rotation=rotation_matrix.tolist(),
                confidence=1.0  # COLMAP doesn't provide confidence scores
            )
            
            poses.append(pose)
            
            # Skip points2D line
            i += 2
        
        # Sort by frame_id
        poses.sort(key=lambda p: p.frame_id)
        
        return poses
    
    def _quat_to_rotation_matrix(
        self,
        qw: float,
        qx: float,
        qy: float,
        qz: float
    ) -> np.ndarray:
        """
        Convert quaternion to 3x3 rotation matrix.
        
        Args:
            qw, qx, qy, qz: Quaternion components (w is scalar)
        
        Returns:
            3x3 rotation matrix
        """
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
    
    def export_for_nerfstudio(
        self,
        sparse_dir: Path,
        output_file: Path
    ):
        """
        Export COLMAP reconstruction in Nerfstudio format.
        
        This is an alternative to manual conversion - uses COLMAP data directly.
        Nerfstudio has built-in support for COLMAP format.
        """
        # Nerfstudio can directly read COLMAP sparse reconstruction
        # Just need to ensure the directory structure is correct
        
        logger.info(f"COLMAP data at {sparse_dir} can be used directly by Nerfstudio")
        logger.info("Use: ns-process-data colmap --data <path>")


def validate_colmap_reconstruction(sparse_dir: Path) -> Tuple[bool, str]:
    """
    Validate COLMAP reconstruction output.
    
    Args:
        sparse_dir: Directory containing COLMAP sparse reconstruction
    
    Returns:
        Tuple of (is_valid, message)
    """
    reconstructions = list(sparse_dir.glob("*/"))
    
    if not reconstructions:
        return False, "No reconstructions found"
    
    recon_dir = reconstructions[0]
    
    # Check for required files
    required_files = ['cameras.bin', 'images.bin', 'points3D.bin']
    missing = []
    
    for filename in required_files:
        if not (recon_dir / filename).exists():
            missing.append(filename)
    
    if missing:
        return False, f"Missing files: {', '.join(missing)}"
    
    return True, f"Valid reconstruction with {len(reconstructions)} model(s)"

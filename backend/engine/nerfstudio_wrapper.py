"""
Nerfstudio Wrapper

Wraps Nerfstudio's pipelines (nerfacto, splatfacto) to provide a clean interface
for the reconstruction engine.

This implementation:
1. Prepares data in Nerfstudio format
2. Runs training pipelines
3. Exports results in various formats
4. Provides progress tracking
"""

import json
import logging
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import shutil

import torch
from tqdm import tqdm

from .base import (
    CameraIntrinsics,
    CameraPose,
    OutputFormat,
    QualityMetrics,
    ReconstructionEngine,
    ReconstructionError,
    ReconstructionInput,
    ReconstructionOutput,
    ReconstructionStatus,
    TrainingError,
    ExportError
)

logger = logging.getLogger(__name__)


class NerfstudioWrapper(ReconstructionEngine):
    """
    Wrapper for Nerfstudio reconstruction pipelines.
    
    Supports:
    - nerfacto: High-quality NeRF reconstruction
    - splatfacto: Fast 3D Gaussian Splatting reconstruction
    """
    
    def __init__(self, workspace_dir: Path, config: Dict[str, Any]):
        """
        Initialize Nerfstudio wrapper.
        
        Args:
            workspace_dir: Directory for intermediate files and checkpoints
            config: Configuration dictionary
        """
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        
        self.config = config
        self._active_jobs: Dict[str, Dict[str, Any]] = {}
        
        logger.info(f"Initialized NerfstudioWrapper with workspace: {workspace_dir}")
    
    def reconstruct(
        self,
        input_data: ReconstructionInput,
        progress_callback: Optional[callable] = None
    ) -> ReconstructionOutput:
        """
        Perform 3D reconstruction using Nerfstudio.
        
        Pipeline:
        1. Prepare data in Nerfstudio format (transforms.json)
        2. Run ns-train with specified method
        3. Export outputs in requested formats
        4. Compute quality metrics
        """
        job_id = input_data.job_id
        started_at = datetime.now()
        
        try:
            logger.info(f"[{job_id}] Starting reconstruction with method: {input_data.method.value}")
            
            # Create job workspace
            job_dir = self.workspace_dir / job_id
            job_dir.mkdir(parents=True, exist_ok=True)
            
            # Track active job
            self._active_jobs[job_id] = {
                "status": ReconstructionStatus.PREPROCESSING,
                "started_at": started_at,
                "input": input_data
            }
            
            # Step 1: Prepare data
            if progress_callback:
                progress_callback("Preparing data", 0.1)
            
            data_dir = self._prepare_nerfstudio_data(input_data, job_dir)
            logger.info(f"[{job_id}] Data prepared in: {data_dir}")
            
            # Step 2: Train model
            self._active_jobs[job_id]["status"] = ReconstructionStatus.TRAINING
            if progress_callback:
                progress_callback("Training model", 0.3)
            
            checkpoint_path = self._train_model(
                input_data,
                data_dir,
                job_dir,
                progress_callback
            )
            logger.info(f"[{job_id}] Training complete. Checkpoint: {checkpoint_path}")
            
            # Step 3: Export outputs
            self._active_jobs[job_id]["status"] = ReconstructionStatus.EXPORTING
            if progress_callback:
                progress_callback("Exporting outputs", 0.9)
            
            output_files = self._export_outputs(
                input_data,
                checkpoint_path,
                job_dir
            )
            logger.info(f"[{job_id}] Exported {len(output_files)} output formats")
            
            # Step 4: Compute quality metrics
            quality_metrics = self._compute_quality_metrics(
                input_data,
                data_dir,
                output_files
            )
            
            # Success
            completed_at = datetime.now()
            duration = (completed_at - started_at).total_seconds()
            
            self._active_jobs[job_id]["status"] = ReconstructionStatus.COMPLETED
            
            if progress_callback:
                progress_callback("Completed", 1.0)
            
            return ReconstructionOutput(
                job_id=job_id,
                status=ReconstructionStatus.COMPLETED,
                output_files=output_files,
                quality_metrics=quality_metrics,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=duration
            )
            
        except Exception as e:
            logger.error(f"[{job_id}] Reconstruction failed: {e}", exc_info=True)
            
            self._active_jobs[job_id]["status"] = ReconstructionStatus.FAILED
            
            import traceback
            return ReconstructionOutput(
                job_id=job_id,
                status=ReconstructionStatus.FAILED,
                output_files={},
                started_at=started_at,
                completed_at=datetime.now(),
                duration_seconds=(datetime.now() - started_at).total_seconds(),
                error_message=str(e),
                error_traceback=traceback.format_exc()
            )
    
    def _prepare_nerfstudio_data(
        self,
        input_data: ReconstructionInput,
        job_dir: Path
    ) -> Path:
        """
        Prepare data in Nerfstudio format.
        
        Creates a directory structure:
        data/
          images/           # Symlinks or copies of input frames
          transforms.json   # Camera poses in Nerfstudio format
        
        Returns:
            Path to data directory
        """
        data_dir = job_dir / "data"
        images_dir = data_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy or symlink images
        if input_data.frame_paths:
            for i, frame_path in enumerate(input_data.frame_paths):
                target = images_dir / f"frame_{i:05d}{frame_path.suffix}"
                if not target.exists():
                    shutil.copy(frame_path, target)
        else:
            raise ValueError("frame_paths must be provided")
        
        # Create transforms.json
        transforms = self._create_transforms_json(input_data)
        
        transforms_path = data_dir / "transforms.json"
        with open(transforms_path, 'w') as f:
            json.dump(transforms, f, indent=2)
        
        logger.info(f"Created transforms.json with {len(input_data.camera_poses)} frames")
        
        return data_dir
    
    def _create_transforms_json(self, input_data: ReconstructionInput) -> Dict[str, Any]:
        """
        Create Nerfstudio transforms.json from camera poses.
        
        Format documentation:
        https://docs.nerf.studio/quickstart/data_conventions.html
        """
        if not input_data.camera_intrinsics:
            raise ValueError("Camera intrinsics required")
        
        intrinsics = input_data.camera_intrinsics
        
        # Base transform structure
        transforms = {
            "camera_model": "OPENCV",
            "fl_x": intrinsics.fx,
            "fl_y": intrinsics.fy,
            "cx": intrinsics.cx,
            "cy": intrinsics.cy,
            "w": intrinsics.width,
            "h": intrinsics.height,
            "frames": []
        }
        
        # Add distortion if available
        if intrinsics.distortion:
            transforms["k1"] = intrinsics.distortion[0] if len(intrinsics.distortion) > 0 else 0
            transforms["k2"] = intrinsics.distortion[1] if len(intrinsics.distortion) > 1 else 0
            transforms["p1"] = intrinsics.distortion[2] if len(intrinsics.distortion) > 2 else 0
            transforms["p2"] = intrinsics.distortion[3] if len(intrinsics.distortion) > 3 else 0
        
        # Add frames
        for i, pose in enumerate(input_data.camera_poses):
            # Construct 4x4 transformation matrix
            # [R | t]
            # [0 | 1]
            transform_matrix = [
                pose.rotation[0] + [pose.position[0]],
                pose.rotation[1] + [pose.position[1]],
                pose.rotation[2] + [pose.position[2]],
                [0, 0, 0, 1]
            ]
            
            frame = {
                "file_path": f"images/frame_{i:05d}.png",
                "transform_matrix": transform_matrix
            }
            
            transforms["frames"].append(frame)
        
        return transforms
    
    def _train_model(
        self,
        input_data: ReconstructionInput,
        data_dir: Path,
        job_dir: Path,
        progress_callback: Optional[callable] = None
    ) -> Path:
        """
        Train Nerfstudio model using ns-train command.
        
        Returns:
            Path to checkpoint directory
        """
        method = input_data.method.value
        output_dir = job_dir / "outputs"
        
        # Build ns-train command
        cmd = [
            "ns-train",
            method,
            "--data", str(data_dir),
            "--output-dir", str(output_dir),
            "--max-num-iterations", str(input_data.max_iterations),
            "--pipeline.model.camera-optimizer.mode", "off",  # Don't optimize camera poses
            "--vis", "wandb",  # Disable viewer for batch processing
        ]
        
        logger.info(f"Running: {' '.join(cmd)}")
        
        try:
            # Run training
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            # Monitor progress
            for line in process.stdout:
                logger.debug(line.rstrip())
                
                # Parse progress from output
                if "Step" in line and "/" in line:
                    try:
                        # Extract step number (format: "Step 1000/30000")
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if part == "Step" and i + 1 < len(parts):
                                step_info = parts[i + 1]
                                current, total = step_info.split("/")
                                progress = float(current) / float(total)
                                
                                if progress_callback:
                                    progress_callback(
                                        f"Training: step {current}/{total}",
                                        0.3 + (progress * 0.6)  # Map to 30-90% overall progress
                                    )
                                break
                    except:
                        pass
            
            process.wait()
            
            if process.returncode != 0:
                raise TrainingError(f"Training failed with exit code {process.returncode}")
            
            # Find checkpoint directory
            # Nerfstudio creates: outputs/<method>/<data-name>/<timestamp>/nerfstudio_models/
            method_dir = output_dir / method
            
            # Find most recent training run
            training_runs = sorted(method_dir.glob("*/"), key=lambda p: p.stat().st_mtime, reverse=True)
            
            if not training_runs:
                raise TrainingError(f"No training output found in {method_dir}")
            
            checkpoint_dir = training_runs[0] / "nerfstudio_models"
            
            if not checkpoint_dir.exists():
                raise TrainingError(f"Checkpoint directory not found: {checkpoint_dir}")
            
            return checkpoint_dir
            
        except subprocess.CalledProcessError as e:
            raise TrainingError(f"Training command failed: {e}")
    
    def _export_outputs(
        self,
        input_data: ReconstructionInput,
        checkpoint_path: Path,
        job_dir: Path
    ) -> Dict[OutputFormat, Path]:
        """
        Export reconstruction in requested formats.
        
        Uses ns-export commands to generate outputs.
        """
        output_files = {}
        export_dir = job_dir / "exports"
        export_dir.mkdir(exist_ok=True)
        
        # Find config file
        config_file = checkpoint_path.parent / "config.yml"
        if not config_file.exists():
            raise ExportError(f"Config file not found: {config_file}")
        
        for output_format in input_data.output_formats:
            try:
                output_path = self._export_format(
                    output_format,
                    config_file,
                    export_dir
                )
                output_files[output_format] = output_path
                logger.info(f"Exported {output_format.value}: {output_path}")
                
            except Exception as e:
                logger.error(f"Failed to export {output_format.value}: {e}")
                # Continue with other formats
        
        if not output_files:
            raise ExportError("No outputs were successfully exported")
        
        return output_files
    
    def _export_format(
        self,
        output_format: OutputFormat,
        config_file: Path,
        export_dir: Path
    ) -> Path:
        """Export a specific format using ns-export."""
        
        if output_format == OutputFormat.PLY:
            # Export point cloud
            output_path = export_dir / "pointcloud.ply"
            cmd = [
                "ns-export", "pointcloud",
                "--load-config", str(config_file),
                "--output-dir", str(export_dir),
                "--num-points", "1000000",
                "--remove-outliers", "true"
            ]
            
        elif output_format == OutputFormat.MESH:
            # Export mesh (requires marching cubes)
            output_path = export_dir / "mesh.ply"
            cmd = [
                "ns-export", "poisson",
                "--load-config", str(config_file),
                "--output-dir", str(export_dir),
                "--normal-method", "open3d",
                "--depth", "9"
            ]
            
        elif output_format == OutputFormat.SPLAT:
            # Export Gaussian splats
            output_path = export_dir / "splat.ply"
            cmd = [
                "ns-export", "gaussian-splat",
                "--load-config", str(config_file),
                "--output-dir", str(export_dir)
            ]
            
        else:
            raise ExportError(f"Unsupported export format: {output_format}")
        
        logger.info(f"Running export: {' '.join(cmd)}")
        
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            
            # Find exported file
            if not output_path.exists():
                # Try to find the actual output file
                possible_paths = list(export_dir.glob(f"*.{output_format.value}"))
                if possible_paths:
                    output_path = possible_paths[0]
                else:
                    raise ExportError(f"Export succeeded but output file not found: {output_path}")
            
            return output_path
            
        except subprocess.CalledProcessError as e:
            raise ExportError(f"Export command failed: {e.stderr}")
    
    def _compute_quality_metrics(
        self,
        input_data: ReconstructionInput,
        data_dir: Path,
        output_files: Dict[OutputFormat, Path]
    ) -> QualityMetrics:
        """
        Compute quality metrics for the reconstruction.
        
        Currently provides basic metrics. Can be extended with:
        - Photometric error analysis
        - Coverage analysis
        - Geometric consistency checks
        """
        num_frames = len(input_data.camera_poses)
        num_valid_poses = sum(1 for p in input_data.camera_poses if p.confidence > 0.5)
        
        # Simple heuristics for now
        coverage_percentage = (num_valid_poses / num_frames) * 100
        pose_confidence = sum(p.confidence for p in input_data.camera_poses) / num_frames * 100
        
        # Overall score based on coverage and pose quality
        overall_score = (coverage_percentage + pose_confidence) / 2
        
        warnings = []
        errors = []
        
        if coverage_percentage < 70:
            warnings.append("Low frame coverage - reconstruction may be incomplete")
        
        if pose_confidence < 50:
            warnings.append("Low pose confidence - quality may be degraded")
        
        if num_frames < 50:
            warnings.append(f"Few frames ({num_frames}) - try capturing more video")
        
        return QualityMetrics(
            num_frames=num_frames,
            num_valid_poses=num_valid_poses,
            coverage_percentage=coverage_percentage,
            overall_score=overall_score,
            sharpness_score=80.0,  # Placeholder
            pose_confidence=pose_confidence,
            texture_quality=75.0,  # Placeholder
            warnings=warnings,
            errors=errors
        )
    
    def export(
        self,
        job_id: str,
        output_format: OutputFormat,
        output_path: Path
    ) -> Path:
        """Export existing reconstruction to a format."""
        raise NotImplementedError("Export of existing jobs not yet implemented")
    
    def get_status(self, job_id: str) -> ReconstructionStatus:
        """Get status of a job."""
        if job_id in self._active_jobs:
            return self._active_jobs[job_id]["status"]
        return ReconstructionStatus.PENDING
    
    def cancel(self, job_id: str) -> bool:
        """Cancel a running job."""
        if job_id in self._active_jobs:
            self._active_jobs[job_id]["status"] = ReconstructionStatus.CANCELLED
            return True
        return False

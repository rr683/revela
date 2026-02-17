"""
Reconstruction Engine Base Classes

Defines the core interfaces and data models for 3D reconstruction.
This abstraction layer allows us to swap out implementations (e.g., different NeRF methods)
without affecting the rest of the system.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid


class ReconstructionMethod(str, Enum):
    """Supported reconstruction methods."""
    NERFACTO = "nerfacto"  # NeRF-based reconstruction
    SPLATFACTO = "splatfacto"  # 3D Gaussian Splatting
    INSTANT_NGP = "instant-ngp"  # Instant Neural Graphics Primitives (future)


class ReconstructionStatus(str, Enum):
    """Status of a reconstruction job."""
    PENDING = "pending"
    PREPROCESSING = "preprocessing"
    POSE_ESTIMATION = "pose_estimation"
    TRAINING = "training"
    EXPORTING = "exporting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OutputFormat(str, Enum):
    """Supported output formats."""
    PLY = "ply"  # Point cloud
    MESH = "mesh"  # Textured mesh
    SPLAT = "splat"  # Gaussian splat file
    GLTF = "gltf"  # glTF/GLB (game engines, web viewers)
    DEPTH = "depth"  # Depth maps
    VIDEO = "video"  # Rendered video


@dataclass
class CameraIntrinsics:
    """Camera intrinsic parameters."""
    width: int
    height: int
    fx: float  # Focal length x
    fy: float  # Focal length y
    cx: float  # Principal point x
    cy: float  # Principal point y
    distortion: Optional[List[float]] = None  # Distortion coefficients
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "fx": self.fx,
            "fy": self.fy,
            "cx": self.cx,
            "cy": self.cy,
            "distortion": self.distortion
        }


@dataclass
class CameraPose:
    """Camera pose (position and orientation)."""
    frame_id: int
    timestamp: float
    position: List[float]  # [x, y, z]
    rotation: List[List[float]]  # 3x3 rotation matrix
    confidence: float = 1.0  # Pose confidence score [0-1]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "frame_id": self.frame_id,
            "timestamp": self.timestamp,
            "position": self.position,
            "rotation": self.rotation,
            "confidence": self.confidence
        }


@dataclass
class ReconstructionInput:
    """
    Input data for reconstruction.

    Accepts one or more of:
    1. Video file path (frames will be extracted)
    2. Image directory path (images used directly)
    3. Pre-extracted frame paths + poses

    Video and image inputs can be combined for greater scene coverage.
    """
    job_id: str

    # Video input
    video_path: Optional[Path] = None

    # Image directory input
    image_dir: Optional[Path] = None

    # Or pre-extracted frames
    frame_paths: Optional[List[Path]] = None
    camera_poses: Optional[List[CameraPose]] = None
    camera_intrinsics: Optional[CameraIntrinsics] = None
    
    # Reconstruction parameters
    method: ReconstructionMethod = ReconstructionMethod.SPLATFACTO
    max_iterations: int = 30000
    resolution: int = 1024
    
    # Output configuration
    output_formats: List[OutputFormat] = None
    output_dir: Optional[Path] = None
    
    def __post_init__(self):
        if self.output_formats is None:
            self.output_formats = [OutputFormat.PLY, OutputFormat.MESH]
        if self.output_dir is None:
            self.output_dir = Path(f"data/outputs/{self.job_id}")


@dataclass
class QualityMetrics:
    """Quality metrics for a reconstruction."""
    # Coverage metrics
    num_frames: int
    num_valid_poses: int
    coverage_percentage: float  # Percentage of scene covered
    
    # Quality scores (0-100)
    overall_score: float
    sharpness_score: float
    pose_confidence: float
    texture_quality: float
    
    # Issues detected
    warnings: List[str]
    errors: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "num_frames": self.num_frames,
            "num_valid_poses": self.num_valid_poses,
            "coverage_percentage": self.coverage_percentage,
            "overall_score": self.overall_score,
            "sharpness_score": self.sharpness_score,
            "pose_confidence": self.pose_confidence,
            "texture_quality": self.texture_quality,
            "warnings": self.warnings,
            "errors": self.errors
        }


@dataclass
class ReconstructionOutput:
    """Output from a reconstruction job."""
    job_id: str
    status: ReconstructionStatus
    
    # Output files
    output_files: Dict[OutputFormat, Path]
    
    # Quality assessment
    quality_metrics: Optional[QualityMetrics] = None
    
    # Timing information
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    
    # Error information (if failed)
    error_message: Optional[str] = None
    error_traceback: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status.value,
            "output_files": {k.value: str(v) for k, v in self.output_files.items()},
            "quality_metrics": self.quality_metrics.to_dict() if self.quality_metrics else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "error_message": self.error_message
        }


class ReconstructionEngine(ABC):
    """
    Abstract base class for reconstruction engines.
    
    This interface allows different implementations (Nerfstudio, custom models, etc.)
    to be used interchangeably.
    """
    
    @abstractmethod
    def reconstruct(
        self,
        input_data: ReconstructionInput,
        progress_callback: Optional[callable] = None
    ) -> ReconstructionOutput:
        """
        Perform 3D reconstruction.
        
        Args:
            input_data: Input configuration and data paths
            progress_callback: Optional callback for progress updates
                               Signature: callback(status: str, progress: float)
        
        Returns:
            ReconstructionOutput with results and quality metrics
        
        Raises:
            ReconstructionError: If reconstruction fails
        """
        pass
    
    @abstractmethod
    def export(
        self,
        job_id: str,
        output_format: OutputFormat,
        output_path: Path
    ) -> Path:
        """
        Export reconstruction to a specific format.
        
        Args:
            job_id: Job identifier
            output_format: Desired output format
            output_path: Where to save the export
        
        Returns:
            Path to exported file
        
        Raises:
            ExportError: If export fails
        """
        pass
    
    @abstractmethod
    def get_status(self, job_id: str) -> ReconstructionStatus:
        """
        Get current status of a reconstruction job.
        
        Args:
            job_id: Job identifier
        
        Returns:
            Current job status
        """
        pass
    
    @abstractmethod
    def cancel(self, job_id: str) -> bool:
        """
        Cancel a running reconstruction job.
        
        Args:
            job_id: Job identifier
        
        Returns:
            True if cancelled successfully, False if not found or already complete
        """
        pass


class ReconstructionError(Exception):
    """Base exception for reconstruction errors."""
    pass


class PreprocessingError(ReconstructionError):
    """Error during preprocessing (frame extraction, etc.)."""
    pass


class PoseEstimationError(ReconstructionError):
    """Error during camera pose estimation."""
    pass


class TrainingError(ReconstructionError):
    """Error during model training."""
    pass


class ExportError(ReconstructionError):
    """Error during model export."""
    pass


def generate_job_id() -> str:
    """Generate a unique job ID."""
    return f"job_{uuid.uuid4().hex[:12]}"

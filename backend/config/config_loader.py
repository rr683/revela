"""
Configuration Management

Loads configuration from YAML files and environment variables.
Provides type-safe access to configuration values.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from pydantic import BaseModel, Field


# Configuration Models (typed schemas)

class ReconstructionPipelineConfig(BaseModel):
    """Configuration for a specific reconstruction pipeline."""
    iterations: int = 30000
    save_iterations: List[int] = [7000, 15000, 30000]
    
class ReconstructionConfig(BaseModel):
    """Reconstruction engine configuration."""
    default_method: str = "splatfacto"
    max_iterations: int = 30000
    resolution: int = 1024
    max_batch_size: int = 4096
    pipelines: Dict[str, Dict[str, Any]] = {}

class FrameExtractionConfig(BaseModel):
    """Frame extraction settings."""
    fps: int = 10
    max_frames: int = 300
    min_frames: int = 50
    format: str = "png"
    quality: int = 95

class QualityFilterConfig(BaseModel):
    """Quality filtering settings."""
    enabled: bool = True
    min_sharpness: float = 10.0
    max_blur: float = 50.0
    min_exposure: int = 20
    max_exposure: int = 235

class ImageProcessingConfig(BaseModel):
    """Image preprocessing settings."""
    max_dimension: int = 1920
    auto_enhance: bool = False
    undistort: bool = False

class PreprocessingConfig(BaseModel):
    """Preprocessing configuration."""
    frame_extraction: FrameExtractionConfig = Field(default_factory=FrameExtractionConfig)
    quality_filter: QualityFilterConfig = Field(default_factory=QualityFilterConfig)
    image_processing: ImageProcessingConfig = Field(default_factory=ImageProcessingConfig)

class COLMAPFeatureConfig(BaseModel):
    """COLMAP feature extraction settings."""
    detector: str = "sift"
    max_features: int = 8192
    use_gpu: bool = True

class COLMAPMatchingConfig(BaseModel):
    """COLMAP feature matching settings."""
    method: str = "sequential"
    overlap: int = 10
    use_gpu: bool = True

class COLMAPBundleAdjustmentConfig(BaseModel):
    """COLMAP bundle adjustment settings."""
    refine_focal_length: bool = True
    refine_principal_point: bool = True
    refine_extra_params: bool = True
    max_iterations: int = 100

class COLMAPConfig(BaseModel):
    """COLMAP configuration."""
    feature_extraction: COLMAPFeatureConfig = Field(default_factory=COLMAPFeatureConfig)
    matching: COLMAPMatchingConfig = Field(default_factory=COLMAPMatchingConfig)
    bundle_adjustment: COLMAPBundleAdjustmentConfig = Field(default_factory=COLMAPBundleAdjustmentConfig)

class StorageConfig(BaseModel):
    """Storage configuration."""
    upload_dir: str = "data/uploads"
    output_dir: str = "data/outputs"
    cache_dir: str = "data/cache"
    use_object_storage: bool = False
    endpoint: str = "localhost:9000"
    access_key: str = "minioadmin"
    secret_key: str = "minioadmin"
    bucket_name: str = "video-3d-recon"

class DatabaseConfig(BaseModel):
    """Database configuration."""
    host: str = "localhost"
    port: int = 5432
    database: str = "video3d"
    user: str = "video3d"
    password: str = "video3d_password"
    pool_size: int = 5
    max_overflow: int = 10

class RedisConfig(BaseModel):
    """Redis configuration."""
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None

class CeleryConfig(BaseModel):
    """Celery configuration."""
    broker_url: str = "redis://localhost:6379/0"
    result_backend: str = "redis://localhost:6379/0"
    task_serializer: str = "json"
    result_serializer: str = "json"
    accept_content: List[str] = ["json"]
    timezone: str = "UTC"
    worker_prefetch_multiplier: int = 1
    worker_max_tasks_per_child: int = 10

class APIConfig(BaseModel):
    """API configuration."""
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]
    max_upload_size_mb: int = 2048
    allowed_video_formats: List[str] = [".mp4", ".mov", ".avi", ".mkv", ".webm"]

class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = "INFO"
    format: str = "json"

class Config(BaseModel):
    """Main configuration object."""
    reconstruction: ReconstructionConfig = Field(default_factory=ReconstructionConfig)
    preprocessing: PreprocessingConfig = Field(default_factory=PreprocessingConfig)
    colmap: COLMAPConfig = Field(default_factory=COLMAPConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    celery: CeleryConfig = Field(default_factory=CeleryConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


class ConfigLoader:
    """
    Configuration loader that reads from YAML files and environment variables.
    
    Usage:
        config = ConfigLoader.load()
        print(config.reconstruction.default_method)
    """
    
    _instance: Optional[Config] = None
    
    @classmethod
    def load(cls, config_file: Optional[str] = None) -> Config:
        """
        Load configuration from file and environment.
        
        Args:
            config_file: Path to YAML config file. If None, uses default.yaml
        
        Returns:
            Config object with loaded settings
        """
        if cls._instance is not None:
            return cls._instance
        
        # Determine config file path
        if config_file is None:
            config_dir = Path(__file__).parent
            config_file = config_dir / "default.yaml"
        else:
            config_file = Path(config_file)
        
        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_file}")
        
        # Load YAML
        with open(config_file, 'r') as f:
            config_dict = yaml.safe_load(f)
        
        # Override with environment variables
        config_dict = cls._apply_env_overrides(config_dict)
        
        # Create Config object
        cls._instance = Config(**config_dict)
        return cls._instance
    
    @classmethod
    def _apply_env_overrides(cls, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Override config values with environment variables.
        
        Environment variables follow the pattern: VIDEO3D_SECTION_KEY
        Example: VIDEO3D_API_PORT=9000
        """
        env_prefix = "VIDEO3D_"
        
        for key, value in os.environ.items():
            if not key.startswith(env_prefix):
                continue
            
            # Parse environment variable name
            parts = key[len(env_prefix):].lower().split('_')
            
            if len(parts) < 2:
                continue
            
            # Navigate nested dict and set value
            current = config_dict
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            
            # Convert value to appropriate type
            env_value = value
            if value.lower() in ('true', 'false'):
                env_value = value.lower() == 'true'
            elif value.isdigit():
                env_value = int(value)
            elif value.replace('.', '', 1).isdigit():
                env_value = float(value)
            
            current[parts[-1]] = env_value
        
        return config_dict
    
    @classmethod
    def reload(cls, config_file: Optional[str] = None) -> Config:
        """Force reload configuration."""
        cls._instance = None
        return cls.load(config_file)


# Global config instance
def get_config() -> Config:
    """Get the global configuration instance."""
    return ConfigLoader.load()


# Example usage
if __name__ == "__main__":
    # Load config
    config = get_config()
    
    # Access settings
    print(f"Reconstruction method: {config.reconstruction.default_method}")
    print(f"Max iterations: {config.reconstruction.max_iterations}")
    print(f"FPS for frame extraction: {config.preprocessing.frame_extraction.fps}")
    print(f"COLMAP feature detector: {config.colmap.feature_extraction.detector}")
    print(f"API port: {config.api.port}")

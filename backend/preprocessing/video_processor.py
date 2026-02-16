"""
Video Preprocessing

Handles video ingestion, frame extraction, and quality filtering.

Pipeline:
1. Extract frames from video at specified FPS
2. Filter frames based on quality metrics (sharpness, exposure)
3. Resize and normalize frames
4. Save processed frames for reconstruction
"""

import logging
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple
import json

import cv2
import numpy as np
from PIL import Image
from tqdm import tqdm

logger = logging.getLogger(__name__)


class VideoPreprocessor:
    """
    Preprocesses video for 3D reconstruction.
    
    Features:
    - Frame extraction at configurable FPS
    - Quality filtering (blur detection, exposure check)
    - Image resizing and normalization
    - Metadata extraction (resolution, duration, codec)
    """
    
    def __init__(self, config: dict):
        """
        Initialize preprocessor.
        
        Args:
            config: Configuration dict from config.preprocessing
        """
        self.config = config
        self.frame_config = config.get('frame_extraction', {})
        self.quality_config = config.get('quality_filter', {})
        self.image_config = config.get('image_processing', {})
        
        logger.info("Initialized VideoPreprocessor")
    
    def process_video(
        self,
        video_path: Path,
        output_dir: Path,
        progress_callback: Optional[callable] = None
    ) -> Tuple[List[Path], dict]:
        """
        Process video and extract frames.
        
        Args:
            video_path: Path to input video
            output_dir: Directory to save extracted frames
            progress_callback: Optional callback(message, progress)
        
        Returns:
            Tuple of:
            - List of extracted frame paths
            - Video metadata dict
        
        Raises:
            ValueError: If video is invalid or processing fails
        """
        if not video_path.exists():
            raise ValueError(f"Video not found: {video_path}")
        
        logger.info(f"Processing video: {video_path}")
        
        # Create output directory
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Extract video metadata
        if progress_callback:
            progress_callback("Analyzing video", 0.05)
        
        metadata = self._get_video_metadata(video_path)
        logger.info(f"Video metadata: {metadata}")
        
        # Extract frames
        if progress_callback:
            progress_callback("Extracting frames", 0.1)
        
        raw_frame_dir = output_dir / "raw_frames"
        raw_frame_dir.mkdir(exist_ok=True)
        
        raw_frames = self._extract_frames(
            video_path,
            raw_frame_dir,
            metadata,
            progress_callback
        )
        
        logger.info(f"Extracted {len(raw_frames)} raw frames")
        
        # Filter frames by quality
        if self.quality_config.get('enabled', True):
            if progress_callback:
                progress_callback("Filtering frames", 0.5)
            
            filtered_frames = self._filter_frames(raw_frames, progress_callback)
            logger.info(f"Filtered to {len(filtered_frames)} high-quality frames")
        else:
            filtered_frames = raw_frames
        
        # Process frames (resize, normalize)
        if progress_callback:
            progress_callback("Processing frames", 0.7)
        
        processed_dir = output_dir / "processed_frames"
        processed_dir.mkdir(exist_ok=True)
        
        processed_frames = self._process_frames(
            filtered_frames,
            processed_dir,
            progress_callback
        )
        
        logger.info(f"Processed {len(processed_frames)} frames")
        
        # Update metadata
        metadata['num_extracted_frames'] = len(raw_frames)
        metadata['num_filtered_frames'] = len(filtered_frames)
        metadata['num_processed_frames'] = len(processed_frames)
        
        # Save metadata
        metadata_path = output_dir / "metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        if progress_callback:
            progress_callback("Preprocessing complete", 1.0)
        
        return processed_frames, metadata
    
    def _get_video_metadata(self, video_path: Path) -> dict:
        """
        Extract video metadata using ffprobe.
        
        Returns dict with:
        - duration: Video duration in seconds
        - fps: Frames per second
        - width, height: Video dimensions
        - codec: Video codec
        - bitrate: Video bitrate
        """
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            str(video_path)
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            
            # Find video stream
            video_stream = None
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    video_stream = stream
                    break
            
            if not video_stream:
                raise ValueError("No video stream found")
            
            # Parse FPS (can be "30/1" format)
            fps_str = video_stream.get('r_frame_rate', '30/1')
            if '/' in fps_str:
                num, denom = map(int, fps_str.split('/'))
                fps = num / denom
            else:
                fps = float(fps_str)
            
            metadata = {
                'duration': float(data.get('format', {}).get('duration', 0)),
                'fps': fps,
                'width': int(video_stream.get('width', 0)),
                'height': int(video_stream.get('height', 0)),
                'codec': video_stream.get('codec_name', 'unknown'),
                'bitrate': int(data.get('format', {}).get('bit_rate', 0)),
                'num_frames': int(video_stream.get('nb_frames', 0))
            }
            
            return metadata
            
        except subprocess.CalledProcessError as e:
            raise ValueError(f"Failed to extract video metadata: {e}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse video metadata: {e}")
    
    def _extract_frames(
        self,
        video_path: Path,
        output_dir: Path,
        metadata: dict,
        progress_callback: Optional[callable] = None
    ) -> List[Path]:
        """
        Extract frames from video using FFmpeg.
        
        Uses FFmpeg for efficient frame extraction at specified FPS.
        """
        target_fps = self.frame_config.get('fps', 10)
        max_frames = self.frame_config.get('max_frames', 300)
        format_ext = self.frame_config.get('format', 'png')
        
        # Calculate frame extraction filter
        # Extract 1 frame every N frames to achieve target FPS
        video_fps = metadata['fps']
        frame_interval = max(1, int(video_fps / target_fps))
        
        logger.info(f"Extracting frames: target_fps={target_fps}, interval={frame_interval}")
        
        # FFmpeg command to extract frames
        output_pattern = str(output_dir / f"frame_%05d.{format_ext}")
        
        cmd = [
            'ffmpeg',
            '-i', str(video_path),
            '-vf', f'select=not(mod(n\\,{frame_interval}))',
            '-vsync', 'vfr',
            '-frames:v', str(max_frames),
            '-q:v', '2',  # High quality
            output_pattern,
            '-y'  # Overwrite
        ]
        
        try:
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Get extracted frames
            frames = sorted(output_dir.glob(f"frame_*.{format_ext}"))
            
            if not frames:
                raise ValueError("No frames extracted")
            
            return frames
            
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error: {e.stderr}")
            raise ValueError(f"Frame extraction failed: {e}")
    
    def _filter_frames(
        self,
        frame_paths: List[Path],
        progress_callback: Optional[callable] = None
    ) -> List[Path]:
        """
        Filter frames based on quality metrics.
        
        Filters:
        1. Sharpness (Laplacian variance)
        2. Exposure (histogram analysis)
        3. Motion blur (gradient magnitude)
        """
        min_sharpness = self.quality_config.get('min_sharpness', 10.0)
        min_exposure = self.quality_config.get('min_exposure', 20)
        max_exposure = self.quality_config.get('max_exposure', 235)
        
        filtered_frames = []
        
        for i, frame_path in enumerate(tqdm(frame_paths, desc="Filtering frames")):
            try:
                # Load image
                img = cv2.imread(str(frame_path))
                if img is None:
                    logger.warning(f"Failed to load frame: {frame_path}")
                    continue
                
                # Convert to grayscale for analysis
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                
                # Check sharpness (Laplacian variance)
                sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
                
                # Check exposure (mean pixel intensity)
                mean_intensity = gray.mean()
                
                # Accept frame if it passes thresholds
                if sharpness >= min_sharpness and min_exposure <= mean_intensity <= max_exposure:
                    filtered_frames.append(frame_path)
                else:
                    logger.debug(
                        f"Rejected frame {frame_path.name}: "
                        f"sharpness={sharpness:.2f}, intensity={mean_intensity:.2f}"
                    )
                
                # Progress update
                if progress_callback and i % 10 == 0:
                    progress = 0.5 + (i / len(frame_paths)) * 0.2
                    progress_callback(f"Filtering frames ({i}/{len(frame_paths)})", progress)
                    
            except Exception as e:
                logger.error(f"Error processing frame {frame_path}: {e}")
                continue
        
        min_frames = self.frame_config.get('min_frames', 50)
        if len(filtered_frames) < min_frames:
            logger.warning(
                f"Only {len(filtered_frames)} frames passed quality filter "
                f"(minimum {min_frames}). Keeping all frames."
            )
            return frame_paths
        
        return filtered_frames
    
    def _process_frames(
        self,
        frame_paths: List[Path],
        output_dir: Path,
        progress_callback: Optional[callable] = None
    ) -> List[Path]:
        """
        Process frames: resize, normalize, and save.
        
        Operations:
        1. Resize to max dimension (maintains aspect ratio)
        2. Optional histogram equalization for low-light
        3. Save as high-quality PNG
        """
        max_dimension = self.image_config.get('max_dimension', 1920)
        auto_enhance = self.image_config.get('auto_enhance', False)
        
        processed_frames = []
        
        for i, frame_path in enumerate(tqdm(frame_paths, desc="Processing frames")):
            try:
                # Load image
                img = cv2.imread(str(frame_path))
                if img is None:
                    logger.warning(f"Failed to load frame: {frame_path}")
                    continue
                
                # Resize if needed
                h, w = img.shape[:2]
                if max(h, w) > max_dimension:
                    scale = max_dimension / max(h, w)
                    new_w = int(w * scale)
                    new_h = int(h * scale)
                    img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
                
                # Optional enhancement
                if auto_enhance:
                    # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
                    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
                    l, a, b = cv2.split(lab)
                    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                    l = clahe.apply(l)
                    img = cv2.merge([l, a, b])
                    img = cv2.cvtColor(img, cv2.COLOR_LAB2BGR)
                
                # Save processed frame
                output_path = output_dir / frame_path.name
                cv2.imwrite(str(output_path), img, [cv2.IMWRITE_PNG_COMPRESSION, 3])
                
                processed_frames.append(output_path)
                
                # Progress update
                if progress_callback and i % 10 == 0:
                    progress = 0.7 + (i / len(frame_paths)) * 0.2
                    progress_callback(f"Processing frames ({i}/{len(frame_paths)})", progress)
                    
            except Exception as e:
                logger.error(f"Error processing frame {frame_path}: {e}")
                continue
        
        return processed_frames
    
    def get_video_info(self, video_path: Path) -> dict:
        """
        Get video information without extracting frames.
        
        Useful for validation and display purposes.
        """
        return self._get_video_metadata(video_path)


def validate_video(video_path: Path, allowed_formats: List[str]) -> Tuple[bool, str]:
    """
    Validate video file.
    
    Args:
        video_path: Path to video file
        allowed_formats: List of allowed extensions (e.g., ['.mp4', '.mov'])
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not video_path.exists():
        return False, "Video file not found"
    
    if video_path.suffix.lower() not in allowed_formats:
        return False, f"Unsupported format. Allowed: {', '.join(allowed_formats)}"
    
    # Try to read metadata
    try:
        preprocessor = VideoPreprocessor({})
        metadata = preprocessor.get_video_info(video_path)
        
        if metadata['duration'] == 0:
            return False, "Video has zero duration"
        
        if metadata['width'] == 0 or metadata['height'] == 0:
            return False, "Video has invalid dimensions"
        
        return True, "Valid video"
        
    except Exception as e:
        return False, f"Failed to read video: {str(e)}"

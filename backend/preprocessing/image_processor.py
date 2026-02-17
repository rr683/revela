"""
Image Set Preprocessing

Handles ingestion and quality filtering for pre-captured image sets.
This complements video_processor.py by supporting direct image directories
as input for 3D reconstruction, without requiring video extraction.

Pipeline:
1. Discover images in a directory
2. Filter by quality (sharpness, exposure)
3. Resize and normalize
4. Save processed images for reconstruction
"""

import logging
from pathlib import Path
from typing import List, Optional, Tuple
import json

import cv2
import numpy as np
from tqdm import tqdm

logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_FORMATS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp"}


class ImageProcessor:
    """
    Preprocesses image sets for 3D reconstruction.

    Accepts a directory of images (e.g. from a camera, phone burst, or
    structured capture session) and prepares them for COLMAP and Nerfstudio.
    """

    def __init__(self, config: dict):
        """
        Initialize image processor.

        Args:
            config: Configuration dict from config.preprocessing
        """
        self.config = config
        self.image_config = config.get('image_ingestion', {})
        self.quality_config = config.get('quality_filter', {})
        self.processing_config = config.get('image_processing', {})

        logger.info("Initialized ImageProcessor")

    def process_images(
        self,
        image_dir: Path,
        output_dir: Path,
        progress_callback: Optional[callable] = None
    ) -> Tuple[List[Path], dict]:
        """
        Process an image directory for reconstruction.

        Args:
            image_dir: Directory containing input images
            output_dir: Directory to save processed images
            progress_callback: Optional callback(message, progress)

        Returns:
            Tuple of (processed image paths, metadata dict)

        Raises:
            ValueError: If directory is invalid or contains no usable images
        """
        image_dir = Path(image_dir)
        if not image_dir.is_dir():
            raise ValueError(f"Image directory not found: {image_dir}")

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if progress_callback:
            progress_callback("Discovering images", 0.05)

        # Discover images
        raw_images = self._discover_images(image_dir)
        if not raw_images:
            raise ValueError(
                f"No supported images found in {image_dir}. "
                f"Supported formats: {', '.join(sorted(SUPPORTED_IMAGE_FORMATS))}"
            )

        logger.info(f"Found {len(raw_images)} images in {image_dir}")

        # Enforce max images limit
        max_images = self.image_config.get('max_images', 500)
        if len(raw_images) > max_images:
            # Subsample evenly
            step = len(raw_images) / max_images
            raw_images = [raw_images[int(i * step)] for i in range(max_images)]
            logger.info(f"Subsampled to {len(raw_images)} images (max_images={max_images})")

        # Collect metadata from first image
        metadata = self._get_image_set_metadata(raw_images)

        # Filter by quality
        if self.quality_config.get('enabled', True):
            if progress_callback:
                progress_callback("Filtering images by quality", 0.2)
            filtered_images = self._filter_images(raw_images, progress_callback)
            logger.info(f"Filtered to {len(filtered_images)} images")
        else:
            filtered_images = raw_images

        # Process (resize, normalize)
        if progress_callback:
            progress_callback("Processing images", 0.6)

        processed_dir = output_dir / "processed_frames"
        processed_dir.mkdir(exist_ok=True)

        processed_images = self._process_images(
            filtered_images, processed_dir, progress_callback
        )

        logger.info(f"Processed {len(processed_images)} images")

        # Update metadata
        metadata['num_discovered_images'] = len(self._discover_images(image_dir))
        metadata['num_filtered_images'] = len(filtered_images)
        metadata['num_processed_images'] = len(processed_images)
        metadata['source'] = 'image_directory'

        metadata_path = output_dir / "metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        if progress_callback:
            progress_callback("Image preprocessing complete", 1.0)

        return processed_images, metadata

    def _discover_images(self, image_dir: Path) -> List[Path]:
        """Find all supported images in a directory, sorted by name."""
        supported = self.image_config.get(
            'supported_formats', list(SUPPORTED_IMAGE_FORMATS)
        )
        supported_set = {fmt.lower() for fmt in supported}

        images = []
        for p in sorted(image_dir.iterdir()):
            if p.is_file() and p.suffix.lower() in supported_set:
                images.append(p)

        return images

    def _get_image_set_metadata(self, image_paths: List[Path]) -> dict:
        """Extract metadata from the image set."""
        if not image_paths:
            return {}

        # Read first image to get dimensions
        first = cv2.imread(str(image_paths[0]))
        if first is None:
            return {'num_images': len(image_paths)}

        h, w = first.shape[:2]
        return {
            'num_images': len(image_paths),
            'width': w,
            'height': h,
            'source': 'image_directory',
        }

    def _filter_images(
        self,
        image_paths: List[Path],
        progress_callback: Optional[callable] = None
    ) -> List[Path]:
        """Filter images by sharpness and exposure."""
        min_sharpness = self.quality_config.get('min_sharpness', 10.0)
        min_exposure = self.quality_config.get('min_exposure', 20)
        max_exposure = self.quality_config.get('max_exposure', 235)

        filtered = []
        for i, path in enumerate(tqdm(image_paths, desc="Filtering images")):
            try:
                img = cv2.imread(str(path))
                if img is None:
                    logger.warning(f"Failed to load image: {path}")
                    continue

                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
                mean_intensity = gray.mean()

                if sharpness >= min_sharpness and min_exposure <= mean_intensity <= max_exposure:
                    filtered.append(path)
                else:
                    logger.debug(
                        f"Rejected {path.name}: sharpness={sharpness:.2f}, "
                        f"intensity={mean_intensity:.2f}"
                    )

                if progress_callback and i % 10 == 0:
                    progress = 0.2 + (i / len(image_paths)) * 0.3
                    progress_callback(f"Filtering ({i}/{len(image_paths)})", progress)

            except Exception as e:
                logger.error(f"Error filtering {path}: {e}")
                continue

        # If too many were rejected, keep all
        min_images = 20
        if len(filtered) < min_images and len(image_paths) >= min_images:
            logger.warning(
                f"Only {len(filtered)} images passed filter (min {min_images}). "
                f"Keeping all {len(image_paths)} images."
            )
            return image_paths

        return filtered

    def _process_images(
        self,
        image_paths: List[Path],
        output_dir: Path,
        progress_callback: Optional[callable] = None
    ) -> List[Path]:
        """Resize and normalize images."""
        max_dimension = self.processing_config.get('max_dimension', 1920)
        auto_enhance = self.processing_config.get('auto_enhance', False)

        processed = []
        for i, path in enumerate(tqdm(image_paths, desc="Processing images")):
            try:
                img = cv2.imread(str(path))
                if img is None:
                    continue

                h, w = img.shape[:2]
                if max(h, w) > max_dimension:
                    scale = max_dimension / max(h, w)
                    img = cv2.resize(
                        img, (int(w * scale), int(h * scale)),
                        interpolation=cv2.INTER_AREA
                    )

                if auto_enhance:
                    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
                    l, a, b = cv2.split(lab)
                    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                    l = clahe.apply(l)
                    img = cv2.merge([l, a, b])
                    img = cv2.cvtColor(img, cv2.COLOR_LAB2BGR)

                # Save as PNG with consistent naming
                output_path = output_dir / f"frame_{i:05d}.png"
                cv2.imwrite(str(output_path), img, [cv2.IMWRITE_PNG_COMPRESSION, 3])
                processed.append(output_path)

                if progress_callback and i % 10 == 0:
                    progress = 0.6 + (i / len(image_paths)) * 0.3
                    progress_callback(f"Processing ({i}/{len(image_paths)})", progress)

            except Exception as e:
                logger.error(f"Error processing {path}: {e}")
                continue

        return processed


def validate_image_directory(
    image_dir: Path,
    min_images: int = 20
) -> Tuple[bool, str]:
    """
    Validate an image directory for reconstruction.

    Args:
        image_dir: Path to image directory
        min_images: Minimum number of images required

    Returns:
        Tuple of (is_valid, message)
    """
    if not image_dir.exists():
        return False, f"Directory not found: {image_dir}"

    if not image_dir.is_dir():
        return False, f"Not a directory: {image_dir}"

    images = [
        p for p in image_dir.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_IMAGE_FORMATS
    ]

    if not images:
        return False, (
            f"No supported images found. "
            f"Supported formats: {', '.join(sorted(SUPPORTED_IMAGE_FORMATS))}"
        )

    if len(images) < min_images:
        return False, (
            f"Only {len(images)} images found (minimum {min_images} recommended "
            f"for reliable reconstruction)"
        )

    return True, f"Found {len(images)} images"

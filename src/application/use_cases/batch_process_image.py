from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from src.domain.entities.image import ImageEntity
from src.domain.services.processing_service import ProcessingService
from src.infrastructure.database.repositories.history_repository import HistoryRepository
from src.infrastructure.database.repositories.image_repository import ImageRepository
from src.infrastructure.storage.supabase_storage import SupabaseStorage


@dataclass
class BatchProcessImageUseCase:
    """
    Process multiple operations on an image in a single request.
    
    This use case solves the problem of cumulative modifications by:
    1. Always starting from the root/original image
    2. Applying all operations in sequence to that original
    3. Saving only the final result as a new version
    
    This ensures that users can modify different aspects of the image
    (brightness, contrast, channels, etc.) and get the right result,
    not a modification over a modification.
    """

    storage: SupabaseStorage
    image_repo: ImageRepository
    history_repo: HistoryRepository
    processing: ProcessingService

    def execute(
        self,
        user_id: str,
        image_id: str,
        operations: list[dict[str, Any]],
    ) -> ImageEntity:
        """
        Apply multiple operations to the root image and save as new version.

        Args:
            user_id: ID of the user performing the operations
            image_id: ID of any image in the version chain
            operations: List of operations to apply, each with format:
                       {"operation": "brightness", "params": {"factor": 1.2}}

        Returns:
            ImageEntity of the newly created processed image

        Raises:
            ValueError: If image not found or user doesn't have access
        """
        # Load the image reference (for metadata and versioning)
        image = self.image_repo.get(image_id)
        if image is None or image.user_id != user_id:
            raise ValueError("Image not found")

        # Determine root image - we ALWAYS start from the root/original
        root_id = image.root_image_id if image.root_image_id else image.id
        root_image = self.image_repo.get(root_id)
        
        if root_image is None:
            raise ValueError("Root image not found")

        # Download the root/original image
        src = self.storage.download_to_numpy(root_image.path)

        # Apply all operations in sequence
        processed = src
        for op_data in operations:
            operation = op_data.get("operation", "").lower()
            params = op_data.get("params", {})
            processed = self._apply_operation(processed, operation, params, user_id)

        # Get current max version number for this root
        version_chain = self.image_repo.get_version_chain(root_id, user_id)
        next_version = max((v.version_number for v in version_chain), default=0) + 1

        # Persist processed image as a new version
        ext = "png"  # Default to PNG for processed images
        stored = self.storage.upload_numpy(user_id=user_id, array=processed, ext=ext)

        # Create new version with full tracking
        entity = self.image_repo.create(
            user_id=user_id,
            path=stored.path,
            width=stored.width,
            height=stored.height,
            mime_type=stored.content_type,
            original_id=image.id,  # Parent is the image user started from
            original_filename=root_image.original_filename,
            file_size=stored.size,
            # Version tracking
            root_image_id=root_id,
            parent_version_id=image.id,
            version_number=next_version,
            is_root=False,
            base_image_id=root_id,  # Base is always the root for batch operations
        )

        # Record in history with all operations
        self.history_repo.create(
            user_id=user_id,
            image_id=entity.id,
            operation_type="batch_process",
            parameters={"operations": operations},
            result_storage_path=entity.path,
            source_image_id=root_id,  # We used root as base
            root_image_id=root_id,
        )

        return entity

    def _apply_operation(
        self,
        matrix: np.ndarray,
        operation: str,
        params: dict[str, Any],
        user_id: str,
    ) -> np.ndarray:
        """
        Apply a single operation to a numpy array.

        Args:
            matrix: Input image as numpy array
            operation: Operation name (e.g., "brightness", "grayscale_luminosity")
            params: Operation-specific parameters
            user_id: User ID (needed for merge operations)

        Returns:
            Processed numpy array

        Raises:
            ValueError: If operation is unsupported or parameters are invalid
        """
        out: np.ndarray

        if operation == "brightness":
            out = self.processing.adjust_brightness(matrix, float(params.get("factor", 0.0)))
        elif operation == "log_contrast":
            out = self.processing.adjust_log_contrast(matrix, float(params.get("k", 1.0)))
        elif operation == "exp_contrast":
            out = self.processing.adjust_exp_contrast(matrix, float(params.get("k", 1.0)))
        elif operation == "invert":
            out = self.processing.invert_color(matrix)
        elif operation == "grayscale_average":
            out = self.processing.grayscale_average(matrix)
        elif operation == "grayscale_luminosity":
            out = self.processing.grayscale_luminosity(matrix)
        elif operation == "grayscale_midgray":
            out = self.processing.grayscale_midgray(matrix)
        elif operation == "binarize":
            # Binarize requires grayscale first
            gray = self.processing.grayscale_luminosity(matrix)
            out = self.processing.binarize(gray, float(params.get("threshold", 0.5)))
        elif operation == "translate":
            out = self.processing.translate(
                matrix, int(params.get("dx", 0)), int(params.get("dy", 0))
            )
        elif operation == "rotate":
            out = self.processing.rotate(matrix, float(params.get("angle", 0.0)))
        elif operation == "crop":
            out = self.processing.crop(
                matrix,
                int(params["x_start"]),
                int(params["x_end"]),
                int(params["y_start"]),
                int(params["y_end"]),
            )
        elif operation == "reduce_resolution":
            out = self.processing.reduce_resolution(matrix, int(params.get("factor", 2)))
        elif operation == "enlarge_region":
            out = self.processing.enlarge_region(
                matrix,
                int(params["x_start"]),
                int(params["x_end"]),
                int(params["y_start"]),
                int(params["y_end"]),
                int(params.get("factor", 2)),
            )
        elif operation == "merge_images":
            # Load the other image for merging
            other_id = params.get("other_image_id")
            if not other_id:
                raise ValueError("Missing other_image_id for merge operation")
            other = self.image_repo.get(str(other_id))
            if other is None or other.user_id != user_id:
                raise ValueError("Other image not found or access denied")
            img2 = self.storage.download_to_numpy(other.path)
            out = self.processing.merge_images(
                matrix, img2, float(params.get("transparency", 0.5))
            )
        elif operation.startswith("channel_"):
            # Channel operations: extract or manipulate RGB/CMY channels
            channel = operation.replace("channel_", "")
            enabled = params.get("enabled", True)

            # Ensure RGB format
            rgb = np.repeat(matrix[..., None], 3, axis=2) if matrix.ndim == 2 else matrix.copy()

            if channel in ("red", "green", "blue"):
                idx = {"red": 0, "green": 1, "blue": 2}[channel]
                if enabled:
                    # Keep only selected channel, zero out others
                    for c in range(3):
                        if c != idx:
                            rgb[..., c] = 0
                else:
                    # Zero out selected channel, keep others
                    rgb[..., idx] = 0
                out = rgb
            elif channel in ("cyan", "magenta", "yellow"):
                # Extract CMY channel as grayscale
                idx = {"cyan": 0, "magenta": 1, "yellow": 2}[channel]
                cmy = 1.0 - rgb[..., :3]
                out = cmy[..., idx]
            else:
                raise ValueError(f"Unsupported channel: {channel}")
        else:
            raise ValueError(f"Unsupported operation: {operation}")

        return out

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
class ProcessImageUseCase:
    storage: SupabaseStorage
    image_repo: ImageRepository
    history_repo: HistoryRepository
    processing: ProcessingService

    def execute(
        self, user_id: str, image_id: str, operation: str, params: dict[str, Any]
    ) -> ImageEntity:
        """
        Save an image edit permanently as a new version.

        WORKFLOW:
        1. User previews edits using PreviewImageUseCase (temporary, not saved)
        2. User clicks "Save" → This method creates permanent version

        IMPORTANT: All edits are applied to the ROOT/ORIGINAL image.
        This prevents cumulative degradation and ensures predictable results.

        Example workflow:
        - User uploads image (v1)
        - User adjusts brightness slider → PreviewImageUseCase shows temp result
        - User adjusts more → Preview recalculates from v1 each time
        - User clicks "Save" → This method creates v2 (permanent)
        - User later edits v2 → Still applies to v1, creates v3

        This creates a new version instead of overwriting.
        Each version maintains a link to:
        - The root/original image (root_image_id)
        - The immediate parent version for UI context (parent_version_id)
        - A sequential version number

        This allows users to:
        - View the complete edit history
        - Revert to any previous version
        - Apply edits without cumulative effects
        """
        # Load the image reference (for metadata and versioning)
        image = self.image_repo.get(image_id)
        if image is None or image.user_id != user_id:
            raise ValueError("Image not found")

        # Determine root and version info
        root_id = image.root_image_id if image.root_image_id else image.id
        parent_id = image.id

        # SMART BASE IMAGE SELECTION:
        # - For structural operations (rotate, crop, translate): Use current version as base
        # - For color/filter operations: Use base_image_id if set (after rotation/crop), otherwise
        # use root
        # - For RGB channel operations: Always use root to avoid cumulative effects
        op = operation.lower()
        structural_ops = {"rotate", "crop", "translate"}
        channel_ops = {
            "channel_red",
            "channel_green",
            "channel_blue",
            "channel_cyan",
            "channel_magenta",
            "channel_yellow",
        }

        if op in structural_ops:
            # Use the current image as base (preserves previous rotations/crops)
            base_image = image
            base_id = image.id
        elif op in channel_ops:
            # Channel operations always use root image to avoid cumulative effects
            base_image = self.image_repo.get(root_id)
            base_id = root_id
        else:
            # Color/filter operations: Use base_image_id if set (after rotation/crop), otherwise use root
            if image.base_image_id:
                base_image = self.image_repo.get(image.base_image_id)
                base_id = image.base_image_id
            else:
                base_image = self.image_repo.get(root_id)
                base_id = root_id

        if base_image is None:
            raise ValueError("Base image not found")

        src = self.storage.download_to_numpy(base_image.path)

        # Get current max version number for this root
        version_chain = self.image_repo.get_version_chain(root_id, user_id)
        next_version = max((v.version_number for v in version_chain), default=0) + 1

        # route operation
        op = operation.lower()
        out: np.ndarray
        if op == "brightness":
            out = self.processing.adjust_brightness(src, float(params.get("factor", 0.0)))
        elif op == "log_contrast":
            out = self.processing.adjust_log_contrast(src, float(params.get("k", 1.0)))
        elif op == "exp_contrast":
            out = self.processing.adjust_exp_contrast(src, float(params.get("k", 1.0)))
        elif op == "invert":
            out = self.processing.invert_color(src)
        elif op == "grayscale_average":
            out = self.processing.grayscale_average(src)
        elif op == "grayscale_luminosity":
            out = self.processing.grayscale_luminosity(src)
        elif op == "grayscale_midgray":
            out = self.processing.grayscale_midgray(src)
        elif op == "binarize":
            out = self.processing.binarize(
                self.processing.grayscale_luminosity(src), float(params.get("threshold", 0.5))
            )
        elif op == "translate":
            out = self.processing.translate(src, int(params.get("dx", 0)), int(params.get("dy", 0)))
        elif op == "rotate":
            out = self.processing.rotate(src, float(params.get("angle", 0.0)))
        elif op == "crop":
            out = self.processing.crop(
                src,
                int(params["x_start"]),
                int(params["x_end"]),
                int(params["y_start"]),
                int(params["y_end"]),
            )
        elif op == "reduce_resolution":
            out = self.processing.reduce_resolution(src, int(params.get("factor", 2)))
        elif op == "enlarge_region":
            out = self.processing.enlarge_region(
                src,
                int(params["x_start"]),
                int(params["x_end"]),
                int(params["y_start"]),
                int(params["y_end"]),
                int(params.get("factor", 2)),
            )
        elif op == "merge_images":
            other_id = params.get("other_image_id")
            if not other_id:
                raise ValueError("Missing other_image_id")
            other = self.image_repo.get(str(other_id))
            if other is None or other.user_id != user_id:
                raise ValueError("Other image not found")
            img2 = self.storage.download_to_numpy(other.path)
            out = self.processing.merge_images(src, img2, float(params.get("transparency", 0.5)))
        elif op.startswith("channel_"):
            # Channel operations: extract or manipulate RGB/CMY channels
            channel = op.replace("channel_", "")
            enabled = params.get("enabled", True)

            # Ensure RGB format
            rgb = np.repeat(src[..., None], 3, axis=2) if src.ndim == 2 else src.copy()

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
        elif op == "histogram":
            # histogram is not persisted as image; return raises to guide route
            # to different response
            raise NotImplementedError("histogram")
        else:
            raise ValueError("Unsupported operation")

        # persist processed image as a new version
        ext = str(params.get("ext", "png"))
        stored = self.storage.upload_numpy(user_id=user_id, array=out, ext=ext)

        # Determine the base image for future edits
        # If this is a structural operation, this version becomes the new base
        # Otherwise, inherit the base from the current image
        new_base_id = (
            None
            if op in structural_ops
            else image.base_image_id if image.base_image_id else base_id
        )

        # Create new version with full tracking
        temp_entity = self.image_repo.create(
            user_id=user_id,
            path=stored.path,
            width=stored.width,
            height=stored.height,
            mime_type=stored.content_type,
            original_id=parent_id,  # Keep for backward compatibility
            original_filename=image.original_filename,  # Copy from parent image
            file_size=stored.size,
            # Version tracking
            root_image_id=root_id,
            parent_version_id=parent_id,
            version_number=next_version,
            is_root=False,
            base_image_id=new_base_id,
        )

        # For structural operations, update base_image_id to point to self
        if op in structural_ops and new_base_id is None:
            # Create a new entity with base_image_id pointing to itself
            entity = ImageEntity(
                id=temp_entity.id,
                user_id=temp_entity.user_id,
                path=temp_entity.path,
                width=temp_entity.width,
                height=temp_entity.height,
                mime_type=temp_entity.mime_type,
                created_at=temp_entity.created_at,
                original_id=temp_entity.original_id,
                original_filename=temp_entity.original_filename,
                file_size=temp_entity.file_size,
                root_image_id=temp_entity.root_image_id,
                parent_version_id=temp_entity.parent_version_id,
                version_number=temp_entity.version_number,
                is_root=temp_entity.is_root,
                base_image_id=temp_entity.id,  # Point to self!
            )
        else:
            entity = temp_entity

        # Record in history with complete tracking
        self.history_repo.create(
            user_id=user_id,
            image_id=entity.id,
            operation_type=op,
            parameters=params,
            result_storage_path=entity.path,
            source_image_id=base_id,  # The image we actually used as base
            root_image_id=root_id,
        )
        return entity

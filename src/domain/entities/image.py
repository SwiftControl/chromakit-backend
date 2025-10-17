from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ImageEntity:
    id: str
    user_id: str
    path: str  # storage path {user_id}/{uuid}.{ext}
    width: int
    height: int
    mime_type: str
    created_at: datetime
    original_id: str | None = None  # DEPRECATED: if derived from another image (parent)
    original_filename: str | None = None
    file_size: int | None = None  # bytes
    # Version tracking fields
    root_image_id: str | None = None  # Points to the first/original uploaded image
    parent_version_id: str | None = (
        None  # Points to the immediate parent version used for this edit
    )
    version_number: int = 1  # Version number within the chain (1 = original upload)
    is_root: bool = True  # True if this is an original uploaded image
    # Base image tracking - which version to use as base for edits
    base_image_id: str | None = None  # Points to the version to use as base (for rotations, crops)

    # Backwards-compat property
    @property
    def content_type(self) -> str:
        return self.mime_type

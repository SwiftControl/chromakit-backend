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
    original_id: str | None = None  # if derived from another image
    original_filename: str | None = None
    file_size: int | None = None  # bytes

    # Backwards-compat property
    @property
    def content_type(self) -> str:
        return self.mime_type

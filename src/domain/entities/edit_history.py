from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class EditHistoryEntity:
    id: str
    user_id: str
    image_id: str
    operation: str
    params: dict[str, Any]
    created_at: datetime

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ProfileEntity:
    id: str  # user id from Supabase auth
    email: str | None
    created_at: datetime | None = None
    display_name: str | None = None

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.domain.services.processing_service import ProcessingService
from src.infrastructure.database.repositories.history_repository import HistoryRepository
from src.infrastructure.database.repositories.image_repository import ImageRepository
from src.infrastructure.database.repositories.profile_repository import ProfileRepository
from src.infrastructure.database.supabase_client import (
    SupabaseAuthAdapter,
    UserInfo,
    get_supabase_client,
)
from src.infrastructure.storage.supabase_storage import SupabaseStorage

_bearer_scheme = HTTPBearer(auto_error=False)


def get_auth_adapter() -> SupabaseAuthAdapter:
    return SupabaseAuthAdapter()


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(_bearer_scheme)] = None,
    auth: Annotated[SupabaseAuthAdapter, Depends(get_auth_adapter)] = None,
) -> UserInfo:
    if not credentials or not credentials.scheme or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = credentials.credentials
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    try:
        user = auth.validate_token(token)
        return user
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))


def get_storage() -> SupabaseStorage:
    client = get_supabase_client()
    return SupabaseStorage(client)


def get_image_repo() -> ImageRepository:
    return ImageRepository(get_supabase_client())


def get_history_repo() -> HistoryRepository:
    return HistoryRepository(get_supabase_client())


def get_profile_repo() -> ProfileRepository:
    return ProfileRepository(get_supabase_client())


def get_processing_service() -> ProcessingService:
    return ProcessingService()

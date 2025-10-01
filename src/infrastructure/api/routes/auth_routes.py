from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.infrastructure.api.dependencies import get_current_user, get_profile_repo
from src.infrastructure.database.repositories.profile_repository import ProfileRepository

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/validate")
def validate_token(
    user=Depends(get_current_user),
    profiles: ProfileRepository = Depends(get_profile_repo),
):
    # ensure profile exists
    prof = profiles.upsert(user.id, user.email)
    return {"user_id": prof.id, "email": prof.email}


@router.get("/me")
def get_me(
    user=Depends(get_current_user),
    profiles: ProfileRepository = Depends(get_profile_repo),
):
    prof = profiles.upsert(user.id, user.email)
    return {"id": prof.id, "email": prof.email, "name": prof.display_name, "created_at": prof.created_at}


class UpdateProfileBody(BaseModel):
    name: str


@router.patch("/profile")
def update_profile(
    body: UpdateProfileBody,
    user=Depends(get_current_user),
    profiles: ProfileRepository = Depends(get_profile_repo),
):
    if not body.name:
        raise HTTPException(status_code=400, detail="Invalid name")
    prof = profiles.set_display_name(user.id, body.name)
    return {"id": prof.id, "email": prof.email, "name": prof.display_name}

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.infrastructure.api.dependencies import get_current_user, get_profile_repo
from src.infrastructure.database.repositories.profile_repository import ProfileRepository

router = APIRouter(
    prefix="/auth", 
    tags=["Authentication"],
    responses={
        401: {"description": "Unauthorized - Invalid or missing authentication token"},
        422: {"description": "Validation Error - Invalid request format"}
    }
)


class ValidateTokenResponse(BaseModel):
    """Response model for token validation."""
    user_id: str = Field(..., description="Unique identifier of the authenticated user")
    email: str = Field(..., description="Email address of the authenticated user", example="user@example.com")


@router.post(
    "/validate",
    response_model=ValidateTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate Authentication Token",
    description="""
    Validate the provided JWT token and ensure the user profile exists.
    
    This endpoint:
    - Verifies the JWT token in the Authorization header
    - Creates or updates the user profile in the database
    - Returns basic user information
    
    **Authentication required**: Yes (Bearer token)
    """,
    response_description="User information confirming valid authentication"
)
def validate_token(
    user=Depends(get_current_user),
    profiles: ProfileRepository = Depends(get_profile_repo),
):
    """Validate JWT token and ensure user profile exists."""
    # ensure profile exists
    prof = profiles.upsert(user.id, user.email)
    return {"user_id": prof.id, "email": prof.email}


class UserProfileResponse(BaseModel):
    """Response model for user profile information."""
    id: str = Field(..., description="Unique identifier of the user")
    email: str = Field(..., description="Email address of the user", example="user@example.com")
    name: str | None = Field(None, description="Display name of the user", example="John Doe")
    created_at: datetime = Field(..., description="ISO timestamp when the user profile was created")


@router.get(
    "/me",
    response_model=UserProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Current User Profile",
    description="""
    Retrieve the complete profile information for the currently authenticated user.
    
    This endpoint returns:
    - User ID and email
    - Display name (if set)
    - Profile creation timestamp
    
    **Authentication required**: Yes (Bearer token)
    """,
    response_description="Complete user profile information"
)
def get_me(
    user=Depends(get_current_user),
    profiles: ProfileRepository = Depends(get_profile_repo),
):
    """Get current user's profile information."""
    prof = profiles.upsert(user.id, user.email)
    return {"id": prof.id, "email": prof.email, "name": prof.display_name, "created_at": prof.created_at}


class UpdateProfileBody(BaseModel):
    """Request model for updating user profile."""
    name: str = Field(..., min_length=1, max_length=100, description="Display name for the user", example="John Doe")


class UpdateProfileResponse(BaseModel):
    """Response model for profile update."""
    id: str = Field(..., description="Unique identifier of the user")
    email: str = Field(..., description="Email address of the user")
    name: str = Field(..., description="Updated display name of the user")


@router.patch(
    "/profile",
    response_model=UpdateProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Update User Profile",
    description="""
    Update the display name for the currently authenticated user.
    
    **Request Requirements:**
    - Display name must be between 1 and 100 characters
    - Display name cannot be empty or whitespace only
    
    **Authentication required**: Yes (Bearer token)
    """,
    response_description="Updated user profile information",
    responses={
        400: {"description": "Bad Request - Invalid name provided"}
    }
)
def update_profile(
    body: UpdateProfileBody,
    user=Depends(get_current_user),
    profiles: ProfileRepository = Depends(get_profile_repo),
):
    """Update the current user's display name."""
    if not body.name or not body.name.strip():
        raise HTTPException(status_code=400, detail="Display name cannot be empty")
    prof = profiles.set_display_name(user.id, body.name.strip())
    return {"id": prof.id, "email": prof.email, "name": prof.display_name}

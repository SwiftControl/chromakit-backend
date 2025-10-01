from __future__ import annotations

from io import BytesIO

import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from PIL import Image

from src.application.dtos.image_dto import (
    DeleteImageResponse,
    ImageMetadata,
    ListImagesResponse,
    UploadImageResponse,
)
from src.application.use_cases.upload_image import UploadImageUseCase
from src.infrastructure.api.dependencies import (
    get_current_user,
    get_history_repo,
    get_image_repo,
    get_storage,
)
from src.infrastructure.database.repositories.history_repository import HistoryRepository
from src.infrastructure.database.repositories.image_repository import ImageRepository
from src.infrastructure.storage.supabase_storage import SupabaseStorage

router = APIRouter(
    prefix="/images",
    tags=["Image Management"],
    responses={
        401: {"description": "Unauthorized - Invalid or missing authentication token"},
        404: {"description": "Not Found - Image does not exist or user doesn't have access"},
        422: {"description": "Validation Error - Invalid request format"},
    },
)


def _load_numpy_from_upload(file: UploadFile) -> tuple[np.ndarray, int, str]:
    data = file.file.read()
    img = Image.open(BytesIO(data)).convert("RGB")
    arr = np.asarray(img).astype(np.float32) / 255.0
    return arr, len(data), Image.MIME.get(img.format, "image/png")


@router.post(
    "/upload",
    response_model=UploadImageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload Image",
    description="""
    Upload a new image file to the system.
    
    **Supported formats**: JPEG, PNG, GIF, BMP, TIFF, WEBP
    **Maximum file size**: Varies based on server configuration
    **Authentication required**: Yes (Bearer token)
    
    The uploaded image will be:
    - Converted to RGB format for processing
    - Stored in the user's personal storage space
    - Assigned a unique identifier for future operations
    - Made available for image processing operations
    """,
    response_description="Metadata of the successfully uploaded image",
    responses={
        400: {"description": "Bad Request - Invalid image file or unsupported format"},
        413: {"description": "Payload Too Large - File size exceeds limit"},
    },
)
async def upload_image(
    file: UploadFile = File(..., description="Image file to upload"),
    user=Depends(get_current_user),
    storage: SupabaseStorage = Depends(get_storage),
    images: ImageRepository = Depends(get_image_repo),
):
    """Upload a new image file and create metadata entry."""
    try:
        arr, size, mime = _load_numpy_from_upload(file)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid image file: {exc}") from exc
    # Ensure we always have a filename (FastAPI should provide it, but be defensive)
    filename = file.filename or "uploaded_image.png"
    ext = filename.split(".")[-1].lower() if "." in filename else "png"

    uc = UploadImageUseCase(storage=storage, image_repo=images)
    entity = uc.execute(
        user_id=user.id,
        array=arr,
        ext=ext,
        original_filename=filename,
        file_size=size,
        mime_type=mime,
    )
    return UploadImageResponse(
        image=ImageMetadata(
            id=entity.id,
            user_id=entity.user_id,
            path=entity.path,
            width=entity.width,
            height=entity.height,
            mime_type=entity.mime_type,
            created_at=entity.created_at,
            original_id=entity.original_id,
            original_filename=entity.original_filename,
            file_size=entity.file_size,
            url=images.get_public_url(entity.path),
        )
    )


@router.get(
    "",
    response_model=ListImagesResponse,
    summary="List User Images",
    description="""
    Retrieve a paginated list of all images owned by the authenticated user.
    
    **Features:**
    - Paginated results with configurable limit and offset
    - Results sorted by creation date (newest first) by default
    - Includes full metadata and public URLs for each image
    - Only returns images owned by the authenticated user
    
    **Authentication required**: Yes (Bearer token)
    """,
    response_description="Paginated list of user images with metadata",
)
async def list_images(
    user=Depends(get_current_user),
    images: ImageRepository = Depends(get_image_repo),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of images to return (1-100)"),
    offset: int = Query(0, ge=0, description="Number of images to skip from the beginning"),
    sort: str | None = Query(None, description="Sort field (not implemented yet)"),
):
    """Get paginated list of user's images."""
    items = images.list_by_user(user.id)
    total = len(items)
    # sort by created_at desc by default
    items.sort(key=lambda i: i.created_at, reverse=True)
    page = items[offset : offset + limit]
    payload: list[ImageMetadata] = [
        ImageMetadata(
            id=it.id,
            user_id=it.user_id,
            path=it.path,
            width=it.width,
            height=it.height,
            mime_type=it.mime_type,
            created_at=it.created_at,
            original_id=it.original_id,
            original_filename=it.original_filename,
            file_size=it.file_size,
            url=images.get_public_url(it.path),
        )
        for it in page
    ]
    return ListImagesResponse(images=payload, total=total, limit=limit, offset=offset)


@router.get(
    "/{image_id}",
    response_model=ImageMetadata,
    summary="Get Image Metadata",
    description="""
    Retrieve complete metadata for a specific image.
    
    **Returns:**
    - Image dimensions (width, height)
    - File information (size, MIME type, original filename)
    - Creation timestamp
    - Public URL for viewing
    - Processing history reference (if processed image)
    
    **Authentication required**: Yes (Bearer token)
    **Access control**: Users can only access their own images
    """,
    response_description="Complete metadata for the requested image",
)
async def get_image(
    image_id: str,
    user=Depends(get_current_user),
    images: ImageRepository = Depends(get_image_repo),
):
    """Get metadata for a specific image."""
    entity = images.get(image_id)
    if entity is None or entity.user_id != user.id:
        raise HTTPException(status_code=404, detail="Image not found or access denied")
    return ImageMetadata(
        id=entity.id,
        user_id=entity.user_id,
        path=entity.path,
        width=entity.width,
        height=entity.height,
        mime_type=entity.mime_type,
        created_at=entity.created_at,
        original_id=entity.original_id,
        original_filename=entity.original_filename,
        file_size=entity.file_size,
        url=images.get_public_url(entity.path),
    )


@router.get(
    "/{image_id}/download",
    summary="Download Image File",
    description="""
    Download the actual image file content.
    
    **Returns:** Raw image file data with appropriate MIME type
    **Authentication required**: Yes (Bearer token)
    **Access control**: Users can only download their own images
    
    The response will have the correct Content-Type header based on the image format.
    """,
    response_description="Binary image file data",
    responses={200: {"content": {"image/*": {}}, "description": "Image file content"}},
)
async def download_image(
    image_id: str,
    user=Depends(get_current_user),
    images: ImageRepository = Depends(get_image_repo),
    storage: SupabaseStorage = Depends(get_storage),
):
    """Download the binary content of an image file."""
    entity = images.get(image_id)
    if entity is None or entity.user_id != user.id:
        raise HTTPException(status_code=404, detail="Image not found or access denied")
    data = storage.download_bytes(entity.path)
    return Response(content=data, media_type=entity.mime_type)


@router.delete(
    "/{image_id}",
    response_model=DeleteImageResponse,
    summary="Delete Image",
    description="""
    Permanently delete an image and all associated data.
    
    **This operation will:**
    - Remove the image file from storage
    - Delete the image metadata from database
    - Remove all processing history for this image
    - Cannot be undone
    
    **Authentication required**: Yes (Bearer token)
    **Access control**: Users can only delete their own images
    """,
    response_description="Confirmation of successful deletion",
)
async def delete_image(
    image_id: str,
    user=Depends(get_current_user),
    images: ImageRepository = Depends(get_image_repo),
    storage: SupabaseStorage = Depends(get_storage),
    history: HistoryRepository = Depends(get_history_repo),
):
    """Permanently delete an image and all associated data."""
    entity = images.get(image_id)
    if entity is None or entity.user_id != user.id:
        raise HTTPException(status_code=404, detail="Image not found or access denied")
    # cascade: delete history, then file, then db row
    history.delete_by_image(image_id)
    storage.delete(entity.path)
    ok = images.delete(image_id)
    return DeleteImageResponse(ok=ok)

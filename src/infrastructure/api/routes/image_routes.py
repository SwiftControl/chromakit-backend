from __future__ import annotations

from io import BytesIO
from typing import List

import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status, Query
from fastapi.responses import Response
from PIL import Image

from src.infrastructure.api.dependencies import (
    get_current_user,
    get_image_repo,
    get_storage,
    get_history_repo,
)
from src.infrastructure.database.repositories.image_repository import ImageRepository
from src.infrastructure.database.repositories.history_repository import HistoryRepository
from src.infrastructure.storage.supabase_storage import SupabaseStorage
from src.application.dtos.image_dto import (
    ImageMetadata,
    UploadImageResponse,
    ListImagesResponse,
    DeleteImageResponse,
)
from src.application.use_cases.upload_image import UploadImageUseCase

router = APIRouter(prefix="/images", tags=["images"])


def _load_numpy_from_upload(file: UploadFile) -> tuple[np.ndarray, int, str]:
    data = file.file.read()
    img = Image.open(BytesIO(data)).convert("RGB")
    arr = np.asarray(img).astype(np.float32) / 255.0
    return arr, len(data), Image.MIME[img.format] if img.format in Image.MIME else "image/png"


@router.post("/upload", response_model=UploadImageResponse, status_code=status.HTTP_201_CREATED)
async def upload_image(
    file: UploadFile = File(...),
    user=Depends(get_current_user),
    storage: SupabaseStorage = Depends(get_storage),
    images: ImageRepository = Depends(get_image_repo),
):
    try:
        arr, size, mime = _load_numpy_from_upload(file)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid image: {exc}")
    ext = (file.filename or "image.png").split(".")[-1].lower()
    uc = UploadImageUseCase(storage=storage, image_repo=images)
    entity = uc.execute(
        user_id=user.id,
        array=arr,
        ext=ext,
        original_filename=file.filename,
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
        )
    )


@router.get("", response_model=ListImagesResponse)
async def list_images(
    user=Depends(get_current_user),
    images: ImageRepository = Depends(get_image_repo),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sort: str | None = Query(None),
):
    items = images.list_by_user(user.id)
    total = len(items)
    # sort by created_at desc by default
    items.sort(key=lambda i: i.created_at, reverse=True)
    page = items[offset : offset + limit]
    payload: List[ImageMetadata] = [
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
        )
        for it in page
    ]
    return ListImagesResponse(images=payload, total=total, limit=limit, offset=offset)


@router.get("/{image_id}", response_model=ImageMetadata)
async def get_image(
    image_id: str,
    user=Depends(get_current_user),
    images: ImageRepository = Depends(get_image_repo),
):
    entity = images.get(image_id)
    if entity is None or entity.user_id != user.id:
        raise HTTPException(status_code=404, detail="Image not found")
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
    )


@router.get("/{image_id}/download")
async def download_image(
    image_id: str,
    user=Depends(get_current_user),
    images: ImageRepository = Depends(get_image_repo),
    storage: SupabaseStorage = Depends(get_storage),
):
    entity = images.get(image_id)
    if entity is None or entity.user_id != user.id:
        raise HTTPException(status_code=404, detail="Image not found")
    data = storage.download_bytes(entity.path)
    return Response(content=data, media_type=entity.mime_type)


@router.delete("/{image_id}", response_model=DeleteImageResponse)
async def delete_image(
    image_id: str,
    user=Depends(get_current_user),
    images: ImageRepository = Depends(get_image_repo),
    storage: SupabaseStorage = Depends(get_storage),
    history: HistoryRepository = Depends(get_history_repo),
):
    entity = images.get(image_id)
    if entity is None or entity.user_id != user.id:
        raise HTTPException(status_code=404, detail="Image not found")
    # cascade: delete history, then file, then db row
    history.delete_by_image(image_id)
    storage.delete(entity.path)
    ok = images.delete(image_id)
    return DeleteImageResponse(ok=ok)

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.infrastructure.api.dependencies import (
    get_current_user,
    get_processing_service,
    get_storage,
    get_image_repo,
    get_history_repo,
)
from src.application.dtos.image_dto import (
    ProcessImageRequest,
    ProcessImageResponse,
    ImageMetadata,
    BrightnessRequest,
    ContrastRequest,
    ChannelRequest,
    GrayscaleRequest,
    NegativeRequest,
    BinarizeRequest,
    TranslateRequest,
    RotateRequest,
    CropRequest,
    ReduceResolutionRequest,
    EnlargeRegionRequest,
    MergeImagesRequest,
)
from src.application.use_cases.process_image import ProcessImageUseCase
from src.domain.services.processing_service import ProcessingService

router = APIRouter(prefix="/processing", tags=["processing"])


@router.post("/{operation}")
async def process_image(
    operation: str,
    body: ProcessImageRequest,
    user=Depends(get_current_user),
    processing: ProcessingService = Depends(get_processing_service),
):
    # special case: histogram returns raw histogram data, not a stored image
    if operation.lower() == "histogram":
        from src.infrastructure.database.repositories.image_repository import ImageRepository
        from src.infrastructure.api.dependencies import get_image_repo  # lazy import for DI

        images: ImageRepository = get_image_repo()
        entity = images.get(body.image_id)
        if entity is None or entity.user_id != user.id:
            raise HTTPException(status_code=404, detail="Image not found")
        from src.infrastructure.storage.supabase_storage import SupabaseStorage
        from src.infrastructure.api.dependencies import get_storage

        storage: SupabaseStorage = get_storage()
        arr = storage.download_to_numpy(entity.path)
        hist = processing.calculate_histogram(arr)
        # Convert numpy arrays to lists for JSON
        return {
            "operation": "histogram",
            "bins": hist["bins"].tolist(),
            "hist": hist["hist"].tolist(),
        }

    # default: run processing use-case which persists new image and history
    from src.infrastructure.api.dependencies import get_storage, get_image_repo, get_history_repo
    from src.infrastructure.storage.supabase_storage import SupabaseStorage
    from src.infrastructure.database.repositories.image_repository import ImageRepository
    from src.infrastructure.database.repositories.history_repository import HistoryRepository

    storage: SupabaseStorage = get_storage()
    images: ImageRepository = get_image_repo()
    history: HistoryRepository = get_history_repo()

    uc = ProcessImageUseCase(storage=storage, image_repo=images, history_repo=history, processing=processing)
    try:
        entity = uc.execute(
            user_id=user.id, image_id=body.image_id, operation=operation, params=dict(body.params)
        )
    except NotImplementedError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return ProcessImageResponse(
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
        ),
        operation=operation,
        params=body.params,
    )


@router.get("/{image_id}/histogram")
async def get_histogram(
    image_id: str,
    user=Depends(get_current_user),
    processing: ProcessingService = Depends(get_processing_service),
):
    from src.infrastructure.database.repositories.image_repository import ImageRepository
    from src.infrastructure.api.dependencies import get_image_repo
    from src.infrastructure.api.dependencies import get_storage
    from src.infrastructure.storage.supabase_storage import SupabaseStorage

    images: ImageRepository = get_image_repo()
    storage: SupabaseStorage = get_storage()
    entity = images.get(image_id)
    if entity is None or entity.user_id != user.id:
        raise HTTPException(status_code=404, detail="Image not found")
    arr = storage.download_to_numpy(entity.path)
    hist = processing.calculate_histogram(arr)
    def to_dict(h):
        # map to spec-style keys
        if arr.ndim == 2:
            return {"gray": h["hist"].tolist()}
        else:
            return {"red": h["hist"][0].tolist(), "green": h["hist"][1].tolist(), "blue": h["hist"][2].tolist()}
    return {"histogram": to_dict(hist)}


@router.post("/brightness")
async def op_brightness(
    body: BrightnessRequest,
    user=Depends(get_current_user),
    processing: ProcessingService = Depends(get_processing_service),
):
    uc = ProcessImageUseCase(get_storage(), get_image_repo(), get_history_repo(), processing)
    entity = uc.execute(user.id, body.image_id, "brightness", {"factor": body.factor})
    return {"id": entity.id, "storage_path": entity.path, "width": entity.width, "height": entity.height, "created_at": entity.created_at}


@router.post("/contrast")
async def op_contrast(
    body: ContrastRequest,
    user=Depends(get_current_user),
    processing: ProcessingService = Depends(get_processing_service),
):
    uc = ProcessImageUseCase(get_storage(), get_image_repo(), get_history_repo(), processing)
    if body.type not in ("logarithmic", "exponential"):
        raise HTTPException(status_code=400, detail="Invalid contrast type")
    operation = "log_contrast" if body.type == "logarithmic" else "exp_contrast"
    entity = uc.execute(user.id, body.image_id, operation, {"k": body.intensity})
    return {"id": entity.id, "storage_path": entity.path, "width": entity.width, "height": entity.height, "created_at": entity.created_at}


@router.post("/negative")
async def op_negative(
    body: NegativeRequest,
    user=Depends(get_current_user),
    processing: ProcessingService = Depends(get_processing_service),
):
    uc = ProcessImageUseCase(get_storage(), get_image_repo(), get_history_repo(), processing)
    entity = uc.execute(user.id, body.image_id, "invert", {})
    return {"id": entity.id, "storage_path": entity.path}


@router.post("/grayscale")
async def op_grayscale(
    body: GrayscaleRequest,
    user=Depends(get_current_user),
    processing: ProcessingService = Depends(get_processing_service),
):
    uc = ProcessImageUseCase(get_storage(), get_image_repo(), get_history_repo(), processing)
    mapping = {
        "average": "grayscale_average",
        "luminosity": "grayscale_luminosity",
        "midgray": "grayscale_midgray",
    }
    if body.method not in mapping:
        raise HTTPException(status_code=400, detail="Invalid grayscale method")
    entity = uc.execute(user.id, body.image_id, mapping[body.method], {})
    return {"id": entity.id, "storage_path": entity.path}


@router.post("/binarize")
async def op_binarize(
    body: BinarizeRequest,
    user=Depends(get_current_user),
    processing: ProcessingService = Depends(get_processing_service),
):
    uc = ProcessImageUseCase(get_storage(), get_image_repo(), get_history_repo(), processing)
    entity = uc.execute(user.id, body.image_id, "binarize", {"threshold": body.threshold})
    return {"id": entity.id, "storage_path": entity.path}


@router.post("/translate")
async def op_translate(
    body: TranslateRequest,
    user=Depends(get_current_user),
    processing: ProcessingService = Depends(get_processing_service),
):
    uc = ProcessImageUseCase(get_storage(), get_image_repo(), get_history_repo(), processing)
    entity = uc.execute(user.id, body.image_id, "translate", {"dx": body.dx, "dy": body.dy})
    return {"id": entity.id, "storage_path": entity.path}


@router.post("/rotate")
async def op_rotate(
    body: RotateRequest,
    user=Depends(get_current_user),
    processing: ProcessingService = Depends(get_processing_service),
):
    uc = ProcessImageUseCase(get_storage(), get_image_repo(), get_history_repo(), processing)
    entity = uc.execute(user.id, body.image_id, "rotate", {"angle": body.angle})
    return {"id": entity.id, "storage_path": entity.path}


@router.post("/crop")
async def op_crop(
    body: CropRequest,
    user=Depends(get_current_user),
    processing: ProcessingService = Depends(get_processing_service),
):
    uc = ProcessImageUseCase(get_storage(), get_image_repo(), get_history_repo(), processing)
    params = {"x_start": body.x_start, "x_end": body.x_end, "y_start": body.y_start, "y_end": body.y_end}
    entity = uc.execute(user.id, body.image_id, "crop", params)
    return {"id": entity.id, "storage_path": entity.path}


@router.post("/reduce-resolution")
async def op_reduce_resolution(
    body: ReduceResolutionRequest,
    user=Depends(get_current_user),
    processing: ProcessingService = Depends(get_processing_service),
):
    uc = ProcessImageUseCase(get_storage(), get_image_repo(), get_history_repo(), processing)
    entity = uc.execute(user.id, body.image_id, "reduce_resolution", {"factor": body.factor})
    return {"id": entity.id, "storage_path": entity.path}


@router.post("/enlarge-region")
async def op_enlarge_region(
    body: EnlargeRegionRequest,
    user=Depends(get_current_user),
    processing: ProcessingService = Depends(get_processing_service),
):
    uc = ProcessImageUseCase(get_storage(), get_image_repo(), get_history_repo(), processing)
    params = {
        "x_start": body.x_start,
        "x_end": body.x_end,
        "y_start": body.y_start,
        "y_end": body.y_end,
        "factor": body.zoom_factor,
    }
    entity = uc.execute(user.id, body.image_id, "enlarge_region", params)
    return {"id": entity.id, "storage_path": entity.path}


@router.post("/merge")
async def op_merge(
    body: MergeImagesRequest,
    user=Depends(get_current_user),
    processing: ProcessingService = Depends(get_processing_service),
):
    uc = ProcessImageUseCase(get_storage(), get_image_repo(), get_history_repo(), processing)
    entity = uc.execute(
        user.id,
        body.image1_id,
        "merge_images",
        {"other_image_id": body.image2_id, "transparency": body.transparency},
    )
    return {"id": entity.id, "storage_path": entity.path}


@router.post("/channel")
async def op_channel(
    body: ChannelRequest,
    user=Depends(get_current_user),
    processing: ProcessingService = Depends(get_processing_service),
):
    # Implement minimal channel toggle/extract
    images = get_image_repo()
    storage = get_storage()
    history = get_history_repo()
    src_meta = images.get(body.image_id)
    if src_meta is None or src_meta.user_id != user.id:
        raise HTTPException(status_code=404, detail="Image not found")
    arr = storage.download_to_numpy(src_meta.path)
    import numpy as np

    ch = body.channel.lower()
    if arr.ndim == 2:
        rgb = np.repeat(arr[..., None], 3, axis=2)
    else:
        rgb = arr.copy()
    if ch in ("red", "green", "blue"):
        idx = {"red": 0, "green": 1, "blue": 2}[ch]
        if body.enabled:
            # zero-out other channels
            for c in range(3):
                if c != idx:
                    rgb[..., c] = 0
        else:
            rgb[..., idx] = 0
    elif ch in ("cyan", "magenta", "yellow"):
        # produce grayscale of selected CMY channel
        idx = {"cyan": 0, "magenta": 1, "yellow": 2}[ch]
        cmy = 1.0 - rgb[..., :3]
        rgb = cmy[..., idx]
    else:
        raise HTTPException(status_code=400, detail="Invalid channel")
    stored = storage.upload_numpy(user.id, rgb, ext="png")
    entity = images.create(
        user_id=user.id,
        path=stored.path,
        width=stored.width,
        height=stored.height,
        mime_type=stored.content_type,
        original_id=src_meta.id,
        original_filename=src_meta.original_filename,
        file_size=stored.size,
    )
    history.create(user.id, entity.id, "channel", {"channel": body.channel, "enabled": body.enabled})
    return {"id": entity.id, "storage_path": entity.path}

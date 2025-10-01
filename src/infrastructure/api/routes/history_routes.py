from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from src.application.dtos.history_dto import DeleteHistoryResponse, HistoryItem, ListHistoryResponse
from src.infrastructure.api.dependencies import get_current_user, get_history_repo
from src.infrastructure.database.repositories.history_repository import HistoryRepository

router = APIRouter(
    prefix="/history",
    tags=["Processing History"],
    responses={
        401: {"description": "Unauthorized - Invalid or missing authentication token"},
        404: {"description": "Not Found - History item does not exist or user doesn't have access"},
        422: {"description": "Validation Error - Invalid request format"},
    },
)


@router.get(
    "",
    response_model=ListHistoryResponse,
    summary="List Processing History",
    description="""
    Retrieve a paginated list of image processing operations performed by the user.
    
    **Features:**
    - Paginated results with configurable limit and offset
    - Optional filtering by specific image ID
    - Includes operation details and parameters used
    - Results sorted by creation time (newest first)
    
    **Authentication required**: Yes (Bearer token)
    """,
    response_description="List of processing history items",
)
async def list_history(
    user=Depends(get_current_user),
    history: HistoryRepository = Depends(get_history_repo),
    limit: int = Query(
        50, ge=1, le=200, description="Maximum number of history items to return (1-200)"
    ),
    offset: int = Query(0, ge=0, description="Number of history items to skip from the beginning"),
    image_id: str | None = Query(None, description="Filter history by specific image ID"),
):
    """Get paginated list of user's processing history."""
    items = history.list_by_user(user.id)
    if image_id:
        items = [h for h in items if h.image_id == image_id]
    page = items[offset : offset + limit]
    out = [
        HistoryItem(
            id=h.id,
            user_id=h.user_id,
            image_id=h.image_id,
            operation=h.operation,
            params=h.params,
            created_at=h.created_at,
        )
        for h in page
    ]
    return ListHistoryResponse(history=out)


@router.get(
    "/{history_id}",
    response_model=HistoryItem,
    summary="Get History Item Details",
    description="""
    Retrieve detailed information about a specific processing operation.
    
    **Returns:**
    - Operation name and parameters used
    - Target image ID
    - Execution timestamp
    - All metadata associated with the operation
    
    **Authentication required**: Yes (Bearer token)
    **Access control**: Users can only access their own history items
    """,
    response_description="Detailed information about the processing operation",
)
async def get_history(
    history_id: str,
    user=Depends(get_current_user),
    history: HistoryRepository = Depends(get_history_repo),
):
    """Get detailed information about a specific history item."""
    item = history.get(history_id)
    if item is None or item.user_id != user.id:
        raise HTTPException(status_code=404, detail="History item not found or access denied")
    return HistoryItem(
        id=item.id,
        user_id=item.user_id,
        image_id=item.image_id,
        operation=item.operation,
        params=item.params,
        created_at=item.created_at,
    )


@router.delete(
    "/{history_id}",
    response_model=DeleteHistoryResponse,
    summary="Delete History Item",
    description="""
    Delete a specific processing history record.
    
    **Note**: This only removes the history record, not the processed image itself.
    To delete the actual image, use the DELETE /images/{image_id} endpoint.
    
    **Authentication required**: Yes (Bearer token)
    **Access control**: Users can only delete their own history items
    """,
    response_description="Confirmation of successful deletion",
)
async def delete_history(
    history_id: str,
    user=Depends(get_current_user),
    history: HistoryRepository = Depends(get_history_repo),
):
    """Delete a specific history record."""
    item = history.get(history_id)
    if item is None or item.user_id != user.id:
        raise HTTPException(status_code=404, detail="History item not found or access denied")
    ok = history.delete(history_id)
    return {"ok": ok}

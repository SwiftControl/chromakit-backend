from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from src.infrastructure.api.dependencies import get_current_user, get_history_repo
from src.infrastructure.database.repositories.history_repository import HistoryRepository
from src.application.dtos.history_dto import ListHistoryResponse, HistoryItem

router = APIRouter(prefix="/history", tags=["history"])


@router.get("", response_model=ListHistoryResponse)
async def list_history(
    user=Depends(get_current_user),
    history: HistoryRepository = Depends(get_history_repo),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    image_id: str | None = Query(None),
):
    items = history.list_by_user(user.id)
    if image_id:
        items = [h for h in items if h.image_id == image_id]
    total = len(items)
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


@router.get("/{history_id}", response_model=HistoryItem)
async def get_history(
    history_id: str,
    user=Depends(get_current_user),
    history: HistoryRepository = Depends(get_history_repo),
):
    item = history.get(history_id)
    if item is None or item.user_id != user.id:
        raise HTTPException(status_code=404, detail="History not found")
    return HistoryItem(
        id=item.id,
        user_id=item.user_id,
        image_id=item.image_id,
        operation=item.operation,
        params=item.params,
        created_at=item.created_at,
    )


@router.delete("/{history_id}")
async def delete_history(
    history_id: str,
    user=Depends(get_current_user),
    history: HistoryRepository = Depends(get_history_repo),
):
    item = history.get(history_id)
    if item is None or item.user_id != user.id:
        raise HTTPException(status_code=404, detail="History not found")
    ok = history.delete(history_id)
    return {"ok": ok}

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from db.database import get_db
from db.models import RequestLog, User
from db import crud

router = APIRouter()

@router.get("/summary")
async def summary(
    key_id: str | None = None,
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stats = await crud.get_stats(db, user_id=current_user.id, key_id=key_id, days=days)
    by_tier = stats.get("by_tier", {})
    return {
        "total_requests": stats.get("total_requests", 0),
        "by_tier": {
            "weak": by_tier.get(0, 0),
            "mid": by_tier.get(1, 0),
            "strong": by_tier.get(2, 0)
        },
        "total_cost_usd": stats.get("total_cost_usd", 0.0),
        "cost_saved_vs_always_strong": stats.get("cost_saved_vs_always_strong", 0.0),
        "avg_latency_ms": stats.get("avg_latency_ms", 0.0),
        "success_rate": stats.get("success_rate", 0.0)
    }

@router.get("/requests")
async def requests(
    key_id: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    logs = await crud.get_request_logs(
        db,
        user_id=current_user.id,
        key_id=key_id,
        limit=limit,
        offset=offset
    )
    return [
        {
            "id": str(log.id),
            "virtual_key_id": str(log.virtual_key_id),
            "user_id": str(log.user_id),
            "prompt_preview": log.prompt_preview,
            "prompt_length": log.prompt_length,
            "tier_assigned": log.tier_assigned,
            "confidence": log.confidence,
            "model_used": log.model_used,
            "input_tokens": log.input_tokens,
            "output_tokens": log.output_tokens,
            "latency_ms": log.latency_ms,
            "cost_estimate_usd": log.cost_estimate_usd,
            "status": log.status,
            "error_message": log.error_message,
            "created_at": log.created_at
        }
        for log in logs
    ]

@router.get("/daily")
async def daily(
    key_id: str | None = None,
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    cutoff = datetime.utcnow() - timedelta(days=days)
    query = select(
        func.date(RequestLog.created_at).label("date"),
        func.count(RequestLog.id).label("requests"),
        func.coalesce(func.sum(RequestLog.cost_estimate_usd), 0).label("cost_usd")
    ).where(
        RequestLog.user_id == current_user.id,
        RequestLog.created_at >= cutoff
    )

    if key_id:
        query = query.where(RequestLog.virtual_key_id == key_id)

    query = query.group_by(func.date(RequestLog.created_at)).order_by(func.date(RequestLog.created_at))
    result = await db.execute(query)

    return [
        {
            "date": row.date.isoformat() if row.date else None,
            "requests": int(row.requests),
            "cost_usd": float(row.cost_usd or 0.0)
        }
        for row in result.all()
    ]

import asyncio
import re
import httpx
from fastapi import APIRouter, Depends, HTTPException
from core.dependencies import rate_limit_api
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from db.database import get_db
from db.models import User
from db import crud

router = APIRouter(dependencies=[Depends(rate_limit_api)])

PROVIDER_CHECK_TIMEOUT = 10.0


async def verify_provider(
    model: str,
    api_key: str,
    base_url: str,
    tier_label: str,
) -> str | None:
    """Check that a model exists by listing models from the provider.

    Returns ``None`` on success, or an error message string on failure.
    """
    headers = {"Authorization": f"Bearer {api_key}"}
    url = base_url.rstrip("/") + "/models"

    try:
        async with httpx.AsyncClient(timeout=PROVIDER_CHECK_TIMEOUT) as client:
            resp = await client.get(url, headers=headers)
    except httpx.TimeoutException:
        return f"{tier_label}: Connection timed out — check the base URL"
    except httpx.RequestError as e:
        return f"{tier_label}: Cannot reach provider — {e}"

    if resp.status_code == 401:
        return f"{tier_label}: Invalid API key (401 Unauthorized)"
    if resp.status_code == 404:
        return f"{tier_label}: Endpoint not found (404) — check the base URL"
    if resp.status_code >= 500:
        return f"{tier_label}: Provider error ({resp.status_code})"

    if resp.status_code != 200:
        return f"{tier_label}: Unexpected response ({resp.status_code})"

    data = resp.json()
    model_ids = {
        m["id"]
        for m in data.get("data", [])
        if isinstance(m, dict) and "id" in m
    }

    if model not in model_ids:
        return f"{tier_label}: Model '{model}' not found. Available: {', '.join(sorted(model_ids)[:10])}{'...' if len(model_ids) > 10 else ''}"

    return None  # success

class KeyCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    weak_model: str = Field(min_length=1)
    weak_api_key: str = Field(min_length=1)
    weak_base_url: str = Field(min_length=1)
    mid_model: str = Field(min_length=1)
    mid_api_key: str = Field(min_length=1)
    mid_base_url: str = Field(min_length=1)
    strong_model: str = Field(min_length=1)
    strong_api_key: str = Field(min_length=1)
    strong_base_url: str = Field(min_length=1)

class KeyCreateResponse(BaseModel):
    key: str
    key_id: str
    name: str

class KeyRevokeRequest(BaseModel):
    key_id: str

class NvidiaModelsRequest(BaseModel):
    api_key: str = Field(min_length=1)
    base_url: str = Field(min_length=1)

class NvidiaModelsResponse(BaseModel):
    models: list[str]

@router.post("/nvidia/models", response_model=NvidiaModelsResponse)
async def list_nvidia_models(
    payload: NvidiaModelsRequest,
    _current_user: User = Depends(get_current_user),
):
    headers = {"Authorization": f"Bearer {payload.api_key}"}
    url = payload.base_url.rstrip("/") + "/models"

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"NVIDIA API error: {e.response.text}",
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=502,
                detail=f"Failed to reach NVIDIA endpoint: {e}",
            )

    data = resp.json()

    def is_valid_model(m: dict) -> bool:
        if not isinstance(m, dict) or "id" not in m:
            return False
        obj = m.get("object")
        if obj is not None:
            return obj == "model"
        return not bool(re.fullmatch(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
            m["id"],
        ))

    models = sorted(
        m["id"] for m in data.get("data", []) if is_valid_model(m)
    )
    if not models:
        raise HTTPException(
            status_code=502,
            detail="No models returned from NVIDIA endpoint. Check your base URL and API key.",
        )
    return NvidiaModelsResponse(models=models)

@router.post("/create", response_model=KeyCreateResponse)
async def create_key(
    payload: KeyCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # --- Validate all three providers before creating the key ---
    checks = await asyncio.gather(
        verify_provider(payload.weak_model, payload.weak_api_key, payload.weak_base_url, "Weak tier"),
        verify_provider(payload.mid_model, payload.mid_api_key, payload.mid_base_url, "Mid tier"),
        verify_provider(payload.strong_model, payload.strong_api_key, payload.strong_base_url, "Strong tier"),
    )

    errors = [e for e in checks if e is not None]
    if errors:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "One or more providers are unreachable. Key not created.",
                "errors": errors,
            },
        )

    key_obj, raw_key = await crud.create_virtual_key(
        db,
        user_id=current_user.id,
        name=payload.name,
        weak_model=payload.weak_model,
        weak_api_key=payload.weak_api_key,
        weak_base_url=payload.weak_base_url,
        mid_model=payload.mid_model,
        mid_api_key=payload.mid_api_key,
        mid_base_url=payload.mid_base_url,
        strong_model=payload.strong_model,
        strong_api_key=payload.strong_api_key,
        strong_base_url=payload.strong_base_url,
    )

    return {
        "key": raw_key,
        "key_id": str(key_obj.id),
        "name": key_obj.name
    }

@router.get("/list")
async def list_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    keys = await crud.list_keys(db, user_id=current_user.id)
    return [
        {
            "key_id": str(k.id),
            "name": k.name,
            "weak_model": k.weak_model,
            "mid_model": k.mid_model,
            "strong_model": k.strong_model,
            "is_active": k.is_active,
            "created_at": k.created_at,
            "last_used_at": k.last_used_at
        }
        for k in keys
    ]

@router.post("/revoke")
async def revoke_key(
    payload: KeyRevokeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    success = await crud.revoke_key(db, key_id=payload.key_id, user_id=current_user.id)
    return {"success": success}

@router.delete("/{key_id}")
async def delete_key(
    key_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    success = await crud.delete_key(db, key_id=key_id, user_id=current_user.id)
    return {"success": success}

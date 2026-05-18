from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from auth.password import hash_password
from core.dependencies import rate_limit_api, require_admin
from db.database import get_db
from db.models import User
from db import crud

router = APIRouter(dependencies=[Depends(rate_limit_api)])


class UpdateProfileRequest(BaseModel):
    username: str | None = Field(None, min_length=1)
    email: EmailStr | None = None
    password: str | None = Field(None, min_length=8)


class UserPublic(BaseModel):
    id: str
    email: str
    username: str
    created_at: str | None = None


@router.get("/", response_model=list[UserPublic])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    users = await crud.list_users(db, skip=skip, limit=limit)
    return [
        {
            "id": str(u.id),
            "email": u.email,
            "username": u.username,
            "created_at": str(u.created_at) if u.created_at else None,
        }
        for u in users
    ]


@router.get("/me", response_model=UserPublic)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "username": current_user.username,
        "created_at": str(current_user.created_at) if current_user.created_at else None,
    }


@router.get("/{user_id}", response_model=UserPublic)
async def get_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if str(current_user.id) != user_id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this user",
        )
    user = await crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": str(user.id),
        "email": user.email,
        "username": user.username,
        "created_at": str(user.created_at) if user.created_at else None,
    }


@router.put("/me", response_model=UserPublic)
async def update_me(
    payload: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    pw_hash = hash_password(payload.password) if payload.password else None
    user = await crud.update_user(
        db,
        user_id=str(current_user.id),
        username=payload.username,
        email=payload.email if payload.email else None,
        password_hash=pw_hash,
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": str(user.id),
        "email": user.email,
        "username": user.username,
        "created_at": str(user.created_at) if user.created_at else None,
    }


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await crud.delete_user_by_id(db, str(current_user.id))


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if str(current_user.id) != user_id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this user",
        )
    success = await crud.delete_user_by_id(db, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    return {"success": True}

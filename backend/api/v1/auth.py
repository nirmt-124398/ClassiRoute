from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from auth.jwt_handler import create_token
from auth.password import hash_password, verify_password
from core.dependencies import rate_limit_auth
from auth.dependencies import get_current_user
from db.database import get_db
from db.models import User
from db import crud

router = APIRouter()

class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=1)
    password: str = Field(min_length=8)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class UserPublic(BaseModel):
    id: str
    email: EmailStr
    username: str

class AuthResponse(BaseModel):
    token: str
    user: UserPublic

@router.post("/register", response_model=AuthResponse)
async def register(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(rate_limit_auth),
):
    existing = await crud.get_user_by_email(db, payload.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    new_user = await crud.create_user(
        db,
        email=payload.email,
        username=payload.username,
        password_hash=hash_password(payload.password)
    )
    token = create_token(str(new_user.id))

    return {
        "token": token,
        "user": {
            "id": str(new_user.id),
            "email": new_user.email,
            "username": new_user.username
        }
    }

@router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(rate_limit_auth),
):
    user = await crud.get_user_by_email(db, payload.email)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = create_token(str(user.id))
    return {
        "token": token,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "username": user.username
        }
    }

@router.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "username": current_user.username,
        "created_at": current_user.created_at
    }

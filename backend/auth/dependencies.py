from fastapi import Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from db.database import get_db
from db.crud import get_user_by_id, get_key_by_hash, hash_key
from auth.jwt_handler import decode_token
from db.models import User, VirtualKey

async def get_current_user(
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Extracts the Bearer token natively from the Authorization header,
    validates the JWT, and returns the User object.
    Used for web frontend routes (/keys/*, /analytics/*, /auth/me)
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format. Expected 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = authorization.split(" ")[1]
    payload = decode_token(token)
    user_id = payload.get("sub")
    
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
        
    user = await get_user_by_id(db, str(user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
        
    return user

async def get_virtual_key(
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db)
) -> VirtualKey:
    """
    Validates API requests using the lmr-xxx format.
    Used ONLY for the /v1/chat/completions route.
    """
    if not authorization.startswith("Bearer lmr-"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key format. Expected 'Bearer lmr-...'",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    token = authorization.split(" ")[1]
    hashed = hash_key(token)
    
    vkey = await get_key_by_hash(db, key_hash=hashed)
    if vkey is None or not vkey.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive virtual key"
        )
        
    return vkey

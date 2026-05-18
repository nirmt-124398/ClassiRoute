import os
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from cryptography.fernet import Fernet
from db.models import User, VirtualKey, RequestLog

def get_fernet() -> Fernet:
    encryption_key = os.getenv("ENCRYPTION_KEY")
    if not encryption_key:
        raise RuntimeError("ENCRYPTION_KEY is not set")
    return Fernet(encryption_key.encode())

def encrypt(val: str) -> str:
    return get_fernet().encrypt(val.encode()).decode()

def decrypt(val: str) -> str:
    return get_fernet().decrypt(val.encode()).decode()

def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()

async def create_user(db: AsyncSession, email: str, username: str, password_hash: str) -> User:
    new_user = User(email=email, username=username, password_hash=password_hash)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user

async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalars().first()

async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalars().first()

async def create_virtual_key(
    db: AsyncSession,
    user_id: str,
    name: str,
    weak_model: str, weak_api_key: str, weak_base_url: str,
    mid_model: str, mid_api_key: str, mid_base_url: str,
    strong_model: str, strong_api_key: str, strong_base_url: str,
) -> tuple[VirtualKey, str]:
    raw_key = f"lmr-{secrets.token_hex(32)}"
    hashed_key = hash_key(raw_key)

    new_key = VirtualKey(
        user_id=user_id,
        name=name,
        key_hash=hashed_key,
        weak_model=weak_model,
        weak_api_key=encrypt(weak_api_key),
        weak_base_url=weak_base_url,
        mid_model=mid_model,
        mid_api_key=encrypt(mid_api_key),
        mid_base_url=mid_base_url,
        strong_model=strong_model,
        strong_api_key=encrypt(strong_api_key),
        strong_base_url=strong_base_url,
    )
    db.add(new_key)
    await db.commit()
    await db.refresh(new_key)
    return new_key, raw_key

async def get_key_by_hash(db: AsyncSession, key_hash: str) -> VirtualKey | None:
    result = await db.execute(select(VirtualKey).where(VirtualKey.key_hash == key_hash))
    return result.scalars().first()

async def list_keys(db: AsyncSession, user_id: str) -> list[VirtualKey]:
    result = await db.execute(select(VirtualKey).where(VirtualKey.user_id == user_id))
    return list(result.scalars().all())

async def revoke_key(db: AsyncSession, key_id: str, user_id: str) -> bool:
    result = await db.execute(select(VirtualKey).where(VirtualKey.id == key_id, VirtualKey.user_id == user_id))
    key = result.scalars().first()
    if key:
        key.is_active = False
        await db.commit()
        return True
    return False

async def delete_key(db: AsyncSession, key_id: str, user_id: str) -> bool:
    result = await db.execute(select(VirtualKey).where(VirtualKey.id == key_id, VirtualKey.user_id == user_id))
    key = result.scalars().first()
    if key:
        await db.delete(key)
        await db.commit()
        return True
    return False

async def touch_key(db: AsyncSession, key_id: str) -> None:
    result = await db.execute(select(VirtualKey).where(VirtualKey.id == key_id))
    key = result.scalars().first()
    if key:
        key.last_used_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await db.commit()

async def log_request(db: AsyncSession, **fields) -> RequestLog:
    log_entry = RequestLog(**fields)
    db.add(log_entry)
    await db.commit()
    await db.refresh(log_entry)
    return log_entry

async def get_stats(db: AsyncSession, user_id: str, key_id: str = None, days: int = 30) -> dict:
    cutoff = datetime.utcnow() - timedelta(days=days)
    query = select(RequestLog).where(
        RequestLog.user_id == user_id,
        RequestLog.created_at >= cutoff
    )
    if key_id:
        query = query.where(RequestLog.virtual_key_id == key_id)
        
    # We can do this in python or pure SQL. Using python for simplicity since this is a college project
    result = await db.execute(query)
    logs = list(result.scalars().all())
    
    total_requests = len(logs)
    by_tier = {0: 0, 1: 0, 2: 0}
    total_cost_usd = 0.0
    total_latency = 0
    success_count = 0
    
    requests_by_day_map = {}

    for log in logs:
        by_tier[log.tier_assigned] = by_tier.get(log.tier_assigned, 0) + 1
        if log.cost_estimate_usd:
            total_cost_usd += log.cost_estimate_usd
        total_latency += log.latency_ms
        if log.status == "success":
            success_count += 1

        if log.created_at:
            day = log.created_at.date().isoformat()
            requests_by_day_map[day] = requests_by_day_map.get(day, 0) + 1
            
    avg_latency_ms = (total_latency / total_requests) if total_requests > 0 else 0
    success_rate = (success_count / total_requests) if total_requests > 0 else 0

    # Mocking cost saved — assumes all requests were routed to tier 2 for worst-case cost
    # Usually requires knowing tier 2 price per token
    cost_saved = total_cost_usd * 2.5 # Mock factor as requested by simple analysis

    requests_by_day = [
        {"date": day, "count": count}
        for day, count in sorted(requests_by_day_map.items())
    ]

    return {
        "total_requests": total_requests,
        "by_tier": by_tier,
        "total_cost_usd": round(total_cost_usd, 6),
        "cost_saved_vs_always_strong": round(cost_saved, 6),
        "avg_latency_ms": round(avg_latency_ms, 2),
        "success_rate": round(success_rate, 4),
        "requests_by_day": requests_by_day
    }

async def get_request_logs(db: AsyncSession, user_id: str, key_id: str = None, limit: int = 50, offset: int = 0) -> list[RequestLog]:
    query = select(RequestLog).where(RequestLog.user_id == user_id)
    if key_id:
        query = query.where(RequestLog.virtual_key_id == key_id)
    
    query = query.order_by(RequestLog.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return list(result.scalars().all())


async def list_users(db: AsyncSession, skip: int = 0, limit: int = 100) -> list[User]:
    result = await db.execute(select(User).offset(skip).limit(limit))
    return list(result.scalars().all())


async def update_user(
    db: AsyncSession,
    user_id: str,
    username: str | None = None,
    email: str | None = None,
    password_hash: str | None = None,
) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        return None
    if username is not None:
        user.username = username
    if email is not None:
        user.email = email
    if password_hash is not None:
        user.password_hash = password_hash
    await db.commit()
    await db.refresh(user)
    return user


async def delete_user_by_id(db: AsyncSession, user_id: str) -> bool:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        return False
    await db.delete(user)
    await db.commit()
    return True

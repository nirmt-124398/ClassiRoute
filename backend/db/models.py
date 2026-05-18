import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, Integer, Float, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from db.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    username = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=func.now())

class VirtualKey(Base):
    __tablename__ = "virtual_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    key_hash = Column(String, unique=True, nullable=False, index=True)
    
    weak_model = Column(String, nullable=False)
    weak_api_key = Column(String, nullable=False)
    weak_base_url = Column(String, nullable=False)
    
    mid_model = Column(String, nullable=False)
    mid_api_key = Column(String, nullable=False)
    mid_base_url = Column(String, nullable=False)
    
    strong_model = Column(String, nullable=False)
    strong_api_key = Column(String, nullable=False)
    strong_base_url = Column(String, nullable=False)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    last_used_at = Column(DateTime, nullable=True)

class RequestLog(Base):
    __tablename__ = "request_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    virtual_key_id = Column(UUID(as_uuid=True), ForeignKey("virtual_keys.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    prompt_preview = Column(String(length=200), nullable=True)
    prompt_length = Column(Integer, nullable=False)
    tier_assigned = Column(Integer, nullable=False)
    confidence = Column(Float, nullable=False)
    model_used = Column(String, nullable=False)
    
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    latency_ms = Column(Integer, nullable=False)
    cost_estimate_usd = Column(Float, nullable=True)
    
    status = Column(String, nullable=False)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())

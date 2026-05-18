"""initial

Revision ID: 3c35c834e2cd
Revises:
Create Date: 2026-05-12 10:59:31.472172

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "3c35c834e2cd"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(), nullable=False, unique=True, index=True),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "virtual_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("key_hash", sa.String(), nullable=False, unique=True, index=True),
        sa.Column("weak_model", sa.String(), nullable=False),
        sa.Column("weak_api_key", sa.String(), nullable=False),
        sa.Column("weak_base_url", sa.String(), nullable=False),
        sa.Column("mid_model", sa.String(), nullable=False),
        sa.Column("mid_api_key", sa.String(), nullable=False),
        sa.Column("mid_base_url", sa.String(), nullable=False),
        sa.Column("strong_model", sa.String(), nullable=False),
        sa.Column("strong_api_key", sa.String(), nullable=False),
        sa.Column("strong_base_url", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "request_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("virtual_key_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("virtual_keys.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("prompt_preview", sa.String(200), nullable=True),
        sa.Column("prompt_length", sa.Integer(), nullable=False),
        sa.Column("tier_assigned", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("model_used", sa.String(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("cost_estimate_usd", sa.Float(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("request_logs")
    op.drop_table("virtual_keys")
    op.drop_table("users")

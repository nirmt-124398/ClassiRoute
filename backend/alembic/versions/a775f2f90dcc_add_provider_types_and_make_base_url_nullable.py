"""add provider_type columns, make base_url nullable

Revision ID: a775f2f90dcc
Revises: 74edb51eb20e
Create Date: 2026-05-20 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a775f2f90dcc"
down_revision: Union[str, Sequence[str], None] = "74edb51eb20e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add provider_type columns with default 'openai'
    op.add_column("virtual_keys", sa.Column("weak_provider_type", sa.String(20), nullable=False, server_default="openai"))
    op.add_column("virtual_keys", sa.Column("mid_provider_type", sa.String(20), nullable=False, server_default="openai"))
    op.add_column("virtual_keys", sa.Column("strong_provider_type", sa.String(20), nullable=False, server_default="openai"))

    # Make base_url columns nullable
    op.alter_column("virtual_keys", "weak_base_url", nullable=True, existing_type=sa.String())
    op.alter_column("virtual_keys", "mid_base_url", nullable=True, existing_type=sa.String())
    op.alter_column("virtual_keys", "strong_base_url", nullable=True, existing_type=sa.String())


def downgrade() -> None:
    # Reverse: make base_url columns not nullable again
    op.alter_column("virtual_keys", "strong_base_url", nullable=False, existing_type=sa.String())
    op.alter_column("virtual_keys", "mid_base_url", nullable=False, existing_type=sa.String())
    op.alter_column("virtual_keys", "weak_base_url", nullable=False, existing_type=sa.String())

    # Drop provider_type columns
    op.drop_column("virtual_keys", "strong_provider_type")
    op.drop_column("virtual_keys", "mid_provider_type")
    op.drop_column("virtual_keys", "weak_provider_type")

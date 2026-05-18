"""add key_raw_encrypted to virtualkey (stub — column managed in code)

Revision ID: 74edb51eb20e
Revises: 3c35c834e2cd
Create Date: 2026-05-14 10:00:00.000000

"""

from typing import Sequence, Union
from alembic import op


revision: str = "74edb51eb20e"
down_revision: Union[str, Sequence[str], None] = "3c35c834e2cd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

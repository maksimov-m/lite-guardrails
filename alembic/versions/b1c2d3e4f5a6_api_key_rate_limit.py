"""api key rate limit

Revision ID: b1c2d3e4f5a6
Revises: 4439aefb1b55
Create Date: 2026-07-02 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, None] = '4439aefb1b55'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'api_keys',
        sa.Column('rate_limit_per_min', sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('api_keys', 'rate_limit_per_min')

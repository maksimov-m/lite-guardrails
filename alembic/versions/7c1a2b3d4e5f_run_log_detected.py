"""run_logs.detected column + composite index for dashboard stats

Добавляет булев столбец `detected` (гуард сработал), считаемый на записи, и
составной индекс (module, created_at). Дашборд/метрики перестают парсить
output::jsonb построчно — агрегация идёт по столбцу.

Revision ID: 7c1a2b3d4e5f
Revises: 4439aefb1b55
Create Date: 2026-07-03 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "7c1a2b3d4e5f"
down_revision: Union[str, None] = "4439aefb1b55"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "run_logs",
        sa.Column("detected", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    # Одноразовый бэкфилл уже накопленных строк по прежней JSON-логике,
    # чтобы дашборд остался корректным на исторических данных.
    op.execute(
        """
        UPDATE run_logs SET detected = CASE
            WHEN module = 'relevant'
                THEN ((output::jsonb) ->> 'RELEVANT')::boolean IS FALSE
            ELSE ((output::jsonb) ->> (upper(module) || '_DETECT'))::boolean IS TRUE
        END
        """
    )
    op.create_index("ix_run_logs_module_created", "run_logs", ["module", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_run_logs_module_created", table_name="run_logs")
    op.drop_column("run_logs", "detected")

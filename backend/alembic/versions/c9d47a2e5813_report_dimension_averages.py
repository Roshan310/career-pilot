"""store per-dimension averages on the session report

Revision ID: c9d47a2e5813
Revises: b8e35f1c07a4
Create Date: 2026-08-07 11:15:00.000000

The per-dimension trend across sessions ("specificity 2.3 -> 3.8") is the
strongest argument for practising again, and it cannot be reconstructed from the
stored findings: those only carry a dimension when it happened to qualify as a
strength or a weakness, so a flat 3.0/3.0/3.0 session left no trace at all.

Nullable with no backfill on purpose. Re-deriving it for old reports means
re-reading every turn of every session, and `app/scripts/backfill_report_findings.py`
already exists for exactly that kind of pass if it's ever wanted. Reports written
before this simply don't appear on the trend, which is honest — the alternative
is inventing numbers for them.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c9d47a2e5813'
down_revision: Union[str, None] = 'b8e35f1c07a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "session_reports",
        sa.Column("dimension_averages", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("session_reports", "dimension_averages")

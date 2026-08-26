"""add session_reports.speech_metrics

Revision ID: f3ba845e1e22
Revises: c3356bc413f0
Create Date: 2026-07-31 06:10:44.670958

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f3ba845e1e22'
down_revision: Union[str, None] = 'c3356bc413f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Hand-edited after autogeneration (see AGENT.md): Alembic also emitted
# drop_index for idx_jobs_embedding / idx_resumes_embedding, because it can't
# introspect the raw `USING ivfflat (... vector_cosine_ops)` indexes the initial
# migration created with op.execute(). Those drops were removed — they are a
# false diff, not an intended schema change. The only real change here is the
# additive nullable column.


def upgrade() -> None:
    op.add_column('session_reports', sa.Column('speech_metrics', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column('session_reports', 'speech_metrics')

"""replay a past interview over its stored question plan

Revision ID: d1a58f3c92b7
Revises: c9d47a2e5813
Create Date: 2026-08-07 15:40:00.000000

Two columns, both on interview_sessions.

`replay_of_session_id` points at the *root* attempt rather than the immediately
preceding one, so every attempt of one interview shares a single parent and
"attempt N of M" is a grouping instead of a recursive walk. ON DELETE SET NULL
matches the resume/job/match FKs on this table: deleting the original attempt
must orphan its replays, never delete them.

`allow_follow_ups` is the per-replay choice between the full adaptive interview
and main questions only. `server_default=true` backfills every existing row to
today's behaviour, so there is no data migration and no window in which a
running session has an undefined rule.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd1a58f3c92b7'
down_revision: Union[str, None] = 'c9d47a2e5813'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "interview_sessions",
        sa.Column("replay_of_session_id", sa.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_interview_sessions_replay_of_session_id",
        "interview_sessions",
        "interview_sessions",
        ["replay_of_session_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # Every attempt-numbering query filters on this column.
    op.create_index(
        "ix_interview_sessions_replay_of_session_id",
        "interview_sessions",
        ["replay_of_session_id"],
    )
    op.add_column(
        "interview_sessions",
        sa.Column(
            "allow_follow_ups",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_column("interview_sessions", "allow_follow_ups")
    op.drop_index("ix_interview_sessions_replay_of_session_id", table_name="interview_sessions")
    op.drop_constraint(
        "fk_interview_sessions_replay_of_session_id", "interview_sessions", type_="foreignkey"
    )
    op.drop_column("interview_sessions", "replay_of_session_id")

"""Re-derive the Strengths / Areas to Improve columns for reports written before
report_findings.py existed.

    docker compose exec api python -m app.scripts.backfill_report_findings --dry-run
    docker compose exec api python -m app.scripts.backfill_report_findings

Makes **no API calls** — findings are computed from turns already in the database.
Safe to re-run: it skips reports that already carry findings unless --force.

Why a script and not an alembic migration:

* `alembic/` is gitignored in this repo, so a data migration would be untracked —
  it would never reach a fresh clone and its existence would be unversioned.
* The container runs `alembic upgrade head` on startup. A data migration that
  trips over one malformed legacy row would block every API boot, not just the
  backfill.
* Alembic's guarantee is "runs exactly once", which is the wrong guarantee here:
  these thresholds will be tuned, so this needs to be re-runnable and dry-runnable.
* `downgrade()` would be a lie — the previous JSONB is overwritten and gone.
"""

import argparse
import asyncio

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.interview import SessionReport
from app.services.interview_service import get_turns
from app.services.report_findings import build_findings

BATCH_SIZE = 50


def _already_backfilled(report: SessionReport) -> bool:
    """New-shape findings carry a `code`; the old shape had turn_number/question_text.

    An empty column counts as not-backfilled, which is harmless: `build_findings`
    always emits at least one improvement (`no_scored_answers` in the worst case),
    so a second run will correctly see the row as done.
    """
    items = (report.strengths or []) + (report.improvement_areas or [])
    return any(isinstance(item, dict) and "code" in item for item in items)


async def main(dry_run: bool, force: bool) -> None:
    scanned = updated = skipped = 0

    async with AsyncSessionLocal() as db:
        reports = (
            (await db.execute(select(SessionReport).order_by(SessionReport.created_at)))
            .scalars()
            .all()
        )

        for report in reports:
            scanned += 1

            if _already_backfilled(report) and not force:
                skipped += 1
                continue

            turns = await get_turns(db, report.session_id)
            findings = build_findings(turns)

            # ONLY these two columns. Deliberately not `aggregate_report`, which
            # also recomputes `gap_coverage` from the session's match — and
            # `interview_sessions.match_id` is ON DELETE SET NULL, so for any
            # session whose match was since deleted that would silently replace
            # correct stored gap coverage with an empty one.
            report.strengths = findings["strengths"]
            report.improvement_areas = findings["improvement_areas"]
            updated += 1

            print(
                f"  session {report.session_id}: "
                f"{len(findings['strengths'])} strengths "
                f"[{', '.join(f['code'] for f in findings['strengths']) or '-'}], "
                f"{len(findings['improvement_areas'])} improvements "
                f"[{', '.join(f['code'] for f in findings['improvement_areas'])}]"
            )

            if not dry_run and updated % BATCH_SIZE == 0:
                await db.commit()

        if dry_run:
            await db.rollback()
        else:
            await db.commit()

    verb = "would update" if dry_run else "updated"
    print(f"\nscanned {scanned}, {verb} {updated}, skipped {skipped} (already backfilled)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="report what would change, write nothing")
    parser.add_argument("--force", action="store_true", help="rewrite reports that already have findings")
    args = parser.parse_args()

    asyncio.run(main(dry_run=args.dry_run, force=args.force))

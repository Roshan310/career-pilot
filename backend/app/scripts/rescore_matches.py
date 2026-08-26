"""Recompute stored match scores with the current algorithm.

Why this exists
---------------
The scoring arithmetic changed: experience is measured in months rather than
calendar years, skill matching is token-based with an alias table, and the
evidence pool includes experience bullets and projects rather than the skills
list alone. Existing rows were scored under the old rules, so old and new
numbers do not mean the same thing — and the interview/match trend charts would
render that discontinuity as though the *candidate* had suddenly improved.

Why a script and not a migration
--------------------------------
Same reasoning as `backfill_report_findings.py`: `alembic upgrade head` is the
api container's start command, so a data pass that throws would stop the API
booting. The thresholds here will also be tuned, which means this needs to be
re-runnable rather than a one-shot revision.

**Makes no LLM or embedding calls.** Everything it needs — parsed resume data,
parsed requirements, both embeddings, the raw text — is already stored. Only the
arithmetic is recomputed, so this is free to run as often as you like.

Usage:
    docker compose exec api python -m app.scripts.rescore_matches --dry-run
    docker compose exec api python -m app.scripts.rescore_matches
"""

import argparse
import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.job_description import JobDescription
from app.models.match import Match
from app.models.resume import Resume
from app.schemas.job import ParsedJobRequirements
from app.schemas.resume import ParsedResumeData
from app.services.matching_service import compute_scores

logger = logging.getLogger(__name__)

BATCH_SIZE = 50

# Only these carry scores worth recomputing. A pending or failed match has no
# numbers, and a stuck one is the reaper's business.
RESCORABLE_STATUSES = ("done",)


async def rescore(db: AsyncSession, *, dry_run: bool) -> tuple[int, int]:
    """Returns (rescored, skipped)."""
    rows = (
        await db.execute(
            # One join rather than a query per match: the previous backfill
            # script's N+1 read loop is a mistake worth not repeating.
            select(Match, Resume, JobDescription)
            .join(Resume, Match.resume_id == Resume.id)
            .join(JobDescription, Match.job_id == JobDescription.id)
            .where(Match.status.in_(RESCORABLE_STATUSES))
            .order_by(Match.created_at)
        )
    ).all()

    rescored = skipped = 0

    for match, resume, job in rows:
        if resume.embedding is None or job.embedding is None:
            # Predates embeddings, or a half-failed upload. Semantic score is
            # not reconstructible without an API call, so leave the row alone
            # rather than silently scoring it as zero.
            logger.warning("Match %s has no embedding on one side; skipping", match.id)
            skipped += 1
            continue

        try:
            scores = compute_scores(
                ParsedResumeData.model_validate(resume.parsed_data),
                ParsedJobRequirements.model_validate(job.parsed_requirements),
                resume.raw_text,
                list(resume.embedding),
                list(job.embedding),
            )
        except Exception:
            # One malformed legacy row must not abort the whole pass.
            logger.warning("Match %s could not be rescored", match.id, exc_info=True)
            skipped += 1
            continue

        before = match.overall_score
        if dry_run:
            logger.info(
                "%s  %.3f -> %.3f  (exp %.2f->%.2f, skills %.2f->%.2f, kw %.2f->%.2f)",
                match.id,
                before or 0.0,
                scores["overall_score"],
                match.experience_match_score or 0.0,
                scores["experience_match_score"],
                match.skill_overlap_score or 0.0,
                scores["skill_overlap_score"],
                match.keyword_density_score or 0.0,
                scores["keyword_density_score"],
            )
        else:
            for field, value in scores.items():
                setattr(match, field, value)

        rescored += 1
        if not dry_run and rescored % BATCH_SIZE == 0:
            await db.commit()

    if not dry_run:
        await db.commit()
    else:
        await db.rollback()

    return rescored, skipped


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="report what would change, write nothing"
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s", force=True)

    async with AsyncSessionLocal() as db:
        rescored, skipped = await rescore(db, dry_run=args.dry_run)

    verb = "would rescore" if args.dry_run else "rescored"
    logger.info("%s %d match(es), skipped %d", verb, rescored, skipped)


if __name__ == "__main__":
    asyncio.run(main())

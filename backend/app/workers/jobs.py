import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.job_description import JobDescription
from app.models.match import Match
from app.models.resume import Resume
from app.schemas.job import ParsedJobRequirements
from app.schemas.resume import ParsedResumeData
from app.services.llm.suggestions import generate_suggestions
from app.services.matching_service import compute_scores


async def compute_match(db: AsyncSession, match_id: uuid.UUID) -> None:
    match = (await db.execute(select(Match).where(Match.id == match_id))).scalar_one_or_none()
    if match is None:
        return  # nothing to do — match row was deleted before the job ran

    match.status = "processing"
    await db.commit()

    resume = (await db.execute(select(Resume).where(Resume.id == match.resume_id))).scalar_one_or_none()
    job = (
        await db.execute(select(JobDescription).where(JobDescription.id == match.job_id))
    ).scalar_one_or_none()

    if resume is None or job is None or resume.embedding is None or job.embedding is None:
        match.status = "failed"
        match.error_message = "Resume or job description is missing required data (embedding)"
        await db.commit()
        return

    try:
        parsed_resume = ParsedResumeData.model_validate(resume.parsed_data)
        parsed_job = ParsedJobRequirements.model_validate(job.parsed_requirements)
        scores = compute_scores(
            parsed_resume, parsed_job, resume.raw_text, list(resume.embedding), list(job.embedding)
        )
    except Exception as exc:
        # scoring itself failing IS fatal (SPECS.md §9 distinguishes this from
        # suggestion generation, which degrades gracefully instead) — there's no
        # meaningful partial result to persist without at least the sub-scores.
        match.status = "failed"
        match.error_message = f"Scoring failed: {exc}"
        await db.commit()
        return

    for field, value in scores.items():
        setattr(match, field, value)

    try:
        match.suggestions = generate_suggestions(parsed_resume, scores["missing_skills"])
    except Exception:
        # §9: "skip scoring detail rather than failing the whole [match]" — the
        # score breakdown just computed above is still valid and worth keeping.
        match.suggestions = []

    match.status = "done"
    await db.commit()


def run_matching_job(match_id: str) -> None:
    """RQ entrypoint (sync) — RQ workers call plain functions, so this wraps
    the async DB/LLM work. Also called directly (not via Redis) by tests that
    want the job to run synchronously and deterministically."""
    asyncio.run(_run(uuid.UUID(match_id)))


async def _run(match_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as db:
        await compute_match(db, match_id)

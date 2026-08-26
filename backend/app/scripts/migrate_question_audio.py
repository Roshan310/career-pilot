"""Move cached question audio onto the content-addressed key scheme.

Why this exists
---------------
`services/tts.cache_key` used to be `interview-audio/{session_id}/{turn}.mp3`.
It is now a hash of the question text plus the voice configuration, so that a
*replay* of a past interview — the same questions, the same voice — hits the
cache instead of re-billing ElevenLabs per character.

Without this pass, every object already in the bucket is orphaned under the old
scheme and the first replay re-synthesizes the whole interview. That is exactly
the cost the replay feature exists to avoid, and it would be charged against
audio that has already been paid for once.

Why a script and not a migration
--------------------------------
Same reasoning as `rescore_matches.py`: `alembic upgrade head` is the api
container's start command, so an object-storage pass that throws would stop the
API booting. Object storage is also not the database's business.

**Makes no ElevenLabs or LLM calls.** It reads bytes that already exist and
writes them to a second key. Old objects are left in place, so this is safe to
re-run and safe to roll back — deleting them is a separate decision, taken once
you're satisfied replays are hitting the cache.

Usage:
    docker compose exec api python -m app.scripts.migrate_question_audio --dry-run
    docker compose exec api python -m app.scripts.migrate_question_audio
"""

import argparse
import asyncio
import logging

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.interview import InterviewTurn
from app.services import storage_service, tts

logger = logging.getLogger(__name__)


def legacy_cache_key(session_id, turn_number: int) -> str:
    """The scheme `tts.cache_key` used before content addressing. Kept here
    rather than left in tts.py, because nothing in the running app should be
    able to write this shape again."""
    return f"interview-audio/{session_id}/{turn_number}.mp3"


async def migrate(*, dry_run: bool) -> tuple[int, int, int]:
    """Returns (copied, already_present, missing)."""
    async with AsyncSessionLocal() as db:
        turns = list(
            (
                await db.execute(
                    select(InterviewTurn).order_by(
                        InterviewTurn.session_id, InterviewTurn.turn_number
                    )
                )
            )
            .scalars()
            .all()
        )

    copied = already_present = missing = 0
    # Two turns asking the same question map to one object — that dedup is the
    # point of content addressing, so track what this run has written to avoid
    # re-reading bytes we just stored.
    written: set[str] = set()

    for turn in turns:
        new_key = tts.cache_key(turn.question_text)
        if new_key in written:
            already_present += 1
            continue

        if storage_service.get_bytes(new_key) is not None:
            already_present += 1
            written.add(new_key)
            continue

        audio = storage_service.get_bytes(legacy_cache_key(turn.session_id, turn.turn_number))
        if audio is None:
            # Never synthesized (the client fell back to browser speech), or
            # already pruned. Nothing to move, and nothing wrong.
            missing += 1
            continue

        if dry_run:
            logger.info("would copy session %s turn %s -> %s", turn.session_id, turn.turn_number, new_key)
        else:
            storage_service.upload_bytes(new_key, audio, tts.CONTENT_TYPE)
        copied += 1
        written.add(new_key)

    return copied, already_present, missing


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="report what would be copied, write nothing"
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s", force=True)

    copied, already_present, missing = await migrate(dry_run=args.dry_run)

    verb = "would copy" if args.dry_run else "copied"
    logger.info(
        "%s %d object(s); %d already in place, %d turn(s) had no cached audio",
        verb,
        copied,
        already_present,
        missing,
    )


if __name__ == "__main__":
    asyncio.run(main())

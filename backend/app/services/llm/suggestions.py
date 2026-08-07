"""Gap-aware resume rewrite suggestions (SPECS.md §6.3).

One suggestion per missing skill. The line being rewritten is chosen *per
skill* — see `pick_bullet_for_skill` for why that matters.
"""

from app.core.exceptions import LLMServiceError
from app.schemas.resume import ParsedResumeData
from app.services.llm.client import call_json
from app.services.llm.prompts import suggestion_prompt
from app.services.matching_service import MATCH_THRESHOLD, relevance

# Bounds the number of suggestion LLM calls per match — one call per missing
# skill would be unbounded for a JD with a long requirements list.
MAX_SUGGESTIONS = 5


def candidate_lines(resume: ParsedResumeData) -> list[tuple[str, str]]:
    """Every resume line that could plausibly be rewritten, each paired with a
    human-readable label saying where it came from.

    Ordered most-recent-experience first, then projects, then the summary as a
    last resort. `pick_bullet_for_skill` breaks ties toward the earlier entry,
    so this ordering is the tie-break rule.

    Projects are in here for the same reason `matching_service.resume_evidence`
    includes them: for an early-career candidate the projects section *is* the
    evidence, and a rewrite pool drawn only from employment history has nothing
    to work with.
    """
    lines: list[tuple[str, str]] = []

    for item in resume.experience:
        role = " at ".join(part for part in (item.title, item.company) if part)
        label = role or "Experience"
        lines.extend((bullet, label) for bullet in item.bullets if bullet.strip())

    for project in resume.projects:
        label = f"Project: {project.name}" if project.name else "Project"
        if project.description and project.description.strip():
            lines.append((project.description, label))
        lines.extend((bullet, label) for bullet in project.bullets if bullet.strip())

    if resume.summary and resume.summary.strip():
        lines.append((resume.summary, "Summary"))

    return lines


def pick_bullet_for_skill(
    resume: ParsedResumeData, skill: str
) -> tuple[str | None, str | None]:
    """The resume line most related to `skill`, as (text, source_label).

    Returns (None, None) when nothing clears `MATCH_THRESHOLD`.

    This used to pick `experience[0].bullets[0]` *once*, before the loop over
    missing skills — so every suggestion in a match rewrote the same arbitrary
    sentence, and the UI showed that one line as "your bullet today" on all of
    them. Worse than cosmetic: the model was being asked to bend one line toward
    a skill it might have nothing to do with, which is pressure toward exactly
    the fabrication the prompt forbids.
    """
    best_text: str | None = None
    best_label: str | None = None
    best_score = 0.0

    for text, label in candidate_lines(resume):
        # Strictly greater, so ties keep the earlier (more recent) entry.
        if (score := relevance(text, skill)) > best_score:
            best_score, best_text, best_label = score, text, label

    if best_score < MATCH_THRESHOLD:
        return None, None
    return best_text, best_label


def _honest_connection_context(resume: ParsedResumeData) -> str:
    """Everything the model may draw on when judging whether a connection is
    honest. Session-wide rather than per-skill: narrowing it to the chosen line
    would let the model claim no connection exists when the evidence is simply
    in a different section.

    Includes projects for that exact reason — a candidate's pgvector or JWT work
    usually lives in a project write-up, and omitting it produced confident
    "no honest connection" verdicts about experience the resume plainly showed.
    """
    parts: list[str] = [resume.summary or ""]
    for item in resume.experience:
        parts.extend(item.bullets)
    for project in resume.projects:
        parts.extend([project.name or "", project.description or "", *project.bullets])
        if project.technologies:
            parts.append(" ".join(project.technologies))
    return " ".join(part for part in parts if part).strip()


def generate_suggestions(resume: ParsedResumeData, missing_skills: list[dict]) -> list[dict]:
    """SPECS.md §6.3 gap-aware rewrite prompt, called once per missing skill
    (required skills first, capped at MAX_SUGGESTIONS). Any single failure is
    skipped (not fatal) — the caller treats this whole function's failure as
    the graceful-degradation boundary for the matching job."""
    required_first = sorted(missing_skills, key=lambda m: m["priority"] != "required")
    context = _honest_connection_context(resume)

    suggestions = []
    for gap in required_first[:MAX_SUGGESTIONS]:
        bullet_text, bullet_source = pick_bullet_for_skill(resume, gap["skill"])
        try:
            result = call_json(suggestion_prompt(bullet_text, gap["skill"], context))
        except LLMServiceError:
            continue
        if not isinstance(result, dict) or "suggestion" not in result:
            continue
        suggestions.append(
            {
                "missing_skill": gap["skill"],
                "priority": gap["priority"],
                # None when no line related to this skill. The UI renders that
                # case as advice rather than as a strikethrough "before".
                "original_bullet": bullet_text,
                "original_bullet_source": bullet_source,
                "suggestion": result.get("suggestion"),
                "has_honest_connection": result.get("has_honest_connection"),
            }
        )
    return suggestions

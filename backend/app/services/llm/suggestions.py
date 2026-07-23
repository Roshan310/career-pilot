from app.core.exceptions import LLMServiceError
from app.schemas.resume import ParsedResumeData
from app.services.llm.client import call_json
from app.services.llm.prompts import suggestion_prompt

# Bounds the number of suggestion LLM calls per match — one call per missing
# skill would be unbounded for a JD with a long requirements list.
MAX_SUGGESTIONS = 5


def _pick_bullet_and_context(resume: ParsedResumeData) -> tuple[str, str]:
    """Most recent experience entry's first bullet as the rewrite target;
    all bullets + summary as context for the LLM to judge an honest connection."""
    all_bullets = [b for exp in resume.experience for b in exp.bullets]
    context = " ".join([resume.summary or "", *all_bullets]).strip()

    if resume.experience and resume.experience[0].bullets:
        return resume.experience[0].bullets[0], context
    return (resume.summary or "No specific bullet on file."), context


def generate_suggestions(resume: ParsedResumeData, missing_skills: list[dict]) -> list[dict]:
    """SPECS.md §6.3 gap-aware rewrite prompt, called once per missing skill
    (required skills first, capped at MAX_SUGGESTIONS). Any single failure is
    skipped (not fatal) — the caller treats this whole function's failure as
    the graceful-degradation boundary for the matching job."""
    required_first = sorted(missing_skills, key=lambda m: m["priority"] != "required")
    bullet_text, context = _pick_bullet_and_context(resume)

    suggestions = []
    for gap in required_first[:MAX_SUGGESTIONS]:
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
                "original_bullet": bullet_text,
                "suggestion": result.get("suggestion"),
                "has_honest_connection": result.get("has_honest_connection"),
            }
        )
    return suggestions

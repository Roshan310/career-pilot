import math
import re

from app.schemas.job import ParsedJobRequirements
from app.schemas.resume import ParsedResumeData

# SPECS.md §6.2 gives these formulas qualitatively, not as exact algorithms
# ("weighted 2x", "capped scoring curve", "simple frequency check"). The
# concrete choices below fill that gap and are documented inline; sanity-check
# against real match output once Gemini calls are live.

WEIGHT_SEMANTIC = 0.40
WEIGHT_SKILL_OVERLAP = 0.35
WEIGHT_EXPERIENCE = 0.15
WEIGHT_KEYWORD_DENSITY = 0.10


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9+#. ]", "", text.lower()).strip()


def _skill_matches(required_skill_norm: str, candidate_skills_norm: set[str]) -> bool:
    # Exact or substring match on normalized strings. Deliberately NOT using an
    # embedding-similarity fallback for synonyms (e.g. "K8s" vs "Kubernetes") —
    # that would cost one extra embedding call per required/preferred skill per
    # match, which doesn't scale; exact/substring matching is the MVP tradeoff.
    return any(
        required_skill_norm in candidate_skill or candidate_skill in required_skill_norm
        for candidate_skill in candidate_skills_norm
    )


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def semantic_similarity_score(resume_embedding: list[float], job_embedding: list[float]) -> float:
    # cosine similarity is in [-1, 1]; clamp to [0, 1] since embeddings of two
    # unrelated-but-plausible texts rarely go meaningfully negative in practice.
    return max(0.0, min(1.0, cosine_similarity(resume_embedding, job_embedding)))


def skill_overlap(
    resume: ParsedResumeData, job: ParsedJobRequirements
) -> tuple[float, list[dict], list[dict]]:
    candidate_skills_norm = {_normalize(s) for s in resume.skills if s}

    matched: list[dict] = []
    missing: list[dict] = []

    for skill in job.required_skills:
        norm = _normalize(skill)
        if norm and _skill_matches(norm, candidate_skills_norm):
            matched.append({"skill": skill, "priority": "required"})
        else:
            missing.append({"skill": skill, "priority": "required"})

    for skill in job.preferred_skills:
        norm = _normalize(skill)
        if norm and _skill_matches(norm, candidate_skills_norm):
            matched.append({"skill": skill, "priority": "preferred"})
        else:
            missing.append({"skill": skill, "priority": "preferred"})

    required_count = len(job.required_skills)
    preferred_count = len(job.preferred_skills)
    denominator = 2 * required_count + preferred_count
    if denominator == 0:
        # nothing was asked for — nothing to be missing, vacuously a full match.
        return 1.0, matched, missing

    matched_required = sum(1 for m in matched if m["priority"] == "required")
    matched_preferred = sum(1 for m in matched if m["priority"] == "preferred")
    score = (2 * matched_required + matched_preferred) / denominator
    return score, matched, missing


_YEAR_RE = re.compile(r"(19|20)\d{2}")


def _extract_year(date_str: str | None, *, is_end_date: bool) -> int | None:
    if not date_str:
        return None
    if is_end_date and re.search(r"present|current|now", date_str, re.IGNORECASE):
        from datetime import UTC, datetime

        return datetime.now(UTC).year
    match = _YEAR_RE.search(date_str)
    return int(match.group()) if match else None


def candidate_years_of_experience(resume: ParsedResumeData) -> float:
    """Approximate total years from the earliest start_date to the latest
    end_date across all experience entries. This assumes continuous employment
    and ignores gaps/overlaps — a deliberate simplification, not a calendar
    reconstruction, given resume date formats are free text."""
    start_years = [
        y for e in resume.experience if (y := _extract_year(e.start_date, is_end_date=False)) is not None
    ]
    end_years = [
        y for e in resume.experience if (y := _extract_year(e.end_date, is_end_date=True)) is not None
    ]
    if not start_years or not end_years:
        return 0.0
    return max(0.0, float(max(end_years) - min(start_years)))


def experience_match_score(resume: ParsedResumeData, job: ParsedJobRequirements) -> float:
    required_years = job.years_experience_required
    if not required_years or required_years <= 0:
        return 1.0  # nothing to measure against

    candidate_years = candidate_years_of_experience(resume)
    if candidate_years >= required_years:
        return 1.0
    # capped scoring curve (§6.2): sub-linear ramp so being close to the bar
    # isn't harshly penalized, rather than a straight linear ratio.
    return max(0.0, min(1.0, math.sqrt(candidate_years / required_years)))


def keyword_density_score(resume_raw_text: str, job: ParsedJobRequirements) -> float:
    terms = {_normalize(s) for s in [*job.required_skills, *job.preferred_skills] if s}
    if not terms:
        return 1.0
    text_norm = _normalize(resume_raw_text)
    found = sum(1 for term in terms if term and term in text_norm)
    return found / len(terms)


def compute_scores(
    resume: ParsedResumeData,
    job: ParsedJobRequirements,
    resume_raw_text: str,
    resume_embedding: list[float],
    job_embedding: list[float],
) -> dict:
    semantic = semantic_similarity_score(resume_embedding, job_embedding)
    overlap, matched_skills, missing_skills = skill_overlap(resume, job)
    experience = experience_match_score(resume, job)
    keyword_density = keyword_density_score(resume_raw_text, job)

    overall = (
        WEIGHT_SEMANTIC * semantic
        + WEIGHT_SKILL_OVERLAP * overlap
        + WEIGHT_EXPERIENCE * experience
        + WEIGHT_KEYWORD_DENSITY * keyword_density
    )

    return {
        "overall_score": overall,
        "semantic_score": semantic,
        "skill_overlap_score": overlap,
        "experience_match_score": experience,
        "keyword_density_score": keyword_density,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
    }

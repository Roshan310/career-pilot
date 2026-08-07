import math
import re
from datetime import UTC, datetime

from app.schemas.job import ParsedJobRequirements
from app.schemas.resume import ParsedResumeData

# SPECS.md §6.2 gives these formulas qualitatively, not as exact algorithms
# ("weighted 2x", "capped scoring curve", "simple frequency check"). The
# concrete choices below fill that gap and are documented inline.

WEIGHT_SEMANTIC = 0.40
WEIGHT_SKILL_OVERLAP = 0.35
WEIGHT_EXPERIENCE = 0.15
WEIGHT_KEYWORD_DENSITY = 0.10


# ---------------------------------------------------------------------------
# Text normalization
# ---------------------------------------------------------------------------

# Separators become a space rather than nothing. Deleting them welded words
# together — "Authentication/authorization" normalized to the single token
# "authenticationauthorization" and "Git & GitHub" to "git  github", neither of
# which can ever match anything. `+ # .` survive so C++, C# and Node.js do too.
_SEPARATORS = re.compile(r"[^a-z0-9+#.]+")


def _normalize(text: str) -> str:
    return _SEPARATORS.sub(" ", text.lower()).strip()


# Words that carry no signal about *which* technology is being asked for. A JD
# writes "Modern CSS (Tailwind or similar)"; only "css" and "tailwind" matter,
# and counting the decoration against the candidate dilutes every match.
_STOP_WORDS = frozenset(
    {
        "a", "an", "the", "and", "or", "of", "in", "with", "for", "to", "on", "as",
        "similar", "modern", "strong", "solid", "good", "basic", "familiarity",
        "knowledge", "understanding", "experience", "principles", "concepts",
        "platforms", "systems", "tools", "technologies", "frameworks", "skills",
        "using", "such", "etc", "plus", "years", "year",
    }
)

# Surface forms that mean the same thing. Hand-written and deliberately small:
# matching_service used to reject synonym handling entirely because an
# embedding-per-skill doesn't scale, but a curated table costs nothing and
# covers the cases that actually show up.
_ALIASES = {
    "k8s": "kubernetes",
    "postgres": "postgresql",
    "psql": "postgresql",
    "pg": "postgresql",
    "js": "javascript",
    "ts": "typescript",
    "nodejs": "node.js",
    "node": "node.js",
    "expressjs": "express",
    "reactjs": "react",
    "react.js": "react",
    "nextjs": "next.js",
    "golang": "go",
    "gcp": "googlecloud",
    "postgressql": "postgresql",
    "mongo": "mongodb",
    "ci": "cicd",
    "cd": "cicd",
    "restful": "rest",
    "apis": "api",
    "auth": "authentication",
    "websockets": "websocket",
    "embeddings": "embedding",
    "databases": "database",
    "containers": "container",
}

# A technology implies the concepts it is an instance of. This is what lets
# "pgvector" satisfy a requirement written as "Vector databases", and "JWT"
# satisfy "Authentication/authorization", without an embedding call.
_IMPLIES = {
    "pgvector": {"vector", "database", "embedding"},
    "postgresql": {"sql", "database", "relational"},
    "mysql": {"sql", "database", "relational"},
    "sqlite": {"sql", "database", "relational"},
    "mongodb": {"nosql", "database"},
    "redis": {"nosql", "database", "cache"},
    "jwt": {"authentication", "authorization", "auth"},
    "oauth": {"authentication", "authorization", "auth"},
    "tailwind": {"css"},
    "bootstrap": {"css"},
    "react": {"frontend", "ui"},
    "next.js": {"react", "frontend", "ssr"},
    "express": {"node.js", "backend", "server"},
    "fastapi": {"python", "backend", "server", "rest", "api"},
    "django": {"python", "backend", "server"},
    "flask": {"python", "backend", "server"},
    "socket.io": {"websocket", "realtime"},
    "websocket": {"realtime"},
    "docker": {"container", "containerization"},
    "kubernetes": {"container", "orchestration"},
    "aws": {"cloud"},
    "azure": {"cloud"},
    "googlecloud": {"cloud"},
    "github": {"git"},
    "gitlab": {"git"},
    "rag": {"llm", "embedding", "retrieval"},
    "openai": {"llm", "api"},
    "gemini": {"llm", "api"},
    "anthropic": {"llm", "api"},
    "embedding": {"vector"},
    "cicd": {"deployment", "pipeline"},
}


# Everything the tables already treat as a canonical form. De-pluralisation must
# not touch these, or an alias value gets mangled into something nothing else
# produces: "k8s" mapped to "kubernetes" and then to "kubernete", while plain
# "kubernetes" took a different path, so the two stopped matching each other.
_CANONICAL_VOCAB = (
    set(_ALIASES.values()) | set(_IMPLIES) | {v for values in _IMPLIES.values() for v in values}
)


def _canonical(token: str) -> str:
    """One surface form per concept: alias-mapped, then crudely de-pluralised.

    The length guard keeps three-letter technologies intact — "css" and "aws"
    must not become "cs" and "aw" — and the double-s guard protects "express".
    """
    token = _ALIASES.get(token.strip("."), token.strip("."))
    if token in _CANONICAL_VOCAB:
        return token
    if len(token) > 4 and token.endswith("s") and not token.endswith("ss"):
        singular = token[:-1]
        return _ALIASES.get(singular, singular)
    return token


def _tokens(text: str) -> set[str]:
    """Meaningful, canonical tokens in a phrase."""
    return {
        canonical
        for raw in _normalize(text).split()
        if raw not in _STOP_WORDS and (canonical := _canonical(raw)) and len(canonical) > 1
    }


def _expand(tokens: set[str]) -> set[str]:
    """Tokens plus the concepts they imply."""
    expanded = set(tokens)
    for token in tokens:
        expanded |= {_canonical(t) for t in _IMPLIES.get(token, ())}
    return expanded


# A requirement counts as met when at least this share of its meaningful tokens
# is present. Half, because a two-token requirement like "Vector databases" is
# satisfied by evidence of either half, while a longer phrase still needs real
# coverage rather than one incidental word.
MATCH_THRESHOLD = 0.5


def _requirement_met(requirement: str, evidence: set[str]) -> bool:
    required = _tokens(requirement)
    if not required:
        # Nothing meaningful was asked for (pure stop words) — don't hold it
        # against the candidate.
        return True
    return len(required & evidence) / len(required) >= MATCH_THRESHOLD


def relevance(text: str, skill: str) -> float:
    """How strongly `text` evidences `skill`, from 0.0 to 1.0.

    The same token / alias / implication machinery `_requirement_met` uses,
    exposed as a score rather than a verdict so callers can *rank* candidates
    instead of merely filtering them. `suggestions.py` needs the single most
    related line in a resume, which a boolean cannot answer.

    Agrees with `_requirement_met` at the boundary by construction: it computes
    the same ratio, and `MATCH_THRESHOLD` remains the cutoff for "related at
    all". The one deliberate difference is the empty-requirement case — a skill
    made entirely of stop words is *met* by anything (we don't penalise the
    candidate for a JD's noise) but is evidenced by nothing, so ranking against
    it must return 0.0 rather than 1.0.
    """
    required = _tokens(skill)
    if not required:
        return 0.0
    return len(required & _expand(_tokens(text))) / len(required)


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------


def resume_evidence(resume: ParsedResumeData) -> set[str]:
    """Everything the resume demonstrates, not just its skills list.

    Skill matching used to read `resume.skills` alone, so a candidate whose
    Tailwind, JWT and pgvector work was described in experience bullets and
    project write-ups was scored as though none of it existed. Projects matter
    most here: for an early-career candidate they *are* the evidence.
    """
    parts: list[str] = [" ".join(resume.skills), resume.summary or ""]

    for item in resume.experience:
        parts.extend([item.title or "", *item.bullets])

    for project in getattr(resume, "projects", []) or []:
        parts.extend(
            [
                project.name or "",
                project.description or "",
                " ".join(project.technologies or []),
                *(project.bullets or []),
            ]
        )

    for section in getattr(resume, "additional_sections", []) or []:
        parts.extend([section.heading or "", *(section.items or [])])

    return _expand(_tokens(" ".join(parts)))


# ---------------------------------------------------------------------------
# Sub-scores
# ---------------------------------------------------------------------------


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
    evidence = resume_evidence(resume)

    matched: list[dict] = []
    missing: list[dict] = []

    for priority, skills in (
        ("required", job.required_skills),
        ("preferred", job.preferred_skills),
    ):
        for skill in skills:
            entry = {"skill": skill, "priority": priority}
            (matched if _requirement_met(skill, evidence) else missing).append(entry)

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
_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
# A date with no month at all defaults to January, which makes a year-only range
# ("2022 - 2026") come out at exactly 4 years, the same as the old year-subtraction.
_DEFAULT_MONTH = 1


def _extract_month_year(date_str: str | None, *, is_end_date: bool) -> tuple[int, int] | None:
    """`(year, month)` from free-text resume dates, or None.

    Month granularity is the whole point: subtracting calendar years reported a
    May-to-August internship as *zero* experience, so a candidate who exactly met
    a three-month requirement scored 0.0 on it.
    """
    if not date_str:
        return None

    if is_end_date and re.search(r"present|current|now|ongoing", date_str, re.IGNORECASE):
        now = datetime.now(UTC)
        return now.year, now.month

    year_match = _YEAR_RE.search(date_str)
    if not year_match:
        return None

    lowered = date_str.lower()
    month = next(
        (number for name, number in _MONTHS.items() if name in lowered), _DEFAULT_MONTH
    )
    return int(year_match.group()), month


def candidate_years_of_experience(resume: ParsedResumeData) -> float:
    """Approximate total years from the earliest start to the latest end across
    all experience entries. Assumes continuous employment and ignores gaps and
    overlaps — a deliberate simplification, not a calendar reconstruction, given
    resume date formats are free text.

    Projects are deliberately excluded. They count as *evidence* (see
    `resume_evidence`) but not as duration: a personal project is not
    employment, and inflating this number would misreport the candidate.
    """
    starts = [
        d for e in resume.experience if (d := _extract_month_year(e.start_date, is_end_date=False))
    ]
    ends = [
        d for e in resume.experience if (d := _extract_month_year(e.end_date, is_end_date=True))
    ]
    if not starts or not ends:
        return 0.0

    start_year, start_month = min(starts)
    end_year, end_month = max(ends)
    months = (end_year - start_year) * 12 + (end_month - start_month)
    # Reversed or malformed dates clamp to zero rather than going negative.
    return max(0.0, months / 12)


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
    """How much of the job's vocabulary the document actually uses.

    Token-based, because the JD's "skills" are frequently phrases: only 5 of 20
    terms in a real posting were findable as literal substrings, so this scored
    0.25 for a resume written against that very posting. It was measuring
    whether the JD parser emitted single words, not whether the resume matched.
    """
    requirements = [s for s in [*job.required_skills, *job.preferred_skills] if s]
    if not requirements:
        return 1.0

    evidence = _expand(_tokens(resume_raw_text))
    found = sum(1 for requirement in requirements if _requirement_met(requirement, evidence))
    return found / len(requirements)


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

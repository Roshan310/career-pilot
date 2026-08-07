import math

import pytest

from app.schemas.job import ParsedJobRequirements
from app.schemas.resume import ExperienceItem, ParsedResumeData, ProjectItem
from app.services.matching_service import (
    WEIGHT_EXPERIENCE,
    WEIGHT_KEYWORD_DENSITY,
    WEIGHT_SKILL_OVERLAP,
    _normalize,
    _tokens,
    candidate_years_of_experience,
    compute_scores,
    cosine_similarity,
    experience_match_score,
    keyword_density_score,
    resume_evidence,
    semantic_similarity_score,
    skill_overlap,
)


def test_cosine_similarity_identical_vectors_is_one():
    v = [1.0, 2.0, 3.0]
    assert math.isclose(cosine_similarity(v, v), 1.0, rel_tol=1e-9)


def test_cosine_similarity_orthogonal_vectors_is_zero():
    assert math.isclose(cosine_similarity([1.0, 0.0], [0.0, 1.0]), 0.0, abs_tol=1e-9)


def test_semantic_similarity_score_clamps_to_zero_one():
    assert semantic_similarity_score([1.0, 0.0], [-1.0, 0.0]) == 0.0
    assert semantic_similarity_score([1.0, 0.0], [1.0, 0.0]) == 1.0


def test_skill_overlap_full_match():
    resume = ParsedResumeData(skills=["Python", "Kubernetes", "Terraform"])
    job = ParsedJobRequirements(required_skills=["Python", "Kubernetes"], preferred_skills=["Terraform"])
    score, matched, missing = skill_overlap(resume, job)
    assert score == 1.0
    assert len(matched) == 3
    assert missing == []


def test_skill_overlap_required_weighted_2x_preferred():
    # 1 of 1 required matched, 0 of 1 preferred matched
    # denom = 2*1 + 1 = 3; matched value = 2*1 + 0 = 2 -> 2/3
    resume = ParsedResumeData(skills=["Python"])
    job = ParsedJobRequirements(required_skills=["Python"], preferred_skills=["Go"])
    score, matched, missing = skill_overlap(resume, job)
    assert math.isclose(score, 2 / 3, rel_tol=1e-9)
    assert len(matched) == 1
    assert len(missing) == 1
    assert missing[0]["skill"] == "Go"
    assert missing[0]["priority"] == "preferred"


def test_skill_overlap_no_requirements_is_vacuous_full_match():
    resume = ParsedResumeData(skills=[])
    job = ParsedJobRequirements(required_skills=[], preferred_skills=[])
    score, matched, missing = skill_overlap(resume, job)
    assert score == 1.0
    assert matched == []
    assert missing == []


def test_skill_overlap_case_and_whitespace_insensitive():
    resume = ParsedResumeData(skills=["  PYTHON  "])
    job = ParsedJobRequirements(required_skills=["python"])
    score, matched, _ = skill_overlap(resume, job)
    assert score == 1.0
    assert len(matched) == 1


def test_candidate_years_of_experience_present_job():
    resume = ParsedResumeData(
        experience=[ExperienceItem(start_date="Jan 2020", end_date="Present")]
    )
    years = candidate_years_of_experience(resume)
    assert years >= 5  # 2020 -> now (test written 2026) is at least 5 years


def test_candidate_years_of_experience_missing_dates_is_zero():
    resume = ParsedResumeData(experience=[ExperienceItem(title="X")])
    assert candidate_years_of_experience(resume) == 0.0


def test_experience_match_score_meets_requirement_is_full_score():
    resume = ParsedResumeData(experience=[ExperienceItem(start_date="2015", end_date="2023")])
    job = ParsedJobRequirements(years_experience_required=5)
    assert experience_match_score(resume, job) == 1.0


def test_experience_match_score_below_requirement_uses_sqrt_curve():
    # candidate has 2 years, job wants 8 -> sqrt(2/8) = 0.5, not a linear 0.25
    resume = ParsedResumeData(experience=[ExperienceItem(start_date="2021", end_date="2023")])
    job = ParsedJobRequirements(years_experience_required=8)
    score = experience_match_score(resume, job)
    assert math.isclose(score, math.sqrt(2 / 8), rel_tol=1e-6)
    assert score > 2 / 8  # confirms it's the sub-linear ramp, not a linear penalty


def test_experience_match_score_no_requirement_is_full_score():
    resume = ParsedResumeData(experience=[])
    job = ParsedJobRequirements(years_experience_required=None)
    assert experience_match_score(resume, job) == 1.0


def test_keyword_density_score():
    job = ParsedJobRequirements(required_skills=["Python", "Kubernetes"], preferred_skills=["Go"])
    resume_text = "Experienced with Python and Kubernetes in production."
    score = keyword_density_score(resume_text, job)
    assert math.isclose(score, 2 / 3, rel_tol=1e-9)


def test_keyword_density_no_terms_is_full_score():
    job = ParsedJobRequirements(required_skills=[], preferred_skills=[])
    assert keyword_density_score("anything", job) == 1.0


def test_compute_scores_overall_is_weighted_sum():
    resume = ParsedResumeData(
        skills=["Python"], experience=[ExperienceItem(start_date="2015", end_date="2023")]
    )
    job = ParsedJobRequirements(required_skills=["Python"], years_experience_required=5)
    embedding = [1.0, 0.0]

    result = compute_scores(resume, job, "Python engineer", embedding, embedding)

    expected_overall = (
        0.40 * 1.0  # identical embeddings -> semantic 1.0
        + 0.35 * result["skill_overlap_score"]
        + 0.15 * 1.0  # experience requirement met
        + 0.10 * result["keyword_density_score"]
    )
    assert math.isclose(result["overall_score"], expected_overall, rel_tol=1e-9)


# ==========================================================================
# The reported failure, locked down
#
# A resume written *against* a job description scored 0.469. Fixture captured
# from the real rows (contact details redacted). Four independent defects:
# calendar-year subtraction reported a 3-month internship as zero experience;
# _normalize welded "Authentication/authorization" into one unmatchable token;
# whole-phrase matching missed "Tailwind CSS" against "Modern CSS (Tailwind or
# similar)"; and only 5 of 20 JD terms were findable as literal substrings.
# ==========================================================================

import json
from pathlib import Path

REAL_CASE = json.loads(
    (Path(__file__).parent / "fixtures" / "real_match_case.json").read_text()
)


@pytest.fixture
def real_case():
    return (
        ParsedResumeData.model_validate(REAL_CASE["resume_parsed_data"]),
        ParsedJobRequirements.model_validate(REAL_CASE["job_parsed_requirements"]),
        REAL_CASE["resume_raw_text"],
    )


def test_a_three_month_internship_meets_a_three_month_requirement(real_case):
    """The single largest defect: 15 points of the total, lost to integer years.

    The internship runs May 2026 -> August 2026 and the posting asks for 0.25
    years. Subtracting calendar years gave 2026 - 2026 = 0.
    """
    resume, job, _ = real_case

    assert job.years_experience_required == 0.25
    assert candidate_years_of_experience(resume) == pytest.approx(0.25)
    assert experience_match_score(resume, job) == 1.0


def test_skills_present_under_a_different_surface_form_are_not_reported_missing(real_case):
    """Every one of these was reported as a missing *required* skill while the
    evidence sat in the resume."""
    resume, job, _ = real_case
    _, matched, _ = skill_overlap(resume, job)
    matched_skills = {m["skill"] for m in matched}

    # "Tailwind CSS" is in the skills list.
    assert "Modern CSS (Tailwind or similar)" in matched_skills
    # "JWT Authentication" is in the skills list; the separator used to weld
    # this requirement into "authenticationauthorization".
    assert "Authentication/authorization" in matched_skills
    # "Git & GitHub" normalized to "git  github" — a token with a double space.
    assert "Git & GitHub" in matched_skills
    # PostgreSQL and MongoDB cover both halves.
    assert "SQL and NoSQL databases" in matched_skills


def test_genuinely_absent_skills_are_still_reported(real_case):
    """The fix must not simply match everything — that would be equally useless."""
    resume, job, _ = real_case
    _, _, missing = skill_overlap(resume, job)
    missing_skills = {m["skill"] for m in missing}

    # The resume really does not mention websockets anywhere.
    assert "WebSockets/Socket.io" in missing_skills
    # Nor these two domains.
    assert "Ecommerce platforms" in missing_skills
    assert "Shipment/logistics tracking systems" in missing_skills


def test_keyword_density_measures_the_resume_not_the_jd_parser(real_case):
    """Was 0.25 because 15 of 20 JD terms were multi-word phrases that never
    appear verbatim in any resume."""
    _, job, raw = real_case
    assert keyword_density_score(raw, job) >= 0.6


def test_the_reported_case_now_scores_in_a_defensible_band(real_case):
    """End to end. The user saw 0.469 for a resume tailored to this posting.

    Banded rather than pinned to an exact number: the thresholds and alias table
    will be tuned, and this test should catch a regression to the old behaviour,
    not freeze the tuning.
    """
    resume, job, raw = real_case
    embedding = [0.1] * 1536  # semantic is unaffected by any of this

    scores = compute_scores(resume, job, raw, embedding, embedding)

    assert scores["experience_match_score"] == 1.0
    assert scores["skill_overlap_score"] > 0.65
    assert scores["keyword_density_score"] > 0.6
    # Semantic is pinned at 1.0 by the identical embeddings above, so compare the
    # three sub-scores this module actually owns.
    owned = (
        WEIGHT_SKILL_OVERLAP * scores["skill_overlap_score"]
        + WEIGHT_EXPERIENCE * scores["experience_match_score"]
        + WEIGHT_KEYWORD_DENSITY * scores["keyword_density_score"]
    ) / (WEIGHT_SKILL_OVERLAP + WEIGHT_EXPERIENCE + WEIGHT_KEYWORD_DENSITY)
    assert owned > 0.7, f"was ~0.42 before the fix, got {owned:.3f}"


# ==========================================================================
# Date arithmetic
# ==========================================================================


def _resume_with_dates(start: str | None, end: str | None) -> ParsedResumeData:
    return ParsedResumeData(experience=[ExperienceItem(start_date=start, end_date=end)])


@pytest.mark.parametrize(
    "start,end,expected",
    [
        ("May 2026", "August 2026", 0.25),      # the reported case: 3 months
        ("Jan 2024", "Jan 2025", 1.0),
        ("March 2023", "June 2023", 0.25),
        ("Sept 2022", "March 2023", 0.5),
        ("2022", "2026", 4.0),                   # year-only keeps the old answer
        ("June 2024", "June 2024", 0.0),         # same month
    ],
)
def test_experience_is_measured_in_months(start, end, expected):
    assert candidate_years_of_experience(_resume_with_dates(start, end)) == pytest.approx(expected)


def test_reversed_dates_clamp_to_zero_rather_than_going_negative():
    """A typo or a swapped parse must not produce negative experience, which
    would sail through the sqrt curve as a domain error."""
    assert candidate_years_of_experience(_resume_with_dates("August 2026", "May 2026")) == 0.0


@pytest.mark.parametrize("end", ["Present", "present", "Current", "now", "Ongoing"])
def test_an_open_ended_role_runs_to_today(end):
    assert candidate_years_of_experience(_resume_with_dates("January 2020", end)) > 5.0


@pytest.mark.parametrize("start,end", [(None, "May 2026"), ("May 2026", None), (None, None)])
def test_missing_dates_yield_zero_not_a_crash(start, end):
    assert candidate_years_of_experience(_resume_with_dates(start, end)) == 0.0


def test_projects_do_not_count_toward_duration():
    """Deliberate: a personal project is not employment, and inflating years
    would misreport the candidate to a recruiter."""
    resume = ParsedResumeData(
        experience=[],
        projects=[ProjectItem(name="Side project", start_date="Jan 2020", end_date="Jan 2024")],
    )
    assert candidate_years_of_experience(resume) == 0.0


# ==========================================================================
# Normalization and token matching
# ==========================================================================


@pytest.mark.parametrize(
    "raw,expected_tokens",
    [
        ("Authentication/authorization", {"authentication", "authorization"}),
        ("Git & GitHub", {"git", "github"}),
        ("Server-side logic", {"server", "side", "logic"}),
        ("UI/UX principles", {"ui", "ux"}),  # "principles" is a stop word
        ("WebSockets/Socket.io", {"websocket", "socket.io"}),
    ],
)
def test_separators_split_words_instead_of_welding_them(raw, expected_tokens):
    """These normalized to single unmatchable tokens: "authenticationauthorization",
    "git  github" (with a double space), "serverside"."""
    assert _tokens(raw) == expected_tokens


@pytest.mark.parametrize("raw", ["C++", "C#", "Node.js", "Next.js", "Socket.io"])
def test_technologies_with_punctuation_survive_normalization(raw):
    assert _normalize(raw) == raw.lower()


@pytest.mark.parametrize(
    "alias,canonical",
    [("k8s", "kubernetes"), ("Postgres", "postgresql"), ("JS", "javascript"), ("TS", "typescript")],
)
def test_common_abbreviations_are_canonicalised(alias, canonical):
    assert canonical in _tokens(alias)


@pytest.mark.parametrize("short", ["CSS", "AWS", "SQL"])
def test_short_technologies_are_not_depluralised_into_nonsense(short):
    """The de-pluralisation guard: "css" must not become "cs"."""
    assert short.lower() in _tokens(short)


def test_evidence_is_drawn_from_prose_and_projects_not_just_the_skills_list():
    """Where an early-career candidate's real evidence lives."""
    resume = ParsedResumeData(
        skills=["Python"],
        experience=[ExperienceItem(bullets=["Styled the UI with Tailwind"])],
        projects=[ProjectItem(name="Search", technologies=["pgvector"], bullets=["JWT auth"])],
    )

    evidence = resume_evidence(resume)

    assert "tailwind" in evidence          # from an experience bullet
    assert "pgvector" in evidence          # from a project's technologies
    assert "jwt" in evidence               # from a project bullet
    assert {"vector", "database"} <= evidence  # implied by pgvector
    assert "authentication" in evidence     # implied by jwt


def test_a_requirement_made_only_of_filler_is_not_held_against_the_candidate():
    job = ParsedJobRequirements(required_skills=["Experience with modern tools"])
    score, matched, missing = skill_overlap(ParsedResumeData(), job)
    assert not missing


def test_a_short_skill_no_longer_matches_by_being_inside_another_word():
    """Substring matching ran in both directions, so a requirement for "Go" was
    satisfied by a candidate who listed "Django" — "go" is inside "django".

    A real stored match was inflated by exactly this. Rescoring it *lowers* the
    score, which is the algorithm becoming honest rather than regressing.
    """
    resume = ParsedResumeData(skills=["Python", "Django", "PostgreSQL"])
    job = ParsedJobRequirements(required_skills=["Go", "Python"])

    _, matched, missing = skill_overlap(resume, job)

    assert {m["skill"] for m in matched} == {"Python"}
    assert {m["skill"] for m in missing} == {"Go"}

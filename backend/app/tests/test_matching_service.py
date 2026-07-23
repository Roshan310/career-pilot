import math

from app.schemas.job import ParsedJobRequirements
from app.schemas.resume import ExperienceItem, ParsedResumeData
from app.services.matching_service import (
    candidate_years_of_experience,
    compute_scores,
    cosine_similarity,
    experience_match_score,
    keyword_density_score,
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

"""Choosing which resume line a rewrite suggestion targets.

No LLM calls: `pick_bullet_for_skill` is pure, offline ranking. Only
`generate_suggestions` talks to a model, and that is patched at the client.
"""

import json
import pathlib
from unittest.mock import patch

from app.schemas.resume import ParsedResumeData
from app.services.llm import suggestions

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "real_match_case.json"


def real_resume() -> ParsedResumeData:
    """The resume from the report that started this: a real parse whose five
    experience bullets each cover a different part of the stack."""
    return ParsedResumeData.model_validate(json.loads(FIXTURE.read_text())["resume_parsed_data"])


def test_a_different_skill_picks_a_different_bullet():
    """The reported defect. Every suggestion in a match used to rewrite
    `experience[0].bullets[0]` — chosen once, before the loop over missing
    skills — so the UI showed one identical "your bullet today" on all of them,
    and the model was asked to bend that one line toward whatever was missing.
    """
    resume = real_resume()

    tailwind, _ = suggestions.pick_bullet_for_skill(resume, "Tailwind CSS")
    docker, _ = suggestions.pick_bullet_for_skill(resume, "Docker")
    jwt, _ = suggestions.pick_bullet_for_skill(resume, "JWT authentication")

    assert "Tailwind CSS" in tailwind
    assert "Docker" in docker
    assert "JWT" in jwt
    assert len({tailwind, docker, jwt}) == 3


def test_the_source_label_says_where_the_line_came_from():
    """Without it, a per-skill pick just looks arbitrary from the outside."""
    _, source = suggestions.pick_bullet_for_skill(real_resume(), "Docker")
    assert source == "Software Developer Intern at Arbyte Solution"


def test_nothing_related_returns_no_bullet_at_all():
    """Rather than handing back an unrelated sentence for the model to bend
    toward a skill the candidate has no evidence for — which is pressure toward
    exactly the fabrication the prompt forbids."""
    bullet, source = suggestions.pick_bullet_for_skill(real_resume(), "Kubernetes")
    assert bullet is None
    assert source is None


def test_projects_are_in_the_rewrite_pool():
    """For an early-career candidate the projects section *is* the evidence, and
    a pool drawn from employment history alone has nothing to work with."""
    resume = ParsedResumeData.model_validate(
        {
            "experience": [
                {
                    "title": "Barista",
                    "company": "Cafe",
                    "bullets": ["Served customers and managed the till."],
                }
            ],
            "projects": [
                {
                    "name": "Semantic Search",
                    "bullets": ["Built a retrieval pipeline over pgvector with FastAPI."],
                }
            ],
        }
    )

    bullet, source = suggestions.pick_bullet_for_skill(resume, "Vector databases")

    assert "pgvector" in bullet
    assert source == "Project: Semantic Search"


def test_ties_keep_the_most_recent_experience():
    """Experience is listed most-recent-first, so a tie should resolve toward the
    line an employer is most likely to care about."""
    resume = ParsedResumeData.model_validate(
        {
            "experience": [
                {"title": "Recent", "company": "A", "bullets": ["Shipped a Docker pipeline."]},
                {"title": "Older", "company": "B", "bullets": ["Shipped a Docker pipeline."]},
            ]
        }
    )

    _, source = suggestions.pick_bullet_for_skill(resume, "Docker")
    assert source == "Recent at A"


def test_an_empty_resume_yields_no_bullet_rather_than_raising():
    bullet, source = suggestions.pick_bullet_for_skill(ParsedResumeData(), "Docker")
    assert (bullet, source) == (None, None)


# --- generate_suggestions ---------------------------------------------------


def _canned(**overrides):
    base = {"suggestion": "a rewritten bullet", "has_honest_connection": True}
    base.update(overrides)
    return base


def test_each_suggestion_carries_its_own_bullet_and_source():
    resume = real_resume()
    gaps = [
        {"skill": "Docker", "priority": "required"},
        {"skill": "Tailwind CSS", "priority": "required"},
    ]

    with patch.object(suggestions, "call_json", return_value=_canned()):
        results = suggestions.generate_suggestions(resume, gaps)

    assert len(results) == 2
    assert "Docker" in results[0]["original_bullet"]
    assert "Tailwind CSS" in results[1]["original_bullet"]
    assert all(r["original_bullet_source"] for r in results)


def test_a_gap_with_no_evidence_is_prompted_without_a_bullet():
    """The prompt asks what to build toward instead of what to rewrite, and the
    stored suggestion carries no `original_bullet` — which is how the UI knows
    to drop the strikethrough "before" it would otherwise show."""
    with patch.object(suggestions, "call_json", return_value=_canned(has_honest_connection=False)) as call:
        results = suggestions.generate_suggestions(
            real_resume(), [{"skill": "Kubernetes", "priority": "required"}]
        )

    prompt = call.call_args.args[0]
    assert "Candidate's current bullet" not in prompt
    assert "Nothing in the candidate's background relates" in prompt
    assert results[0]["original_bullet"] is None
    assert results[0]["original_bullet_source"] is None


def test_the_honest_connection_context_includes_projects():
    """Otherwise the model confidently reports "no honest connection" about work
    the resume plainly shows — the same hole `resume_evidence` had before
    projects were parsed."""
    resume = ParsedResumeData.model_validate(
        {"projects": [{"name": "Search", "bullets": ["Used pgvector for retrieval."]}]}
    )

    with patch.object(suggestions, "call_json", return_value=_canned()) as call:
        suggestions.generate_suggestions(resume, [{"skill": "pgvector", "priority": "required"}])

    assert "pgvector" in call.call_args.args[0]


def test_suggestions_are_capped_and_required_skills_come_first():
    gaps = [{"skill": f"Skill {i}", "priority": "preferred"} for i in range(8)]
    gaps.append({"skill": "Docker", "priority": "required"})

    with patch.object(suggestions, "call_json", return_value=_canned()):
        results = suggestions.generate_suggestions(real_resume(), gaps)

    assert len(results) == suggestions.MAX_SUGGESTIONS
    assert results[0]["missing_skill"] == "Docker"

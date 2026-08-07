import uuid
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.db.session import get_db
from app.main import app
from app.models.job_description import JobDescription
from app.models.match import Match
from app.models.resume import Resume
from app.schemas.interview import QuestionPlan
from app.services.auth_service import issue_tokens, register_user
from app.services.llm.answer_evaluation import AnswerEvaluation
from app.services.tts import TTSUnavailableError

settings = get_settings()
EMBEDDING = [0.1] * 1536

QUESTIONS = [
    {"question_text": f"Question {i}", "question_type": "main", "targets_gap": f"gap-{i}", "based_on": f"bullet {i}"}
    for i in range(1, 7)
]
CANNED_PLAN = QuestionPlan(questions=QUESTIONS)


@pytest.fixture
async def resume_job_match(db_session):
    user = await register_user(db_session, "interviewuser@example.com", "password123", None)
    resume = Resume(
        user_id=user.id,
        raw_text="Experienced Python engineer",
        parsed_data={"skills": ["Python"], "experience": []},
        embedding=EMBEDDING,
    )
    job = JobDescription(
        user_id=user.id,
        raw_text="Need a Python engineer",
        parsed_requirements={"required_skills": ["Python"]},
        embedding=EMBEDDING,
    )
    db_session.add_all([resume, job])
    await db_session.flush()
    match = Match(
        resume_id=resume.id,
        job_id=job.id,
        status="done",
        missing_skills=[{"skill": "gap-1", "priority": "required"}],
    )
    db_session.add(match)
    await db_session.commit()
    await db_session.refresh(resume)
    await db_session.refresh(job)
    await db_session.refresh(match)
    return user, resume, job, match


@pytest.fixture
async def authed_client(db_session, resume_job_match):
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    user, _, _, _ = resume_job_match
    access_token, _ = issue_tokens(user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        client.headers["Authorization"] = f"Bearer {access_token}"
        yield client

    app.dependency_overrides.clear()


def _create_interview_payload(resume, job, match):
    return {"resume_id": str(resume.id), "job_id": str(job.id), "match_id": str(match.id)}


async def test_create_interview_generates_question_plan_and_first_question(authed_client, resume_job_match):
    _, resume, job, match = resume_job_match
    with patch("app.services.interview_service.generate_question_plan", return_value=CANNED_PLAN):
        response = await authed_client.post("/api/interviews", json=_create_interview_payload(resume, job, match))

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "in_progress"
    assert len(body["question_plan"]) == 6
    assert body["current_question"]["turn_number"] == 1
    assert body["current_question"]["question_text"] == "Question 1"


def _good_evaluation(**overrides):
    base = {"structure": 5, "specificity": 5, "relevance": 5, "next_action": "next_question", "follow_up_question": None}
    base.update(overrides)
    return base


async def test_well_answered_session_completes_without_followups(authed_client, resume_job_match):
    _, resume, job, match = resume_job_match
    with patch("app.services.interview_service.generate_question_plan", return_value=CANNED_PLAN):
        create_response = await authed_client.post(
            "/api/interviews", json=_create_interview_payload(resume, job, match)
        )
    session_id = create_response.json()["id"]

    with patch("app.services.interview_service.evaluate_answer") as mock_eval:
        from app.services.llm.answer_evaluation import AnswerEvaluation

        mock_eval.return_value = AnswerEvaluation(**_good_evaluation())

        question_number = 1
        session_status = "in_progress"
        turns_answered = 0
        while session_status == "in_progress" and turns_answered < 10:
            response = await authed_client.post(
                f"/api/interviews/{session_id}/turns",
                json={"question_number": question_number, "answer_transcript": "A great STAR answer.", "duration": 30.0},
            )
            assert response.status_code == 200, response.text
            body = response.json()
            session_status = body["session_status"]
            turns_answered += 1
            if body["next_question"]:
                question_number = body["next_question"]["turn_number"]

    assert session_status == "wrapping_up"
    assert turns_answered == len(QUESTIONS)  # exactly 6 main questions, zero follow-ups

    complete_response = await authed_client.post(f"/api/interviews/{session_id}/complete")
    assert complete_response.status_code == 200, complete_response.text
    report = complete_response.json()
    assert report["overall_score"] == 5.0
    # Findings are patterns across the session, not one entry per question — six
    # flawless answers are three strong dimensions plus full participation, not
    # six identical rows. See report_findings.py.
    assert [f["code"] for f in report["strengths"]] == [
        "structure_strong",
        "specificity_strong",
        "relevance_strong",
        "all_questions_answered",
    ]
    assert report["improvement_areas"] == []


async def test_weakly_answered_session_reports_what_went_wrong(authed_client, resume_job_match):
    """The bug this guards: a report whose columns were empty or listed nothing
    but question titles, leaving the candidate with no idea what to fix."""
    _, resume, job, match = resume_job_match
    with patch("app.services.interview_service.generate_question_plan", return_value=CANNED_PLAN):
        create_response = await authed_client.post(
            "/api/interviews", json=_create_interview_payload(resume, job, match)
        )
    session_id = create_response.json()["id"]

    with patch("app.services.interview_service.evaluate_answer") as mock_eval:
        from app.services.llm.answer_evaluation import AnswerEvaluation

        mock_eval.return_value = AnswerEvaluation(
            **_good_evaluation(structure=2, specificity=1, relevance=2)
        )

        question_number = 1
        session_status = "in_progress"
        while session_status == "in_progress":
            response = await authed_client.post(
                f"/api/interviews/{session_id}/turns",
                json={
                    "question_number": question_number,
                    "answer_transcript": "I guess I just sort of handled it.",
                    "duration": 30.0,
                },
            )
            body = response.json()
            session_status = body["session_status"]
            if body["next_question"]:
                question_number = body["next_question"]["turn_number"]

    report = (await authed_client.post(f"/api/interviews/{session_id}/complete")).json()

    improvements = {f["code"]: f for f in report["improvement_areas"]}
    assert set(improvements) == {"structure_weak", "specificity_weak", "relevance_weak"}
    # Weakest first, each naming its average and a question that demonstrates it.
    assert [f["code"] for f in report["improvement_areas"]][0] == "specificity_weak"
    assert improvements["specificity_weak"]["average"] == 1.0
    assert improvements["specificity_weak"]["turns_counted"] == len(QUESTIONS)
    assert improvements["specificity_weak"]["exemplar"]["question_text"] in {
        q["question_text"] for q in QUESTIONS
    }
    # And no invented consolation prize on the other side.
    assert [f["code"] for f in report["strengths"] if f["kind"] == "dimension"] == []


async def test_forced_followup_caps_at_max_then_advances(authed_client, resume_job_match):
    _, resume, job, match = resume_job_match
    with patch("app.services.interview_service.generate_question_plan", return_value=CANNED_PLAN):
        create_response = await authed_client.post(
            "/api/interviews", json=_create_interview_payload(resume, job, match)
        )
    session_id = create_response.json()["id"]

    from app.services.llm.answer_evaluation import AnswerEvaluation

    # Always tells the state machine to ask a follow-up — the cap must still hold.
    always_follow_up = AnswerEvaluation(
        structure=2, specificity=2, relevance=2, next_action="follow_up", follow_up_question="Can you say more?"
    )

    with patch("app.services.interview_service.evaluate_answer", return_value=always_follow_up):
        response = await authed_client.post(
            f"/api/interviews/{session_id}/turns",
            json={"question_number": 1, "answer_transcript": "vague answer", "duration": 10.0},
        )
        assert response.json()["next_question"]["question_type"] == "follow_up"

        followup_count = 0
        question_number = response.json()["next_question"]["turn_number"]
        for _ in range(settings.interview_max_followups_per_question + 2):
            resp = await authed_client.post(
                f"/api/interviews/{session_id}/turns",
                json={"question_number": question_number, "answer_transcript": "still vague", "duration": 10.0},
            )
            body = resp.json()
            if body["next_question"] and body["next_question"]["question_type"] == "follow_up":
                followup_count += 1
                question_number = body["next_question"]["turn_number"]
            else:
                break

        assert followup_count == settings.interview_max_followups_per_question - 1
        # after the cap, the next question served must be "Question 2" (advance), not another follow-up
        assert body["next_question"]["question_text"] == "Question 2"


async def test_mismatched_question_number_returns_conflict(authed_client, resume_job_match):
    _, resume, job, match = resume_job_match
    with patch("app.services.interview_service.generate_question_plan", return_value=CANNED_PLAN):
        create_response = await authed_client.post(
            "/api/interviews", json=_create_interview_payload(resume, job, match)
        )
    session_id = create_response.json()["id"]

    response = await authed_client.post(
        f"/api/interviews/{session_id}/turns",
        json={"question_number": 99, "answer_transcript": "wrong turn", "duration": 5.0},
    )
    assert response.status_code == 409


async def test_list_interviews_returns_own_sessions_with_joined_info(authed_client, resume_job_match, db_session):
    _, resume, job, match = resume_job_match
    job.title = "Backend Engineer"
    job.company = "Stripe"
    await db_session.commit()

    with patch("app.services.interview_service.generate_question_plan", return_value=CANNED_PLAN):
        create_response = await authed_client.post(
            "/api/interviews", json=_create_interview_payload(resume, job, match)
        )
    assert create_response.status_code == 201

    response = await authed_client.get("/api/interviews")
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body) == 1
    item = body[0]
    assert item["status"] == "in_progress"
    assert item["job_title"] == "Backend Engineer"
    assert item["job_company"] == "Stripe"
    assert item["overall_score"] is None  # no report yet
    assert item["ended_at"] is None


async def test_get_interview_report_before_completion_returns_404(authed_client, resume_job_match):
    _, resume, job, match = resume_job_match
    with patch("app.services.interview_service.generate_question_plan", return_value=CANNED_PLAN):
        create_response = await authed_client.post(
            "/api/interviews", json=_create_interview_payload(resume, job, match)
        )
    session_id = create_response.json()["id"]

    response = await authed_client.get(f"/api/interviews/{session_id}/report")
    assert response.status_code == 404


async def _start_session(client, resume, job, match) -> str:
    with patch("app.services.interview_service.generate_question_plan", return_value=CANNED_PLAN):
        response = await client.post("/api/interviews", json=_create_interview_payload(resume, job, match))
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def test_create_response_carries_progress_for_the_live_ui(authed_client, resume_job_match):
    _, resume, job, match = resume_job_match
    with patch("app.services.interview_service.generate_question_plan", return_value=CANNED_PLAN):
        response = await authed_client.post("/api/interviews", json=_create_interview_payload(resume, job, match))

    progress = response.json()["progress"]
    assert progress["main_questions_answered"] == 0
    assert progress["main_questions_planned"] == len(QUESTIONS)
    assert progress["seconds_remaining"] > 0
    assert progress["hard_capped"] is False


async def test_get_interview_returns_turns_for_reconnect(authed_client, resume_job_match):
    _, resume, job, match = resume_job_match
    session_id = await _start_session(authed_client, resume, job, match)

    with patch("app.services.interview_service.evaluate_answer", return_value=AnswerEvaluation(**_good_evaluation())):
        await authed_client.post(
            f"/api/interviews/{session_id}/turns",
            json={
                "question_number": 1,
                "answer_transcript": "I led the migration end to end.",
                "duration": 30.0,
                "source": "typed",
            },
        )

    response = await authed_client.get(f"/api/interviews/{session_id}")
    assert response.status_code == 200, response.text
    body = response.json()

    # the answered turn keeps its transcript, and the pending one is the current question
    assert len(body["turns"]) == 2
    assert body["turns"][0]["answer_transcript"] == "I led the migration end to end."
    assert body["turns"][0]["score"] == {"structure": 5, "specificity": 5, "relevance": 5}
    assert body["turns"][1]["answer_transcript"] is None
    assert body["current_question"]["turn_number"] == 2
    assert body["progress"]["main_questions_answered"] == 1


async def test_speech_metrics_are_computed_and_persisted_per_turn(authed_client, resume_job_match):
    _, resume, job, match = resume_job_match
    session_id = await _start_session(authed_client, resume, job, match)

    with patch("app.services.interview_service.evaluate_answer", return_value=AnswerEvaluation(**_good_evaluation())):
        response = await authed_client.post(
            f"/api/interviews/{session_id}/turns",
            json={
                "question_number": 1,
                "answer_transcript": "Um, I sort of led the migration.",
                "duration": 30.0,
                "source": "browser_speech",
                "segments": [
                    {"text": "Um, I sort of", "start_ms": 0, "end_ms": 2000},
                    {"text": "led the migration.", "start_ms": 5000, "end_ms": 7000},
                ],
            },
        )

    metrics = response.json()["speech_metrics"]
    assert metrics["word_count"] == 7
    assert metrics["wpm"] == 14.0
    assert metrics["filler_count"] == 2  # "um" + "sort of"
    assert metrics["longest_pause_ms"] == 3000.0
    assert metrics["source"] == "browser_speech"

    # and it survives to the turn history
    turns = (await authed_client.get(f"/api/interviews/{session_id}")).json()["turns"]
    assert turns[0]["speech_metrics"]["filler_count"] == 2


async def test_skipped_turn_advances_without_calling_the_llm(authed_client, resume_job_match):
    _, resume, job, match = resume_job_match
    session_id = await _start_session(authed_client, resume, job, match)

    with patch("app.services.interview_service.evaluate_answer") as mock_eval:
        response = await authed_client.post(
            f"/api/interviews/{session_id}/turns",
            json={"question_number": 1, "answer_transcript": "", "duration": 8.0, "skipped": True},
        )

    assert response.status_code == 200, response.text
    mock_eval.assert_not_called()  # §7.2: silence costs no LLM round trip

    body = response.json()
    assert body["evaluation"] is None
    assert body["speech_metrics"] is None
    assert body["next_question"]["question_text"] == "Question 2"

    # the skipped turn counts as answered, so the interview genuinely moved on
    turns = (await authed_client.get(f"/api/interviews/{session_id}")).json()["turns"]
    assert turns[0]["answer_transcript"] == ""
    assert turns[0]["score"] is None


async def test_blank_transcript_is_treated_as_skipped(authed_client, resume_job_match):
    _, resume, job, match = resume_job_match
    session_id = await _start_session(authed_client, resume, job, match)

    with patch("app.services.interview_service.evaluate_answer") as mock_eval:
        response = await authed_client.post(
            f"/api/interviews/{session_id}/turns",
            json={"question_number": 1, "answer_transcript": "   ", "duration": 8.0},
        )

    assert response.status_code == 200
    mock_eval.assert_not_called()
    assert response.json()["next_question"]["question_text"] == "Question 2"


async def test_wrapping_up_status_is_persisted_not_just_reported(authed_client, resume_job_match):
    _, resume, job, match = resume_job_match
    session_id = await _start_session(authed_client, resume, job, match)

    with patch("app.services.interview_service.evaluate_answer", return_value=AnswerEvaluation(**_good_evaluation())):
        question_number = 1
        for _ in range(len(QUESTIONS)):
            body = (
                await authed_client.post(
                    f"/api/interviews/{session_id}/turns",
                    json={"question_number": question_number, "answer_transcript": "A great answer.", "duration": 30.0},
                )
            ).json()
            if body["next_question"] is None:
                break
            question_number = body["next_question"]["turn_number"]

    assert body["session_status"] == "wrapping_up"

    # a client reconnecting mid-session must see the same thing, not "in_progress"
    reconnect = (await authed_client.get(f"/api/interviews/{session_id}")).json()
    assert reconnect["status"] == "wrapping_up"
    assert reconnect["current_question"] is None

    # no further answers accepted once wrapping up
    late = await authed_client.post(
        f"/api/interviews/{session_id}/turns",
        json={"question_number": 7, "answer_transcript": "one more thing", "duration": 5.0},
    )
    assert late.status_code == 409

    # but it can still be completed
    assert (await authed_client.post(f"/api/interviews/{session_id}/complete")).status_code == 200


async def test_report_includes_the_session_speech_rollup(authed_client, resume_job_match):
    _, resume, job, match = resume_job_match
    session_id = await _start_session(authed_client, resume, job, match)

    with patch("app.services.interview_service.evaluate_answer", return_value=AnswerEvaluation(**_good_evaluation())):
        for question_number, transcript in ((1, "Um, I led it."), (2, "I like shipped it, you know.")):
            await authed_client.post(
                f"/api/interviews/{session_id}/turns",
                json={"question_number": question_number, "answer_transcript": transcript, "duration": 30.0},
            )

    report = (await authed_client.post(f"/api/interviews/{session_id}/complete")).json()
    rollup = report["speech_metrics"]
    assert rollup["turns_measured"] == 2
    assert rollup["total_filler_count"] == 3  # "um" + "like" + "you know"
    assert rollup["avg_wpm"] > 0


async def test_abandon_ends_the_session_without_a_report(authed_client, resume_job_match):
    _, resume, job, match = resume_job_match
    session_id = await _start_session(authed_client, resume, job, match)

    response = await authed_client.post(f"/api/interviews/{session_id}/abandon")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "abandoned"
    assert body["ended_at"] is not None

    # no report was generated, and the session is closed to further answers
    assert (await authed_client.get(f"/api/interviews/{session_id}/report")).status_code == 404
    late = await authed_client.post(
        f"/api/interviews/{session_id}/turns",
        json={"question_number": 1, "answer_transcript": "still here", "duration": 5.0},
    )
    assert late.status_code == 409
    assert (await authed_client.post(f"/api/interviews/{session_id}/abandon")).status_code == 409

    # and it shows up as abandoned in history rather than as a real result
    listed = (await authed_client.get("/api/interviews")).json()
    assert listed[0]["status"] == "abandoned"
    assert listed[0]["overall_score"] is None


async def test_abandon_and_complete_require_ownership(authed_client, resume_job_match, db_session):
    _, resume, job, match = resume_job_match
    session_id = await _start_session(authed_client, resume, job, match)

    other = await register_user(db_session, "otherinterviewuser@example.com", "password123", None)
    other_token, _ = issue_tokens(other)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as other_client:
        other_client.headers["Authorization"] = f"Bearer {other_token}"
        assert (await other_client.post(f"/api/interviews/{session_id}/abandon")).status_code == 404
        assert (await other_client.post(f"/api/interviews/{session_id}/complete")).status_code == 404
        assert (await other_client.get(f"/api/interviews/{session_id}")).status_code == 404


def test_llm_descriptive_question_type_does_not_become_a_control_flag():
    """Regression: Gemini returns question_type values like "Technical Deep Dive"
    (§7.1's prompt never constrains the field). Those must not reach the state
    machine, which reads question_type as main|follow_up — see the validator on
    QuestionPlanItem."""
    plan = QuestionPlan(
        questions=[
            {"question_text": "Q1", "question_type": "Technical Deep Dive"},
            {"question_text": "Q2", "question_type": "Behavioral/Leadership", "category": "given"},
            {"question_text": "Q3", "question_type": "main"},
        ]
    )

    assert [q.question_type for q in plan.questions] == ["main", "main", "main"]
    assert plan.questions[0].category == "Technical Deep Dive"  # label preserved, not discarded
    assert plan.questions[1].category == "given"  # an explicit category isn't overwritten


def test_llm_list_valued_fields_are_coerced_to_scalars():
    """Regression: a question probing several related gaps makes Gemini return
    targets_gap as a JSON array (['Distributed Systems', 'Scalability', ...]).
    Field validation rejected that outright, so the whole plan raised
    LLMServiceError and no interview could start."""
    plan = QuestionPlan(
        questions=[
            {
                "question_text": "How have you handled scale?",
                "question_type": ["Technical", "Gap"],
                "targets_gap": ["Distributed Systems", "Scalability", "Production Environments"],
                "based_on": ["JD requirement 2", "JD requirement 5"],
            },
            {"question_text": "Q2", "targets_gap": "Kubernetes"},
            {"question_text": "Q3", "targets_gap": []},
        ]
    )

    # targets_gap is a join key into missing_skills[].skill (see
    # interview_service.aggregate_report), so it keeps the FIRST gap rather than
    # a joined string — a joined string would match no skill at all and the gap
    # would be reported still-open forever.
    assert plan.questions[0].targets_gap == "Distributed Systems"
    assert plan.questions[0].question_type == "main"
    assert plan.questions[0].based_on == "JD requirement 2"
    assert plan.questions[1].targets_gap == "Kubernetes"  # scalars pass through untouched
    assert plan.questions[2].targets_gap is None  # an empty list is "no gap", not ""


async def test_list_valued_targets_gap_still_counts_toward_gap_coverage(authed_client, resume_job_match):
    """The point of the coercion above: after normalizing, the gap still matches
    a missing_skills entry and shows up as addressed in the report."""
    _, resume, job, match = resume_job_match
    # "gap-1" is the fixture's only missing skill; the extra entries are the noise
    # the LLM adds when a question probes several related gaps at once.
    plan = QuestionPlan(
        questions=[{"question_text": "Tell me about scaling.", "targets_gap": ["gap-1", "Kubernetes"]}]
    )

    with patch("app.services.interview_service.generate_question_plan", return_value=plan):
        session_id = (
            await authed_client.post("/api/interviews", json=_create_interview_payload(resume, job, match))
        ).json()["id"]

    with patch("app.services.interview_service.evaluate_answer", return_value=AnswerEvaluation(**_good_evaluation())):
        await authed_client.post(
            f"/api/interviews/{session_id}/turns",
            json={"question_number": 1, "answer_transcript": "I ran EKS in production for two years.", "duration": 25.0},
        )

    report = (await authed_client.post(f"/api/interviews/{session_id}/complete")).json()
    assert report["gap_coverage"]["addressed"] == ["gap-1"]


async def test_interview_advances_through_the_plan_with_llm_question_types(authed_client, resume_job_match):
    """End-to-end version of the above: with descriptive question_types, the
    session must walk the plan instead of re-serving question 1."""
    _, resume, job, match = resume_job_match
    descriptive_plan = QuestionPlan(
        questions=[
            {"question_text": f"Question {i}", "question_type": "Technical/Gap", "targets_gap": f"gap-{i}"}
            for i in range(1, 4)
        ]
    )

    with patch("app.services.interview_service.generate_question_plan", return_value=descriptive_plan):
        session_id = (
            await authed_client.post("/api/interviews", json=_create_interview_payload(resume, job, match))
        ).json()["id"]

    asked = []
    with patch("app.services.interview_service.evaluate_answer", return_value=AnswerEvaluation(**_good_evaluation())):
        question_number = 1
        for _ in range(len(descriptive_plan.questions)):
            body = (
                await authed_client.post(
                    f"/api/interviews/{session_id}/turns",
                    json={"question_number": question_number, "answer_transcript": "A solid answer.", "duration": 20.0},
                )
            ).json()
            if body["next_question"] is None:
                break
            asked.append(body["next_question"]["question_text"])
            question_number = body["next_question"]["turn_number"]

    assert asked == ["Question 2", "Question 3"]  # never repeats Question 1
    assert body["session_status"] == "wrapping_up"

    progress = (await authed_client.get(f"/api/interviews/{session_id}")).json()["progress"]
    assert progress["main_questions_answered"] == 3


# ---- the voice endpoints (SPECS.md §7.3, moved server-side) ----

async def _start_session(authed_client, resume, job, match) -> str:
    with patch("app.services.interview_service.generate_question_plan", return_value=CANNED_PLAN):
        response = await authed_client.post("/api/interviews", json=_create_interview_payload(resume, job, match))
    return response.json()["id"]


async def test_question_audio_is_served_for_the_turns_own_question(authed_client, resume_job_match):
    _, resume, job, match = resume_job_match
    session_id = await _start_session(authed_client, resume, job, match)

    with patch("app.services.tts.question_audio", return_value=b"mp3-bytes") as synth:
        response = await authed_client.get(f"/api/interviews/{session_id}/turns/1/audio")

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.content == b"mp3-bytes"
    # The text spoken is the stored question — never client-supplied, or the
    # endpoint becomes a way to bill someone else's key for arbitrary text.
    assert synth.call_args.args[2] == "Question 1"


async def test_missing_voice_config_degrades_to_503_not_a_broken_interview(authed_client, resume_job_match):
    """The client answers a 503 by falling back to the browser's own voice, so
    this path must stay distinguishable from a real interview failure."""
    _, resume, job, match = resume_job_match
    session_id = await _start_session(authed_client, resume, job, match)

    with patch("app.services.tts.question_audio", side_effect=TTSUnavailableError("no key")):
        response = await authed_client.get(f"/api/interviews/{session_id}/turns/1/audio")

    assert response.status_code == 503


async def test_audio_for_a_turn_that_does_not_exist_is_404(authed_client, resume_job_match):
    _, resume, job, match = resume_job_match
    session_id = await _start_session(authed_client, resume, job, match)

    response = await authed_client.get(f"/api/interviews/{session_id}/turns/99/audio")
    assert response.status_code == 404


async def test_another_users_session_audio_is_not_reachable(authed_client, resume_job_match, db_session):
    """Ownership is checked before anything is generated — otherwise one account
    could spend another's TTS budget and hear their questions."""
    _, resume, job, match = resume_job_match
    session_id = await _start_session(authed_client, resume, job, match)

    intruder = await register_user(db_session, "intruder-audio@example.com", "password123", None)
    token, _ = issue_tokens(intruder)

    with patch("app.services.tts.question_audio") as synth:
        response = await authed_client.get(
            f"/api/interviews/{session_id}/turns/1/audio",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 404
    assert synth.call_count == 0


async def test_transcribe_returns_the_text_for_an_uploaded_answer(authed_client, resume_job_match):
    _, resume, job, match = resume_job_match
    session_id = await _start_session(authed_client, resume, job, match)

    with patch("app.services.transcription.call_transcription", return_value="I shipped it on Friday."):
        response = await authed_client.post(
            f"/api/interviews/{session_id}/transcribe",
            files={"audio": ("answer.webm", b"fake-opus-bytes", "audio/webm;codecs=opus")},
        )

    assert response.status_code == 200, response.text
    assert response.json() == {"transcript": "I shipped it on Friday."}


async def test_transcribed_answer_submits_as_server_stt_with_real_pause_timings(
    authed_client, resume_job_match
):
    """The whole round trip the browser now does: record → transcribe → submit.
    `server_stt` was already an accepted source; this is the first thing to send
    it. The segments are VAD bursts, so longest_pause_ms is measured rather than
    inferred — the value that used to come back as a structural zero."""
    _, resume, job, match = resume_job_match
    session_id = await _start_session(authed_client, resume, job, match)

    with patch("app.services.transcription.call_transcription", return_value="I rewrote the retry loop."):
        transcript = (
            await authed_client.post(
                f"/api/interviews/{session_id}/transcribe",
                files={"audio": ("answer.webm", b"fake-opus-bytes", "audio/webm")},
            )
        ).json()["transcript"]

    with patch("app.services.interview_service.evaluate_answer", return_value=AnswerEvaluation(**_good_evaluation())):
        response = await authed_client.post(
            f"/api/interviews/{session_id}/turns",
            json={
                "question_number": 1,
                "answer_transcript": transcript,
                "duration": 9.0,
                "source": "server_stt",
                "segments": [
                    {"text": transcript, "start_ms": 0, "end_ms": 2000},
                    {"text": "", "start_ms": 5500, "end_ms": 9000},
                ],
            },
        )

    assert response.status_code == 200, response.text
    metrics = response.json()["speech_metrics"]
    assert metrics["source"] == "server_stt"
    assert metrics["longest_pause_ms"] == 3500
    assert metrics["word_count"] == 5


async def test_transcribe_on_another_users_session_is_not_reachable(authed_client, resume_job_match, db_session):
    _, resume, job, match = resume_job_match
    session_id = await _start_session(authed_client, resume, job, match)

    intruder = await register_user(db_session, "intruder-stt@example.com", "password123", None)
    token, _ = issue_tokens(intruder)

    with patch("app.services.transcription.call_transcription") as call:
        response = await authed_client.post(
            f"/api/interviews/{session_id}/transcribe",
            files={"audio": ("answer.webm", b"bytes", "audio/webm")},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 404
    assert call.call_count == 0


# --------------------------------------------------------------------------
# Completing twice
#
# A double-click, a retry after a dropped response, or two open tabs all send a
# second POST /complete. Before session_reports.session_id was unique this wrote
# a second report, and GET /report's scalar_one_or_none() then raised
# MultipleResultsFound for that session *permanently* — the user could never see
# their report again.
# --------------------------------------------------------------------------


async def test_completing_twice_returns_the_same_report(authed_client, resume_job_match):
    _, resume, job, match = resume_job_match
    session_id = await _start_session(authed_client, resume, job, match)

    with patch("app.services.interview_service.evaluate_answer", return_value=AnswerEvaluation(**_good_evaluation())):
        await authed_client.post(
            f"/api/interviews/{session_id}/turns",
            json={"question_number": 1, "answer_transcript": "A great STAR answer.", "duration": 30.0},
        )

    first = await authed_client.post(f"/api/interviews/{session_id}/complete")
    second = await authed_client.post(f"/api/interviews/{session_id}/complete")

    assert first.status_code == 200, first.text
    # Idempotent, not a 409: "finish my interview" on an already-finished
    # interview has an obvious correct answer.
    assert second.status_code == 200, second.text
    assert second.json()["id"] == first.json()["id"]

    # The endpoint that used to break is still readable.
    report = await authed_client.get(f"/api/interviews/{session_id}/report")
    assert report.status_code == 200
    assert report.json()["id"] == first.json()["id"]


async def test_a_second_report_row_cannot_be_inserted(authed_client, resume_job_match, db_session):
    """The database constraint, not just the application check.

    complete_session's status guard is check-then-set and cannot be atomic, so
    the uniqueness has to be enforced underneath it.
    """
    from sqlalchemy.exc import IntegrityError

    from app.models.interview import SessionReport

    _, resume, job, match = resume_job_match
    session_id = await _start_session(authed_client, resume, job, match)
    await authed_client.post(f"/api/interviews/{session_id}/complete")

    db_session.add(SessionReport(session_id=uuid.UUID(session_id), overall_score=1.0))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


async def test_session_response_says_what_the_interview_was_about(authed_client, resume_job_match):
    """resume_id / job_id / match_id on the session response.

    The report page needs these to name the role and to offer "Practice again"
    with the pairing pre-selected — without them its heading was the literal
    string "Interview Feedback" and the ids were unreachable, so the only next
    step was a link back to the list.
    """
    _, resume, job, match = resume_job_match
    with patch("app.services.interview_service.generate_question_plan", return_value=CANNED_PLAN):
        created = await authed_client.post(
            "/api/interviews", json=_create_interview_payload(resume, job, match)
        )
    assert created.status_code == 201, created.text

    body = created.json()
    assert body["resume_id"] == str(resume.id)
    assert body["job_id"] == str(job.id)
    assert body["match_id"] == str(match.id)

    # And on re-fetch, which is the path the report page actually takes.
    fetched = (await authed_client.get(f"/api/interviews/{body['id']}")).json()
    assert fetched["job_id"] == str(job.id)


async def test_match_id_is_null_when_the_interview_had_no_gap_analysis(authed_client, resume_job_match):
    """An interview started without a prior match is legal; the practice link
    just omits the match parameter rather than sending "None"."""
    _, resume, job, _ = resume_job_match
    with patch("app.services.interview_service.generate_question_plan", return_value=CANNED_PLAN):
        created = await authed_client.post(
            "/api/interviews", json={"resume_id": str(resume.id), "job_id": str(job.id)}
        )

    body = created.json()
    assert body["match_id"] is None
    assert body["resume_id"] == str(resume.id)

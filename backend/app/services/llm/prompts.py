RESUME_PARSING_SCHEMA = """{
  "contact": { "name": "", "email": "", "phone": "", "location": "" },
  "summary": "",
  "skills": ["Python", "React", "AWS"],
  "experience": [
    {
      "title": "", "company": "", "start_date": "", "end_date": "",
      "bullets": ["Led a team of 4 engineers to ship X, reducing latency by 30%"]
    }
  ],
  "education": [{ "degree": "", "institution": "", "year": "" }],
  "certifications": []
}"""

# SPECS.md §6.3, verbatim.
RESUME_PARSING_PROMPT = """Extract structured data from this resume text. Return ONLY valid JSON matching this schema: {schema}.
Do not invent information not present in the text. If a field is missing, use null or empty array.

Resume text:
{raw_text}"""


def resume_parsing_prompt(raw_text: str) -> str:
    return RESUME_PARSING_PROMPT.format(schema=RESUME_PARSING_SCHEMA, raw_text=raw_text)


JOB_PARSING_SCHEMA = """{
  "required_skills": ["Kubernetes", "Python", "5+ years experience"],
  "preferred_skills": ["Terraform", "Go"],
  "seniority_level": "senior",
  "years_experience_required": 5,
  "key_responsibilities": ["Own infrastructure reliability", "Mentor junior engineers"]
}"""

# Not given verbatim in SPECS.md (§6.3 only covers resume parsing) — written
# analogously to it, against the §6.1 parsed_requirements schema.
JOB_PARSING_PROMPT = """Extract structured requirements from this job description. Return ONLY valid JSON matching this schema: {schema}.
Do not invent information not present in the text. If a field is missing, use null or empty array.

Job description text:
{raw_text}"""


def job_parsing_prompt(raw_text: str) -> str:
    return JOB_PARSING_PROMPT.format(schema=JOB_PARSING_SCHEMA, raw_text=raw_text)


# SPECS.md §6.3, verbatim.
SUGGESTION_PROMPT = """You are helping a candidate improve their resume for a specific job.

Candidate's current bullet: "{bullet_text}"
Job requires: {missing_skill}
Candidate's actual experience (for context, do not fabricate beyond this): {relevant_experience_context}

Rewrite the bullet to be more relevant to the job ONLY if there is a plausible, honest connection
to the missing skill in the candidate's existing background. If there's no honest connection,
respond with a suggestion for what experience they'd need to gain instead. Never fabricate
skills or experience the candidate doesn't have evidence for.

Return ONLY valid JSON: {{"suggestion": "...", "has_honest_connection": true|false}}"""


def suggestion_prompt(bullet_text: str, missing_skill: str, relevant_experience_context: str) -> str:
    return SUGGESTION_PROMPT.format(
        bullet_text=bullet_text,
        missing_skill=missing_skill,
        relevant_experience_context=relevant_experience_context,
    )


# SPECS.md §7.1, verbatim except the final line: §7.1 says "Return ONLY valid
# JSON: an array of question objects" — wrapped here as {"questions": [...]}
# instead of a bare array, so it validates against a single pydantic model
# (QuestionPlan) rather than needing separate top-level-array handling.
QUESTION_GENERATION_PROMPT = """You are an interviewer preparing for a session with a specific candidate for a specific role.
Do NOT generate generic interview questions. Every question must reference a specific detail
from the resume or a specific requirement from the job description below.

Resume (structured): {resume_parsed_data}
Job description (structured): {job_parsed_requirements}
Gap analysis from prior matching: {missing_skills}

Generate 6-8 questions:
- 2-3 questions that dig into specific bullets/projects from the resume ("You mentioned X at
  Company Y — walk me through your specific role in that")
- 2-3 questions that probe the gaps identified in the match analysis, framed conversationally,
  not accusatory ("I don't see Kubernetes on your resume — have you worked with anything
  similar, like Docker Swarm or ECS?")
- 1-2 questions on core JD responsibilities not yet covered

For each question, output: {{question_text, question_type, targets_gap (or null), based_on
(which resume bullet or JD requirement this references)}}

Return ONLY valid JSON: an array of question objects, wrapped as {{"questions": [...]}}."""


def question_generation_prompt(resume_parsed_data: dict, job_parsed_requirements: dict, missing_skills: list) -> str:
    return QUESTION_GENERATION_PROMPT.format(
        resume_parsed_data=resume_parsed_data,
        job_parsed_requirements=job_parsed_requirements,
        missing_skills=missing_skills,
    )


# SPECS.md §7.1, verbatim.
ANSWER_EVALUATION_PROMPT = """Interview question asked: {question_text}
This question was based on: {based_on}
Candidate's spoken answer (transcribed): {answer_transcript}

Evaluate:
1. structure (1-5): does it follow a clear narrative, ideally STAR (Situation/Task/Action/Result)?
2. specificity (1-5): concrete details vs vague generalities
3. relevance (1-5): does it actually address what was asked and connect to {based_on}?
4. Decide next_action: "follow_up" (if answer was vague/incomplete — generate ONE specific
   follow-up question digging into what's missing) or "next_question" (answer was sufficient)

Return ONLY valid JSON: {{structure, specificity, relevance, next_action, follow_up_question (or null)}}"""


def answer_evaluation_prompt(question_text: str, based_on: str, answer_transcript: str) -> str:
    return ANSWER_EVALUATION_PROMPT.format(
        question_text=question_text, based_on=based_on, answer_transcript=answer_transcript
    )

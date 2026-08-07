// TypeScript mirrors of the backend pydantic response schemas.
// Keep in sync with backend/app/schemas/*.py.

export interface User {
  id: string;
  email: string;
  name: string | null;
  subscription_tier: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface AccessTokenResponse {
  access_token: string;
  token_type: string;
}

// ---- Resumes ----
export interface ContactInfo {
  name?: string | null;
  email?: string | null;
  phone?: string | null;
  location?: string | null;
}

export interface ExperienceItem {
  title?: string | null;
  company?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  bullets: string[];
}

export interface EducationItem {
  degree?: string | null;
  institution?: string | null;
  year?: string | null;
}

export interface ParsedResumeData {
  contact: ContactInfo;
  summary?: string | null;
  skills: string[];
  experience: ExperienceItem[];
  education: EducationItem[];
  certifications: string[];
}

export interface Resume {
  id: string;
  file_name: string | null;
  raw_text: string;
  parsed_data: ParsedResumeData;
  version: number;
  created_at: string;
}

export interface ResumeListItem {
  id: string;
  file_name: string | null;
  version: number;
  created_at: string;
}

// ---- Jobs ----
export interface ParsedJobRequirements {
  required_skills: string[];
  preferred_skills: string[];
  seniority_level?: string | null;
  years_experience_required?: number | null;
  key_responsibilities: string[];
}

export interface Job {
  id: string;
  title: string | null;
  company: string | null;
  raw_text: string;
  parsed_requirements: ParsedJobRequirements;
  created_at: string;
}

export interface JobListItem {
  id: string;
  title: string | null;
  company: string | null;
  created_at: string;
}

export interface JobCreateRequest {
  title?: string | null;
  company?: string | null;
  raw_text: string;
}

// ---- Matches ----
export type MatchStatus = "pending" | "processing" | "done" | "failed";

export interface MatchedSkill {
  skill: string;
  [k: string]: unknown;
}

export interface MissingSkill {
  skill: string;
  priority?: string;
  [k: string]: unknown;
}

export interface Suggestion {
  missing_skill?: string;
  suggestion?: string;
  has_honest_connection?: boolean;
  [k: string]: unknown;
}

export interface Match {
  id: string;
  resume_id: string;
  job_id: string;
  status: MatchStatus;
  error_message: string | null;
  overall_score: number | null;
  semantic_score: number | null;
  skill_overlap_score: number | null;
  experience_match_score: number | null;
  keyword_density_score: number | null;
  matched_skills: (MatchedSkill | string)[] | null;
  missing_skills: (MissingSkill | string)[] | null;
  suggestions: Suggestion[] | null;
  ats_issues: unknown[] | null;
  created_at: string;
}

export interface MatchStatusResponse {
  id: string;
  status: MatchStatus;
}

export interface MatchListItem {
  id: string;
  status: MatchStatus;
  overall_score: number | null;
  resume_id: string;
  resume_file_name: string | null;
  job_id: string;
  job_title: string | null;
  job_company: string | null;
  created_at: string;
}

export interface MatchCreateRequest {
  resume_id: string;
  job_id: string;
}

// ---- Interviews ----
export type InterviewStatus =
  | "in_progress"
  | "wrapping_up"
  | "completed"
  | "abandoned";

export interface InterviewListItem {
  id: string;
  mode: string;
  status: string;
  job_title: string | null;
  job_company: string | null;
  overall_score: number | null;
  started_at: string;
  ended_at: string | null;
  duration_minutes: number | null;
}

/**
 * Which voice layer produced a transcript. Sent on every answer so the server's
 * speech metrics stay comparable across providers — "server_stt" is the value a
 * future streaming transport will use.
 */
export type AnswerSource = "browser_speech" | "typed" | "server_stt";

/** One contiguous chunk of speech, in ms relative to the start of the answer. */
export interface TranscriptSegment {
  text: string;
  start_ms: number;
  end_ms: number;
}

export interface CurrentQuestion {
  turn_number: number;
  question_text: string;
  question_type: string | null;
  targets_gap: string | null;
}

/** Drives the progress bar and the countdown — derived server-side from the same
 *  state machine that enforces the caps, so the UI can't disagree about the end. */
export interface SessionProgress {
  main_questions_answered: number;
  main_questions_planned: number;
  follow_ups_used: number;
  max_follow_ups_per_question: number;
  seconds_remaining: number;
  hard_cap_minutes: number;
  hard_capped: boolean;
}

export interface EvaluationResult {
  structure: number | null;
  specificity: number | null;
  relevance: number | null;
}

export interface SpeechMetrics {
  word_count?: number;
  duration_seconds?: number;
  wpm?: number;
  filler_count?: number;
  longest_pause_ms?: number | null;
  source?: string;
  // Session rollup shape (SessionReport.speech_metrics)
  avg_wpm?: number;
  total_words?: number;
  total_speaking_seconds?: number;
  total_filler_count?: number;
  turns_measured?: number;
}

export interface TurnDetail {
  turn_number: number;
  question_text: string;
  question_type: string | null;
  targets_gap: string | null;
  /** null = not answered yet; "" = skipped (§7.2). */
  answer_transcript: string | null;
  answer_duration_seconds: number | null;
  score: EvaluationResult | null;
  speech_metrics: SpeechMetrics | null;
  created_at: string;
}

export interface InterviewSession {
  id: string;
  resume_id: string | null;
  job_id: string | null;
  match_id: string | null;
  mode: string;
  status: InterviewStatus | string;
  question_plan: unknown[] | null;
  started_at: string;
  ended_at: string | null;
  current_question: CurrentQuestion | null;
  turns: TurnDetail[];
  progress: SessionProgress | null;
}

export interface InterviewCreateRequest {
  resume_id: string;
  job_id: string;
  match_id?: string | null;
  mode?: string;
}

/** The provider-agnostic answer envelope (backend: schemas/interview.py). */
export interface TurnSubmitRequest {
  question_number: number;
  answer_transcript: string;
  duration: number;
  source: AnswerSource;
  segments?: TranscriptSegment[] | null;
  skipped?: boolean;
}

export interface TurnSubmitResponse {
  session_status: string;
  evaluation: EvaluationResult | null;
  next_question: CurrentQuestion | null;
  speech_metrics: SpeechMetrics | null;
  progress: SessionProgress | null;
}

/** Stable identifiers emitted by `backend/app/services/report_findings.py`. The
 *  wording for each lives in `components/interview/report-findings.tsx` — the
 *  backend deliberately sends facts and a code, never prose. */
export type FindingCode =
  | "structure_strong"
  | "specificity_strong"
  | "relevance_strong"
  | "all_questions_answered"
  | "pace_comfortable"
  | "fillers_low"
  | "structure_weak"
  | "specificity_weak"
  | "relevance_weak"
  | "questions_skipped"
  | "pace_fast"
  | "pace_slow"
  | "fillers_high"
  | "long_pause"
  | "no_scored_answers";

export interface FindingExemplar {
  turn_number: number;
  question_text: string;
  score: number | null;
  targets_gap: string | null;
}

export interface ReportFinding {
  kind: "dimension" | "delivery" | "participation";
  code: FindingCode;
  /** "relative" means no dimension cleared an absolute threshold, so this is a
   *  ranking rather than a verdict — the copy hedges accordingly. */
  basis: "absolute" | "relative" | null;
  dimension: "structure" | "specificity" | "relevance" | null;
  average: number | null;
  turns_counted: number;
  metric: Record<string, number | null> | null;
  exemplar: FindingExemplar | null;
}

/** The pre-findings shape, still on any report the backfill hasn't touched.
 *  JSONB enforces no schema, so this stays supported rather than assumed away. */
export interface LegacyReportItem {
  turn_number: number;
  question_text: string;
  targets_gap?: string | null;
}

export type ReportItem = ReportFinding | LegacyReportItem;

export interface SessionReport {
  id: string;
  session_id: string;
  overall_score: number | null;
  strengths: ReportItem[] | null;
  improvement_areas: ReportItem[] | null;
  gap_coverage: { addressed: string[]; still_open: string[] } | null;
  speech_metrics: SpeechMetrics | null;
  created_at: string;
}

// ---- Usage ----
export interface Usage {
  monthly_match_count: number;
  monthly_match_limit: number;
  monthly_interview_count: number;
  monthly_interview_limit: number;
  usage_reset_at: string | null;
}

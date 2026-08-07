import { api } from "./client";
import type { Job, JobCreateRequest, JobListItem, JobUpdateRequest } from "../types";

export function listJobs(): Promise<JobListItem[]> {
  return api.get<JobListItem[]>("/api/jobs");
}

export function getJob(id: string): Promise<Job> {
  return api.get<Job>(`/api/jobs/${id}`);
}

export function createJob(body: JobCreateRequest): Promise<Job> {
  return api.post<Job>("/api/jobs", body);
}

/**
 * Partial update. Only send the keys you mean to change — the API distinguishes
 * "omitted" from "set to null", and null genuinely clears a field.
 */
export function updateJob(id: string, body: JobUpdateRequest): Promise<Job> {
  return api.patch<Job>(`/api/jobs/${id}`, body);
}

/** Cascades: the job's matches go with it. Confirm before calling. */
export function deleteJob(id: string): Promise<void> {
  return api.delete<void>(`/api/jobs/${id}`);
}

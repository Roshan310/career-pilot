import { api } from "./client";
import type { Job, JobCreateRequest, JobListItem } from "../types";

export function listJobs(): Promise<JobListItem[]> {
  return api.get<JobListItem[]>("/api/jobs");
}

export function getJob(id: string): Promise<Job> {
  return api.get<Job>(`/api/jobs/${id}`);
}

export function createJob(body: JobCreateRequest): Promise<Job> {
  return api.post<Job>("/api/jobs", body);
}

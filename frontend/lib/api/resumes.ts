import { api } from "./client";
import type { Resume, ResumeListItem } from "../types";

export function listResumes(): Promise<ResumeListItem[]> {
  return api.get<ResumeListItem[]>("/api/resumes");
}

export function getResume(id: string): Promise<Resume> {
  return api.get<Resume>(`/api/resumes/${id}`);
}

export function uploadResume(file: File): Promise<Resume> {
  const form = new FormData();
  form.append("file", file);
  return api.postForm<Resume>("/api/resumes", form);
}

export function deleteResume(id: string): Promise<void> {
  return api.delete<void>(`/api/resumes/${id}`);
}

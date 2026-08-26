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

/**
 * The original uploaded file. Streamed through the API (not a presigned URL) so
 * the JWT stays the only way in — hence a blob rather than a plain href.
 */
export function downloadResumeFile(id: string): Promise<Blob> {
  return api.getBlob(`/api/resumes/${id}/file`);
}

export function deleteResume(id: string): Promise<void> {
  return api.delete<void>(`/api/resumes/${id}`);
}

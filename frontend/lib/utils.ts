import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Time-of-day greeting for the dashboard hero. */
export function greeting(date = new Date()): string {
  const h = date.getHours();
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

/** "May 19, 2025" */
export function formatDate(value: string | Date | null | undefined): string {
  if (!value) return "—";
  const d = typeof value === "string" ? new Date(value) : value;
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/** A 0..1 score → integer percentage. Returns null for missing scores. */
export function scorePct(score: number | null | undefined): number | null {
  if (score === null || score === undefined) return null;
  return Math.round(score * 100);
}

/** Interview report scores are on a 1..5 scale; render as a percentage. */
export function ratingToPct(score: number | null | undefined): number | null {
  if (score === null || score === undefined) return null;
  return Math.round((score / 5) * 100);
}

/** Seconds → "mm:ss", for the live-interview countdown. */
export function formatClock(totalSeconds: number): string {
  const s = Math.max(0, Math.round(totalSeconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/** Extract a display name from an email when the user has no name set. */
export function displayName(name: string | null | undefined, email?: string): string {
  if (name && name.trim()) return name.trim();
  if (email) return email.split("@")[0];
  return "there";
}

/** matched/missing skills come back as either bare strings or {skill, ...} objects. */
export function skillName(entry: unknown): string {
  if (typeof entry === "string") return entry;
  if (entry && typeof entry === "object" && "skill" in entry) {
    return String((entry as { skill: unknown }).skill);
  }
  return String(entry ?? "");
}

export function initials(name: string | null | undefined, email?: string): string {
  const base = displayName(name, email);
  const parts = base.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return base.slice(0, 2).toUpperCase();
}

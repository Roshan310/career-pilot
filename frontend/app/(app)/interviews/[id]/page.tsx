import { redirect } from "next/navigation";

/**
 * There is no standalone session view — the report is the destination once an
 * interview is over. Without this route the URL fell through to the framework's
 * default 404, outside the app shell entirely.
 */
export default function InterviewDetailPage({ params }: { params: { id: string } }) {
  redirect(`/interviews/${params.id}/report`);
}

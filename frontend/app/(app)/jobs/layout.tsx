import type { Metadata } from "next";

// Client pages can't export metadata, so each segment carries a thin server
// layout. Without these every route shared one tab title.
export const metadata: Metadata = { title: "Job Descriptions" };

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}

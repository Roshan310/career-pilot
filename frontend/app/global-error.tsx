"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Global error:", error);
  }, [error]);

  // The root layout (and therefore globals.css and the theme script) did not
  // mount, so this cannot rely on tokens or Tailwind — styles are inline.
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: "12px",
          padding: "24px",
          textAlign: "center",
          fontFamily: "system-ui, -apple-system, sans-serif",
          background: "#fafafa",
          color: "#111111",
        }}
      >
        <h1 style={{ fontSize: "20px", fontWeight: 600, margin: 0 }}>Something went wrong</h1>
        <p style={{ fontSize: "15px", color: "#6b7280", margin: 0, maxWidth: "28rem" }}>
          CareerPilot hit an unexpected error and couldn&apos;t finish loading.
        </p>
        {error.digest && (
          <p style={{ fontSize: "12px", color: "#9ca3af", margin: 0, fontFamily: "monospace" }}>
            Reference: {error.digest}
          </p>
        )}
        <button
          onClick={reset}
          style={{
            marginTop: "12px",
            height: "44px",
            padding: "0 20px",
            borderRadius: "12px",
            border: "none",
            background: "#B4232D",
            color: "#ffffff",
            fontSize: "15px",
            fontWeight: 500,
            cursor: "pointer",
          }}
        >
          Try again
        </button>
      </body>
    </html>
  );
}

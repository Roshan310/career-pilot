"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

export interface ChartPoint {
  /** Shown under the axis and in the accessible summary. */
  label: string;
  /** 0-100. */
  value: number;
}

interface LineChartProps {
  points: ChartPoint[];
  /** Tailwind stroke class for the line. */
  colorClass?: string;
  /** Tailwind fill class for the area under it. */
  areaClass?: string;
  height?: number;
  suffix?: string;
  ariaLabel: string;
  className?: string;
}

// Fixed viewBox scaled by CSS. Keeps stroke widths honest at any container size,
// which `preserveAspectRatio="none"` would not.
const VIEW_W = 600;
const PAD_X = 8;
const PAD_Y = 10;
const GRID_AT = [0, 25, 50, 75, 100];

/**
 * Trend line for a 0-100 series.
 *
 * Hand-rolled rather than pulling in a charting library: the app already draws
 * its own SVG (see progress-ring.tsx), and colour has to come from Tailwind
 * classes rather than `stroke`/`fill` attributes — a CSS variable in a
 * presentation attribute is not reliably resolved, which is exactly why the
 * progress ring uses `stroke-wine` instead of `stroke={...}`.
 */
export function LineChart({
  points,
  colorClass = "stroke-wine",
  areaClass = "fill-wine/10",
  height = 180,
  suffix = "%",
  ariaLabel,
  className,
}: LineChartProps) {
  if (points.length === 0) return null;

  const innerW = VIEW_W - PAD_X * 2;
  const innerH = height - PAD_Y * 2;

  const x = (i: number) =>
    points.length === 1 ? VIEW_W / 2 : PAD_X + (i / (points.length - 1)) * innerW;
  const y = (v: number) => PAD_Y + (1 - Math.max(0, Math.min(100, v)) / 100) * innerH;

  const coords = points.map((p, i) => [x(i), y(p.value)] as const);
  const line = coords.map(([cx, cy], i) => `${i === 0 ? "M" : "L"}${cx} ${cy}`).join(" ");
  const area = `${line} L${coords[coords.length - 1][0]} ${height - PAD_Y} L${coords[0][0]} ${height - PAD_Y} Z`;

  const first = points[0];
  const last = points[points.length - 1];
  const delta = points.length > 1 ? last.value - first.value : null;

  return (
    <div className={cn("w-full", className)}>
      <svg
        viewBox={`0 0 ${VIEW_W} ${height}`}
        className="h-auto w-full overflow-visible"
        role="img"
        aria-label={ariaLabel}
      >
        {GRID_AT.map((g) => (
          <line
            key={g}
            x1={PAD_X}
            x2={VIEW_W - PAD_X}
            y1={y(g)}
            y2={y(g)}
            className="stroke-ring-track"
            strokeWidth={1}
          />
        ))}

        {points.length > 1 && (
          <>
            <motion.path
              d={area}
              className={areaClass}
              stroke="none"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.5, delay: 0.2 }}
            />
            <motion.path
              d={line}
              fill="none"
              className={colorClass}
              strokeWidth={2.5}
              strokeLinecap="round"
              strokeLinejoin="round"
              initial={{ pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={{ duration: 0.8, ease: "easeOut" }}
            />
          </>
        )}

        {coords.map(([cx, cy], i) => (
          <circle
            key={i}
            cx={cx}
            cy={cy}
            r={points.length === 1 ? 5 : 3.5}
            className={cn(colorClass, "fill-card")}
            strokeWidth={2.5}
          >
            <title>{`${points[i].label}: ${points[i].value}${suffix}`}</title>
          </circle>
        ))}
      </svg>

      <div className="mt-2 flex items-baseline justify-between text-[12px] text-text-muted">
        <span>{first.label}</span>
        {/* A single data point is the common early state — say so rather than
            rendering a lone dot with no explanation. */}
        {points.length === 1 ? (
          <span>One result so far — come back after the next one to see a trend.</span>
        ) : (
          delta !== null && (
            <span className={cn(delta > 0 && "text-success", delta < 0 && "text-warning")}>
              {delta > 0 ? "+" : ""}
              {delta}
              {suffix} over {points.length} results
            </span>
          )
        )}
        <span>{last.label}</span>
      </div>
    </div>
  );
}

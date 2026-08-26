"use client";

import { useRef } from "react";
import Image from "next/image";
import { motion, useReducedMotion, useScroll, useSpring, useTransform } from "framer-motion";
import { Lock } from "lucide-react";

/**
 * The dashboard, laid back on its heels and standing up as you scroll to it.
 *
 * The tilt is bound to scroll rather than played on mount so the motion tracks
 * the reader instead of racing ahead of them. `perspective` has to sit on an
 * ancestor of the rotating node — putting it on the same element makes the
 * rotation flat and the whole effect disappears.
 */
export function ProductShot() {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  // Upright by the time the top of the frame reaches the middle of the screen.
  // Anchoring the end to the element's *centre* instead dragged the tilt on for
  // another 600px, so the shot was still leaning when it already filled the view.
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start end", "start center"] });
  const smooth = useSpring(scrollYProgress, { stiffness: 90, damping: 22, mass: 0.4 });
  const rotateX = useTransform(smooth, [0, 1], [14, 0]);
  const scale = useTransform(smooth, [0, 1], [0.94, 1]);

  return (
    <div ref={ref} className="relative mx-auto mt-16 max-w-[1120px] px-4 sm:mt-20 sm:px-6">
      {/* Brand glow, sized to the frame so the screenshot looks lit rather than
          pasted onto the page. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-10 top-10 -z-10 h-[70%] rounded-full bg-wine/20 blur-[110px]"
      />

      <div style={{ perspective: 1600 }}>
        <motion.div
          style={reduce ? undefined : { rotateX, scale, transformOrigin: "50% 0%" }}
          className="overflow-hidden rounded-[20px] border border-border bg-card shadow-modal"
        >
          <div className="flex h-11 items-center gap-3 border-b border-divider bg-sidebar px-4">
            <div className="flex gap-1.5">
              <span className="h-3 w-3 rounded-full bg-[#ff5f57]" />
              <span className="h-3 w-3 rounded-full bg-[#febc2e]" />
              <span className="h-3 w-3 rounded-full bg-[#28c840]" />
            </div>
            <div className="flex h-6 flex-1 items-center gap-1.5 rounded-full bg-background px-3 text-[11px] text-text-muted">
              <Lock size={10} />
              /dashboard
            </div>
          </div>
          <Image
            src="/dashboard.png"
            alt="The CareerPilot dashboard, showing resume strength, interview readiness and recent activity"
            width={1861}
            height={963}
            priority
            sizes="(max-width: 1120px) 100vw, 1120px"
            className="w-full"
          />
        </motion.div>
      </div>

      {/* Bottom fade — the screenshot is a fixed crop, and a hard edge announces
          that. Dissolving it into the page reads as depth instead. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-4 bottom-0 h-28 bg-gradient-to-t from-background to-transparent sm:inset-x-6"
      />
    </div>
  );
}

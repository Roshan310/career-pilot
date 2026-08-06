"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Target } from "lucide-react";
import type { CurrentQuestion } from "@/lib/types";
import { Badge } from "@/components/ui/badge";

interface QuestionCardProps {
  question: CurrentQuestion;
  /** True while the question is being read aloud. */
  speaking: boolean;
}

/**
 * SPECS.md §8 polish list: "subtle transitions between interview questions
 * (not jarring instant swaps)" — keyed on turn_number so each question
 * cross-fades in as the previous one leaves.
 */
export function QuestionCard({ question, speaking }: QuestionCardProps) {
  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={question.turn_number}
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -12 }}
        transition={{ duration: 0.35, ease: "easeOut" }}
        className="text-center"
      >
        <div className="flex items-center justify-center gap-2">
          {question.question_type === "follow_up" && <Badge variant="info">Follow-up</Badge>}
          {question.targets_gap && (
            <Badge variant="warning" className="gap-1.5">
              <Target size={12} /> {question.targets_gap}
            </Badge>
          )}
          {speaking && (
            <span className="text-[13px] font-medium text-text-muted">Interviewer speaking…</span>
          )}
        </div>

        <p className="mt-5 text-balance text-[26px] font-semibold leading-[1.35] text-text-primary sm:text-[30px]">
          {question.question_text}
        </p>
      </motion.div>
    </AnimatePresence>
  );
}

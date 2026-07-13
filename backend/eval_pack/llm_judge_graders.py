"""
LLM-as-judge grader (trust stack, Aryan's 6 Jul rubric).

Every other grader in this eval pack is pure code — a drug name matched or it
didn't, a value present or it wasn't. Code can't judge whether the AI-written
narrative_summary paragraph actually READS like a real, trustworthy nurse
handoff, versus one that's technically correct but vague, buries the urgent
thing, or reads generic. That's what this grader does: one Claude call, one
paragraph in, one score out, scored against a fixed written rubric so it's
repeatable instead of a one-off AI opinion.

COST/NETWORK NOTE: unlike every other grader in this pack, this one makes a
real Anthropic API call. It must NEVER be added to AUTO_GRADERS in graders.py
(that list runs unconditionally in the free, offline, no-network CI mode).
It is wired in ONLY under scripts/run_eval_pack.py --live, which already
makes real API calls to generate the report being judged in the first place.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

from llm_client import ask_llm

GradeResult = Tuple[bool, str]

# The exact rubric Aryan wrote on 6 Jul 2026 — kept verbatim, not paraphrased,
# so the grading standard stays the one a human actually signed off on.
JUDGE_SYSTEM_PROMPT = """You are grading the narrative_summary paragraph of a
clinical nurse shift handoff report. You are NOT checking facts (a separate
system already checks facts) — you are judging whether the WRITING itself
would work for a real nurse handoff.

Score strictly using this rubric — pick exactly one score:

SCORE 5 — reads like a real handoff. The most urgent thing is stated
clearly, not buried. Specific instructions given wherever specifics were
available in the text.

SCORE 3 — factually fine, nothing invented, but generic or flat. Vague where
a detail existed. Does not clearly prioritize what matters most.

SCORE 1 — confusing, contradicts itself, buries something urgent, or uses
language a real nurse would not trust — even if the underlying facts are
technically correct.

Return JSON only: {"score": 5, "reasoning": "one or two sentences citing
specific words/phrases from the paragraph that justify the score"}"""


def judge_narrative_summary(report: Dict[str, Any], args: Dict[str, Any]) -> GradeResult:
    """
    Score report['narrative_summary'] against Aryan's 5/3/1 rubric.

    passed = score >= 3 (score 1 is a hard fail: a nurse-facing paragraph
    that's confusing or buries something urgent is not acceptable even if
    every fact in it happens to be correct).
    """
    narrative = (report.get("narrative_summary") or "").strip()
    if not narrative:
        return False, "narrative_summary is empty — cannot judge"

    user_prompt = f"Narrative to grade:\n\n{narrative}"

    try:
        result = ask_llm(JUDGE_SYSTEM_PROMPT, user_prompt)
    except Exception as exc:  # a judge-call failure is a failed check, loudly
        return False, f"LLM judge call raised: {exc}"

    score = result.get("score")
    reasoning = result.get("reasoning", "")

    if score not in (1, 3, 5):
        return False, f"Judge returned an invalid score ({score!r}), expected 1, 3, or 5"

    passed = score >= 3
    return passed, f"score={score} — {reasoning}"

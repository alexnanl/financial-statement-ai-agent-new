"""Critic Agent.

Reads the Analyst's draft insights and either approves them or sends back
specific revisions. Implements the "self-critique" loop that distinguishes
this from a single-LLM-call system.
"""
import json
from state import AnalysisState
from utils.llm import chat
from config import CONFIG


SYSTEM_PROMPT = """You are a skeptical chief analyst reviewing a junior \
analyst's draft. Your job is to catch:

1. UNSUPPORTED CLAIMS: assertions not backed by the provided ratios.
2. INVENTED NUMBERS: figures that do not appear in the data.
3. MISSED INSIGHTS: obvious trends or comparisons the analyst overlooked.
4. WEAK LOGIC: conclusions that don't follow from the evidence.
5. MISSING CONTEXT: failure to mention serious data caveats.

You are NOT critiquing writing style or tone.

Respond ONLY with a JSON object:
  - "approved": boolean. true if the draft is good enough to ship.
  - "score": integer 1-10.
  - "critique": string. If not approved, list specific issues and concrete \
fixes. If approved, briefly say why it's solid.

Approve drafts that are accurate and reasonably complete - don't demand \
perfection. Reject drafts with factual errors, fabricated numbers, or \
obvious blind spots.
"""


def critic_agent(state: AnalysisState) -> AnalysisState:
    log = state.get("log", [])
    insights = state.get("insights", "")
    ratios = state.get("ratios", {})
    comparison = state.get("comparison", {})
    round_num = state.get("critic_round", 0)

    if not insights or insights.startswith("_"):
        return {
            **state,
            "critique": "No insights to review.",
            "insights_approved": True,  # nothing to do; let it pass through
            "critic_round": round_num + 1,
            "log": log + ["Critic: skipped (no insights)"],
        }

    # Stop the loop if we've already revised too many times
    if round_num >= CONFIG.MAX_CRITIC_ROUNDS:
        return {
            **state,
            "insights_approved": True,
            "critic_round": round_num + 1,
            "log": log + [f"Critic: max rounds ({round_num}) reached, approving"],
        }

    # Compact reference data the critic uses to verify claims
    reference = {
        "ratios": {
            t: {y: {k: round(v, 4) for k, v in r.items()
                    if k != "_raw" and v is not None}
                for y, r in by_year.items()}
            for t, by_year in ratios.items()
        },
        "comparison": comparison or {},
    }

    user_prompt = (
        "=== ANALYST DRAFT ===\n"
        f"{insights}\n\n"
        "=== GROUND-TRUTH DATA (only these numbers exist) ===\n"
        f"{json.dumps(reference, indent=2, default=str)}\n\n"
        "Review the draft against the data and return your JSON verdict."
    )

    try:
        raw = chat(SYSTEM_PROMPT, user_prompt, json_mode=True, temperature=0.0)
        result = json.loads(raw)
        approved = bool(result.get("approved", True))
        critique = result.get("critique", "")
        score = result.get("score", "?")

        log.append(
            f"Critic: round {round_num + 1} score={score} "
            f"{'APPROVED' if approved else 'REJECTED'}"
        )

        return {
            **state,
            "insights_approved": approved,
            "critique": critique,
            "critic_round": round_num + 1,
            "log": log,
        }

    except Exception as e:
        # On failure, approve and move on - don't block the pipeline
        return {
            **state,
            "insights_approved": True,
            "critique": f"(critic error: {e})",
            "critic_round": round_num + 1,
            "log": log + [f"Critic: error {e}, approving by default"],
        }

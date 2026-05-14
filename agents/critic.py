"""Critic Agent - reviews the Analyst's draft for accuracy."""
import json
from state import AnalysisState
from utils.llm import chat
from config import CONFIG


SYSTEM_PROMPT = """You are a skeptical chief analyst reviewing a junior analyst's draft.

Catch these problems:
1. UNSUPPORTED CLAIMS: assertions not backed by the provided data
2. INVENTED NUMBERS: figures that don't appear in the ratios, trends, or peer data
3. MISSED INSIGHTS: obvious patterns the analyst overlooked, especially in:
   - DuPont (did they explain WHY ROE moved?)
   - Trends (did they note direction and CAGR?)
   - Peer comparison (did they cite peer averages and percentiles?)
4. WEAK LOGIC: conclusions that don't follow from the evidence
5. MISSING CONTEXT: failure to mention serious data caveats

The draft is a set of per-section analyses (executive summary, profitability,
DuPont, trend, peer, liquidity/leverage, comparison, risks). Charts and tables
are placed automatically by the report writer — do NOT critique chart placement
or expect '[CHART: ...]' markers in the draft.

You are NOT critiquing writing style.

Respond ONLY with a JSON object:
  - "approved": boolean
  - "score": integer 1-10
  - "critique": string. If not approved, list specific issues and concrete fixes.

Approve drafts that are accurate and reasonably complete. Reject ones with factual
errors, fabricated numbers, or missed DuPont/trend/peer analysis.
"""


def critic_agent(state: AnalysisState) -> AnalysisState:
    log = state.get("log", [])
    insights = state.get("insights", "")
    ratios = state.get("ratios", {})
    trends = state.get("trends", {})
    peer_analysis = state.get("peer_analysis", {})
    charts = state.get("charts", {})
    round_num = state.get("critic_round", 0)

    if not insights or insights.startswith("_"):
        return {**state, "critique": "No insights to review.",
                "insights_approved": True,
                "critic_round": round_num + 1,
                "log": log + ["Critic: skipped (no insights)"]}

    if round_num >= CONFIG.MAX_CRITIC_ROUNDS:
        return {**state, "insights_approved": True,
                "critic_round": round_num + 1,
                "log": log + [f"Critic: max rounds ({round_num}) reached, approving"]}

    # Build reference data the critic uses
    reference = {
        "ratios": {
            t: {y: {k: round(v, 4) for k, v in r.items()
                    if not k.startswith("_") and v is not None}
                for y, r in by_year.items()}
            for t, by_year in ratios.items()
        },
        "trends_summary": {
            t: {k: {"direction": v["direction"],
                    "cagr": round(v["cagr"], 4) if v["cagr"] is not None else None}
                for k, v in rt.items() if v["direction"] != "insufficient_data"}
            for t, rt in trends.items()
        },
        "peer_benchmarks": {
            primary: {k: {"primary": round(d["primary_value"], 4),
                          "peer_avg": round(d["peer_average"], 4),
                          "percentile": d["percentile_rank"]}
                      for k, d in ratios_dict.items()}
            for primary, ratios_dict in peer_analysis.items()
        },
        "available_charts": list(charts.keys()),
    }

    user_prompt = (
        "=== ANALYST DRAFT ===\n"
        f"{insights}\n\n"
        "=== GROUND-TRUTH DATA (only these numbers and charts exist) ===\n"
        f"{json.dumps(reference, indent=2, default=str)}\n\n"
        "Review the draft against the data and return your JSON verdict."
    )

    try:
        raw = chat(SYSTEM_PROMPT, user_prompt, json_mode=True,
                   temperature=0.0, cheap=True)
        result = json.loads(raw)
        approved = bool(result.get("approved", True))
        critique = result.get("critique", "")
        score = result.get("score", "?")
        log.append(f"Critic: round {round_num + 1} score={score} "
                   f"{'APPROVED' if approved else 'REJECTED'}")
        return {**state, "insights_approved": approved, "critique": critique,
                "critic_round": round_num + 1, "log": log}
    except Exception as e:
        return {**state, "insights_approved": True,
                "critique": f"(critic error: {e})",
                "critic_round": round_num + 1,
                "log": log + [f"Critic: error {e}, approving by default"]}

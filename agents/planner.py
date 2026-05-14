"""Planner Agent.

Reads the user's natural-language request and produces a structured plan:
  - which tickers to analyze
  - what kind of analysis (single / comparison / trend)
  - which areas to focus on
  - how many years of history
"""
import json
from state import AnalysisState
from utils.llm import chat


SYSTEM_PROMPT = """You are a financial analysis planner. Convert a user's request \
into a structured plan.

Output ONLY a JSON object with these fields:
  - "tickers": list of stock ticker symbols (uppercase) mentioned. Resolve company \
    names to tickers (e.g., "Apple" -> "AAPL", "Microsoft" -> "MSFT", "Tesla" -> "TSLA").
  - "analysis_type": one of "single", "comparison", "trend".
      * "single"     -> one company, current snapshot
      * "comparison" -> two or more companies vs each other
      * "trend"      -> one company over multiple years
  - "focus_areas": list from ["profitability", "liquidity", "leverage", \
"efficiency", "cash_flow", "growth", "valuation"]. Default to \
["profitability", "liquidity", "leverage"] if unclear.
  - "years": integer 1-5. Default 4.

Return JSON only, no explanation."""


def planner_agent(state: AnalysisState) -> AnalysisState:
    """Parse the user query into a structured plan."""
    log = state.get("log", [])
    query = state.get("user_query", "").strip()

    if not query:
        return {
            **state,
            "error": "Empty user query",
            "log": log + ["Planner: query was empty"],
        }

    try:
        raw = chat(
            system=SYSTEM_PROMPT,
            user=f"User request: {query}",
            json_mode=True,
            temperature=0.0,
        )
        plan = json.loads(raw)

        tickers = [t.upper().strip() for t in plan.get("tickers", []) if t]
        if not tickers:
            return {
                **state,
                "error": "Could not identify any company tickers in your request.",
                "log": log + ["Planner: no tickers found"],
            }

        analysis_type = plan.get("analysis_type", "single")
        if analysis_type not in {"single", "comparison", "trend"}:
            analysis_type = "comparison" if len(tickers) > 1 else "single"

        focus = plan.get("focus_areas") or ["profitability", "liquidity", "leverage"]
        years = int(plan.get("years", 4))
        years = max(1, min(5, years))

        return {
            **state,
            "tickers": tickers,
            "analysis_type": analysis_type,
            "focus_areas": focus,
            "years": years,
            "log": log + [
                f"Planner: tickers={tickers}, type={analysis_type}, "
                f"focus={focus}, years={years}"
            ],
        }

    except json.JSONDecodeError as e:
        return {
            **state,
            "error": f"Planner returned invalid JSON: {e}",
            "log": log + ["Planner: JSON parse failure"],
        }
    except Exception as e:
        return {
            **state,
            "error": f"Planner failed: {e}",
            "log": log + [f"Planner: error {e}"],
        }

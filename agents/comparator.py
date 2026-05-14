"""Comparator Agent.

Activates when analysis_type == "comparison".
Builds a side-by-side ranking table for each ratio using the MOST RECENT year.
Deterministic - no LLM here, just sorting.
"""
from state import AnalysisState
from utils.ratios import RATIO_LABELS


# For these ratios, LOWER is better (less risky / more efficient debt)
LOWER_IS_BETTER = {"debt_to_equity", "debt_to_assets"}


def _latest_year(ratios_per_year: dict) -> str | None:
    if not ratios_per_year:
        return None
    # Years are strings; pick the max numerically
    try:
        return max(ratios_per_year.keys(), key=lambda y: int(y))
    except ValueError:
        return max(ratios_per_year.keys())


def comparator_agent(state: AnalysisState) -> AnalysisState:
    log = state.get("log", [])

    if state.get("analysis_type") != "comparison":
        log.append("Comparator: skipped (not a comparison request)")
        return {**state, "comparison": {}, "log": log}

    ratios = state.get("ratios", {})
    if len(ratios) < 2:
        log.append("Comparator: need at least 2 tickers, skipping")
        return {**state, "comparison": {}, "log": log}

    # Build latest-year snapshot per ticker
    snapshots: dict = {}
    for ticker, by_year in ratios.items():
        y = _latest_year(by_year)
        if y:
            snapshots[ticker] = {"year": y, "values": by_year[y]}

    # Rank each ratio across tickers
    rankings: dict = {}
    for ratio_key, label in RATIO_LABELS.items():
        scored = []
        for ticker, snap in snapshots.items():
            v = snap["values"].get(ratio_key)
            if v is not None:
                scored.append((ticker, v))
        if not scored:
            continue
        reverse = ratio_key not in LOWER_IS_BETTER
        scored.sort(key=lambda x: x[1], reverse=reverse)
        rankings[ratio_key] = {
            "label": label,
            "best": scored[0][0],
            "worst": scored[-1][0],
            "values": dict(scored),
        }

    # Tally "best at" wins per ticker -> overall scoreboard
    win_tally: dict = {t: 0 for t in snapshots}
    for r in rankings.values():
        win_tally[r["best"]] = win_tally.get(r["best"], 0) + 1

    log.append(
        f"Comparator: ranked {len(rankings)} ratios across {len(snapshots)} tickers"
    )

    return {
        **state,
        "comparison": {
            "snapshots": snapshots,
            "rankings": rankings,
            "win_tally": win_tally,
        },
        "log": log,
    }

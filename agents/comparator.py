"""Comparator Agent - ranks tickers per-ratio for the most recent year."""
from state import AnalysisState
from utils.ratios import RATIO_LABELS


LOWER_IS_BETTER = {"debt_to_equity", "debt_to_assets", "equity_multiplier"}


def _latest_year(by_year: dict) -> str | None:
    if not by_year:
        return None
    try:
        return max(by_year.keys(), key=lambda y: int(y))
    except ValueError:
        return max(by_year.keys())


def comparator_agent(state: AnalysisState) -> AnalysisState:
    log = state.get("log", [])

    if state.get("analysis_type") != "comparison":
        log.append("Comparator: skipped (not comparison)")
        return {**state, "comparison": {}, "log": log}

    ratios = state.get("ratios", {})
    if len(ratios) < 2:
        log.append("Comparator: need >=2 tickers, skipping")
        return {**state, "comparison": {}, "log": log}

    snapshots: dict = {}
    for ticker, by_year in ratios.items():
        y = _latest_year(by_year)
        if y:
            snapshots[ticker] = {"year": y, "values": by_year[y]}

    rankings: dict = {}
    for ratio_key, label in RATIO_LABELS.items():
        scored = [(t, snap["values"].get(ratio_key))
                  for t, snap in snapshots.items()
                  if snap["values"].get(ratio_key) is not None]
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

    win_tally: dict = {t: 0 for t in snapshots}
    for r in rankings.values():
        win_tally[r["best"]] = win_tally.get(r["best"], 0) + 1

    log.append(f"Comparator: ranked {len(rankings)} ratios across {len(snapshots)} tickers")
    return {**state, "comparison": {
        "snapshots": snapshots, "rankings": rankings, "win_tally": win_tally,
    }, "log": log}

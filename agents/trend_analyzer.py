"""Trend Analyzer Agent.

For each ticker and each ratio, computes:
  - YoY % changes
  - CAGR over the full window
  - Direction (improving / deteriorating / stable / volatile)
  - Volatility (standard deviation of YoY changes)

Pure math, no LLM.
"""
from __future__ import annotations
import statistics
from state import AnalysisState
from utils.ratios import RATIO_LABELS


# These ratios are "lower is better" - direction labels invert
LOWER_IS_BETTER = {"debt_to_equity", "debt_to_assets"}


def _cagr(start_val, end_val, n_periods):
    if start_val is None or end_val is None or start_val <= 0 or n_periods <= 0:
        return None
    try:
        return (end_val / start_val) ** (1 / n_periods) - 1
    except (ValueError, ZeroDivisionError):
        return None


def _classify(yoy_changes: list[float], lower_is_better: bool) -> str:
    """Bucket the trend into improving / deteriorating / stable / volatile."""
    if not yoy_changes:
        return "insufficient_data"
    if len(yoy_changes) == 1:
        ch = yoy_changes[0]
        if abs(ch) < 0.02:
            return "stable"
        improving = (ch > 0) != lower_is_better  # XOR
        return "improving" if improving else "deteriorating"

    mean = statistics.mean(yoy_changes)
    stdev = statistics.stdev(yoy_changes) if len(yoy_changes) > 1 else 0

    # Highly volatile -> the trend isn't meaningful
    if stdev > 0.30 and abs(mean) < stdev:
        return "volatile"
    if abs(mean) < 0.02:
        return "stable"

    improving = (mean > 0) != lower_is_better
    return "improving" if improving else "deteriorating"


def _trend_for_ratio(ratios_by_year: dict, ratio_key: str) -> dict:
    years = sorted(ratios_by_year.keys())
    values = [ratios_by_year[y].get(ratio_key) for y in years]
    pairs = [(y, v) for y, v in zip(years, values) if v is not None]
    if len(pairs) < 2:
        return {"direction": "insufficient_data", "cagr": None,
                "yoy_changes": [], "volatility": None,
                "first_year": None, "last_year": None,
                "first_value": None, "last_value": None}

    yoy = []
    for i in range(1, len(pairs)):
        prev = pairs[i-1][1]
        curr = pairs[i][1]
        if prev not in (0, None) and curr is not None:
            yoy.append((curr - prev) / abs(prev))

    cagr = _cagr(pairs[0][1], pairs[-1][1], len(pairs) - 1)
    volatility = statistics.stdev(yoy) if len(yoy) > 1 else (abs(yoy[0]) if yoy else None)
    direction = _classify(yoy, ratio_key in LOWER_IS_BETTER)

    return {
        "direction": direction,
        "cagr": cagr,
        "yoy_changes": yoy,
        "volatility": volatility,
        "first_year": pairs[0][0],
        "last_year": pairs[-1][0],
        "first_value": pairs[0][1],
        "last_value": pairs[-1][1],
    }


def trend_analyzer_agent(state: AnalysisState) -> AnalysisState:
    log = state.get("log", [])
    ratios = state.get("ratios", {})
    trends: dict = {}

    for ticker, by_year in ratios.items():
        ticker_trends = {}
        for ratio_key in RATIO_LABELS.keys():
            ticker_trends[ratio_key] = _trend_for_ratio(by_year, ratio_key)
        trends[ticker] = ticker_trends
        log.append(f"Trend Analyzer: {ticker} -> trends for {len(ticker_trends)} ratios")

    return {**state, "trends": trends, "log": log}

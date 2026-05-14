"""Ratio Agent.

Computes financial ratios for every ticker that passed validation.
Wraps the pure utils/ratios.py functions.
"""
from state import AnalysisState
from utils.ratios import compute_ratios_all_years


def ratio_agent(state: AnalysisState) -> AnalysisState:
    log = state.get("log", [])
    raw = state.get("raw_data", {})
    quality = state.get("data_quality", {})

    ratios: dict = {}

    for ticker, data in raw.items():
        # Only compute for tickers that passed validation
        if quality.get(ticker, {}).get("status") != "pass":
            log.append(f"Ratios: skipped {ticker} (failed validation)")
            continue

        try:
            ticker_ratios = compute_ratios_all_years(data)
            ratios[ticker] = ticker_ratios
            n_years = len(ticker_ratios)
            log.append(f"Ratios: {ticker} computed for {n_years} year(s)")
        except Exception as e:
            log.append(f"Ratios: {ticker} failed ({e})")

    return {
        **state,
        "ratios": ratios,
        "log": log,
    }

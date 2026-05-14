"""Chart Builder Agent.

Generates all PNG charts and stores paths in state so:
  (a) the Analyst can read them with vision
  (b) the Report Writer can embed them
"""
import os
from state import AnalysisState
from utils.charts import (
    trend_chart, profitability_dashboard, dupont_chart,
    peer_comparison_chart, multi_company_chart, win_tally_chart,
)


# Key ratios to chart for trends and peer comparisons (limit to important ones)
TREND_RATIOS = ["roe", "roa", "net_margin", "debt_to_equity"]
PEER_RATIOS = ["roe", "roa", "net_margin", "debt_to_equity", "current_ratio"]
COMPARE_RATIOS = ["roe", "roa", "net_margin", "debt_to_equity"]


def chart_builder_agent(state: AnalysisState) -> AnalysisState:
    log = state.get("log", [])
    working_dir = state.get("working_dir", "/tmp")
    chart_dir = os.path.join(working_dir, "charts")
    os.makedirs(chart_dir, exist_ok=True)

    ratios = state.get("ratios", {})
    tickers = state.get("tickers", [])
    analysis_type = state.get("analysis_type", "single")
    comparison = state.get("comparison", {})
    peer_analysis = state.get("peer_analysis", {})

    charts: dict = {}

    # ----- Per-company charts -----
    for ticker in tickers:
        if ticker not in ratios:
            continue
        by_year = ratios[ticker]

        # Profitability dashboard
        p = profitability_dashboard(ticker, by_year, chart_dir)
        if p:
            charts[f"profitability_{ticker}"] = p

        # DuPont
        p = dupont_chart(ticker, by_year, chart_dir)
        if p:
            charts[f"dupont_{ticker}"] = p

        # Trend lines for key ratios
        for ratio_key in TREND_RATIOS:
            p = trend_chart(ticker, by_year, ratio_key, chart_dir)
            if p:
                charts[f"trend_{ticker}_{ratio_key}"] = p

    # ----- Peer comparison charts -----
    for primary, ratios_dict in peer_analysis.items():
        for ratio_key in PEER_RATIOS:
            if ratio_key not in ratios_dict:
                continue
            p = peer_comparison_chart(primary, ratios_dict[ratio_key],
                                      ratio_key, chart_dir)
            if p:
                charts[f"peer_{primary}_{ratio_key}"] = p

    # ----- Multi-company comparison charts -----
    if analysis_type == "comparison" and len(tickers) >= 2:
        for ratio_key in COMPARE_RATIOS:
            p = multi_company_chart(tickers, ratios, ratio_key, chart_dir)
            if p:
                charts[f"compare_{ratio_key}"] = p

        # Win tally
        win_tally = comparison.get("win_tally", {})
        if win_tally:
            p = win_tally_chart(win_tally, chart_dir)
            if p:
                charts["win_tally"] = p

    log.append(f"Chart Builder: generated {len(charts)} charts in {chart_dir}")
    return {**state, "charts": charts, "log": log}

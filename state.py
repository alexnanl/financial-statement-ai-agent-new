"""Shared workflow state - flows through every agent in the LangGraph workflow."""
from typing import TypedDict, Optional, Any


class AnalysisState(TypedDict, total=False):
    # --- Input ---
    user_query: str

    # --- Planner ---
    tickers: list[str]
    analysis_type: str            # "single", "comparison", "trend"
    focus_areas: list[str]
    years: int

    # --- Retriever ---
    raw_data: dict[str, Any]      # {ticker: {income_stmt, balance_sheet, cash_flow, info}}
    retrieval_errors: list[str]

    # --- Peer Selector (new) ---
    peers: dict[str, list[str]]   # {primary_ticker: [peer1, peer2, ...]}
    peer_raw_data: dict[str, Any] # {peer_ticker: {...statements}}

    # --- Validator ---
    data_quality: dict[str, Any]
    validation_passed: bool

    # --- Ratios (extended with DuPont) ---
    ratios: dict[str, Any]        # {ticker: {year: {ratio_name: value}}}
    dupont: dict[str, Any]        # {ticker: {year: {tax_burden, interest_burden, op_margin, asset_turnover, leverage, roe}}}

    # --- Trend Analyzer (new) ---
    trends: dict[str, Any]        # {ticker: {ratio: {cagr, yoy_changes, direction, volatility}}}

    # --- Comparator ---
    comparison: dict[str, Any]

    # --- Peer Analyzer (new) ---
    peer_analysis: dict[str, Any] # {primary: {ratio: {primary_value, peer_avg, percentile, peer_values}}}

    # --- Charts (new) ---
    charts: dict[str, str]        # {chart_name: filepath}

    # --- Analyst ---
    insights: str
    insights_image_summary: str   # what the analyst saw in the charts

    # --- Critic ---
    critique: str
    critic_round: int
    insights_approved: bool

    # --- Final report ---
    final_report_md: str          # markdown
    final_report_html: str        # html (for download)
    final_report_docx_path: str   # path on disk
    final_report_pdf_path: str

    # --- Bookkeeping ---
    error: Optional[str]
    log: list[str]
    working_dir: str              # temp dir for charts and outputs

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

    # --- Peer Selector ---
    peers: dict[str, list[str]]   # {primary_ticker: [peer1, peer2, ...]}
    peer_raw_data: dict[str, Any] # {peer_ticker: {...statements}}

    # --- Validator ---
    data_quality: dict[str, Any]
    validation_passed: bool

    # --- Ratios (extended with DuPont) ---
    ratios: dict[str, Any]        # {ticker: {year: {ratio_name: value}}}
    dupont: dict[str, Any]

    # --- Trend Analyzer ---
    trends: dict[str, Any]        # {ticker: {ratio: {cagr, yoy_changes, direction, volatility}}}

    # --- Comparator ---
    comparison: dict[str, Any]

    # --- Peer Analyzer ---
    peer_analysis: dict[str, Any]

    # --- Charts ---
    charts: dict[str, str]        # {chart_name: filepath}

    # --- Analyst ---
    # v3: the analyst now produces a STRUCTURED, per-section set of analyses
    # instead of one monolithic blob. Each key is a section id; each value is
    # the AI-written prose for that section. The report writer interleaves
    # these with the matching tables and charts.
    section_analysis: dict[str, str]   # {section_id: markdown prose}
    insights: str                      # legacy: full concatenated insights (kept for compatibility)
    insights_image_summary: str

    # --- Critic ---
    critique: str
    critic_round: int
    insights_approved: bool

    # --- Final report ---
    final_report_md: str
    final_report_html: str
    final_report_docx_path: str
    final_report_pdf_path: str

    # --- Bookkeeping ---
    error: Optional[str]
    log: list[str]
    working_dir: str

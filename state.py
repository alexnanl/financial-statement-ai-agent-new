"""Shared workflow state - this is the 'memory' that flows through every agent."""
from typing import TypedDict, Optional, Any
from typing_extensions import NotRequired


class AnalysisState(TypedDict, total=False):
    """State that flows through the LangGraph workflow.

    Each agent reads what it needs and writes its results back.
    Using TypedDict (instead of a class) keeps it serializable for LangGraph.
    """
    # --- Input ---
    user_query: str

    # --- Step 1: Planner output ---
    tickers: list[str]              # e.g., ["AAPL", "MSFT"]
    analysis_type: str              # "single", "comparison", "trend"
    focus_areas: list[str]          # ["profitability", "liquidity", ...]
    years: int                      # how many years of history to pull

    # --- Step 2: Data Retrieval output ---
    raw_data: dict[str, Any]        # {ticker: {income_stmt, balance_sheet, cash_flow, info}}
    retrieval_errors: list[str]

    # --- Step 3: Validation output ---
    data_quality: dict[str, Any]    # {ticker: {completeness, issues, status}}
    validation_passed: bool

    # --- Step 4: Ratios output ---
    ratios: dict[str, Any]          # {ticker: {year: {ratio_name: value}}}

    # --- Step 5: Comparison output (only if comparison) ---
    comparison: dict[str, Any]      # ranked comparisons + commentary

    # --- Step 6: Insights output ---
    insights: str                   # markdown text from analyst agent

    # --- Step 7: Critic output ---
    critique: str                   # critic's feedback
    critic_round: int               # how many revision rounds done
    insights_approved: bool

    # --- Step 8: Final report ---
    final_report: str               # full markdown report

    # --- Bookkeeping ---
    error: Optional[str]
    log: list[str]                  # human-readable trail of what each agent did

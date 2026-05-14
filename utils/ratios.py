"""Financial ratio calculations.

This module is intentionally LLM-free: ratios are math, not opinion.
The agent system uses the LLM only for interpretation.
"""
from __future__ import annotations
import pandas as pd


def _safe_div(a, b):
    """Division that returns None when denominator is zero/missing."""
    try:
        if a is None or b is None or pd.isna(a) or pd.isna(b) or b == 0:
            return None
        return float(a) / float(b)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _get(df: pd.DataFrame, row_candidates: list[str], col):
    """Look up a value by trying multiple possible row names.

    Yahoo Finance row names vary (e.g., 'Total Revenue' vs 'TotalRevenue').
    This tries each candidate and returns the first match.
    """
    if df is None or df.empty:
        return None
    for name in row_candidates:
        if name in df.index:
            try:
                val = df.loc[name, col]
                return None if pd.isna(val) else float(val)
            except (KeyError, ValueError):
                continue
    return None


def compute_ratios_for_year(income_stmt: pd.DataFrame,
                            balance_sheet: pd.DataFrame,
                            cash_flow: pd.DataFrame,
                            col) -> dict:
    """Compute all ratios for one fiscal year (one column of the statements)."""
    # --- Income statement items ---
    revenue = _get(income_stmt, ["Total Revenue", "TotalRevenue", "Revenue"], col)
    gross_profit = _get(income_stmt, ["Gross Profit", "GrossProfit"], col)
    operating_income = _get(income_stmt, ["Operating Income", "OperatingIncome",
                                          "Total Operating Income As Reported"], col)
    net_income = _get(income_stmt, ["Net Income", "NetIncome",
                                    "Net Income Common Stockholders"], col)
    interest_expense = _get(income_stmt, ["Interest Expense", "InterestExpense"], col)
    ebit = operating_income  # close enough for our purposes

    # --- Balance sheet items ---
    total_assets = _get(balance_sheet, ["Total Assets", "TotalAssets"], col)
    current_assets = _get(balance_sheet, ["Current Assets", "Total Current Assets"], col)
    current_liab = _get(balance_sheet, ["Current Liabilities", "Total Current Liabilities"], col)
    total_liab = _get(balance_sheet, ["Total Liabilities Net Minority Interest",
                                     "Total Liab", "Total Liabilities"], col)
    total_equity = _get(balance_sheet, ["Stockholders Equity", "Total Equity Gross Minority Interest",
                                        "Total Stockholder Equity"], col)
    inventory = _get(balance_sheet, ["Inventory"], col)
    cash = _get(balance_sheet, ["Cash And Cash Equivalents", "Cash"], col)
    long_term_debt = _get(balance_sheet, ["Long Term Debt", "LongTermDebt"], col)
    short_term_debt = _get(balance_sheet, ["Current Debt", "Short Long Term Debt"], col)

    total_debt = None
    if long_term_debt is not None or short_term_debt is not None:
        total_debt = (long_term_debt or 0) + (short_term_debt or 0)

    # --- Cash flow items ---
    operating_cf = _get(cash_flow, ["Operating Cash Flow", "Total Cash From Operating Activities"], col)
    capex = _get(cash_flow, ["Capital Expenditure", "Capital Expenditures"], col)
    free_cash_flow = None
    if operating_cf is not None and capex is not None:
        free_cash_flow = operating_cf + capex  # capex is negative in Yahoo data

    # --- Build the ratio dictionary ---
    quick_assets = None
    if current_assets is not None and inventory is not None:
        quick_assets = current_assets - inventory

    return {
        # Profitability
        "gross_margin": _safe_div(gross_profit, revenue),
        "operating_margin": _safe_div(operating_income, revenue),
        "net_margin": _safe_div(net_income, revenue),
        "roa": _safe_div(net_income, total_assets),
        "roe": _safe_div(net_income, total_equity),

        # Liquidity
        "current_ratio": _safe_div(current_assets, current_liab),
        "quick_ratio": _safe_div(quick_assets, current_liab),
        "cash_ratio": _safe_div(cash, current_liab),

        # Leverage
        "debt_to_equity": _safe_div(total_debt, total_equity),
        "debt_to_assets": _safe_div(total_debt, total_assets),
        "interest_coverage": _safe_div(ebit, interest_expense),

        # Efficiency
        "asset_turnover": _safe_div(revenue, total_assets),

        # Cash flow
        "fcf_margin": _safe_div(free_cash_flow, revenue),
        "ocf_to_net_income": _safe_div(operating_cf, net_income),

        # Raw values (useful for the LLM to cite)
        "_raw": {
            "revenue": revenue,
            "net_income": net_income,
            "total_assets": total_assets,
            "total_equity": total_equity,
            "operating_cash_flow": operating_cf,
            "free_cash_flow": free_cash_flow,
        }
    }


def compute_ratios_all_years(raw: dict) -> dict:
    """Compute ratios for every year available in the statements.

    Returns: {year_str: {ratio_name: value, ...}, ...}
    """
    income = raw.get("income_stmt")
    balance = raw.get("balance_sheet")
    cash = raw.get("cash_flow")

    if income is None or income.empty:
        return {}

    result = {}
    for col in income.columns:
        year_key = str(col.year) if hasattr(col, "year") else str(col)
        result[year_key] = compute_ratios_for_year(income, balance, cash, col)
    return result


# Friendly names for display
RATIO_LABELS = {
    "gross_margin": "Gross Margin",
    "operating_margin": "Operating Margin",
    "net_margin": "Net Margin",
    "roa": "Return on Assets",
    "roe": "Return on Equity",
    "current_ratio": "Current Ratio",
    "quick_ratio": "Quick Ratio",
    "cash_ratio": "Cash Ratio",
    "debt_to_equity": "Debt / Equity",
    "debt_to_assets": "Debt / Assets",
    "interest_coverage": "Interest Coverage",
    "asset_turnover": "Asset Turnover",
    "fcf_margin": "Free Cash Flow Margin",
    "ocf_to_net_income": "OCF / Net Income",
}

RATIO_CATEGORIES = {
    "Profitability": ["gross_margin", "operating_margin", "net_margin", "roa", "roe"],
    "Liquidity": ["current_ratio", "quick_ratio", "cash_ratio"],
    "Leverage": ["debt_to_equity", "debt_to_assets", "interest_coverage"],
    "Efficiency": ["asset_turnover"],
    "Cash Flow": ["fcf_margin", "ocf_to_net_income"],
}

"""Validator Agent.

Checks each ticker's data for completeness and obvious issues before
downstream agents (ratios, insights) rely on it. Deterministic - no LLM.
"""
import pandas as pd
from state import AnalysisState
from config import CONFIG


REQUIRED_INCOME_ROWS = [
    ["Total Revenue", "TotalRevenue", "Revenue"],
    ["Net Income", "NetIncome", "Net Income Common Stockholders"],
]
REQUIRED_BALANCE_ROWS = [
    ["Total Assets", "TotalAssets"],
    ["Stockholders Equity", "Total Stockholder Equity",
     "Total Equity Gross Minority Interest"],
]


def _has_any_row(df: pd.DataFrame, candidates: list[str]) -> bool:
    if df is None or df.empty:
        return False
    return any(c in df.index for c in candidates)


def _validate_one(ticker: str, data: dict) -> dict:
    """Validate a single ticker's data, return a quality report."""
    issues: list[str] = []
    checks_passed = 0
    total_checks = 0

    income = data.get("income_stmt")
    balance = data.get("balance_sheet")
    cash = data.get("cash_flow")

    # --- Existence checks ---
    total_checks += 3
    if income is None or income.empty:
        issues.append("Income statement missing")
    else:
        checks_passed += 1
    if balance is None or balance.empty:
        issues.append("Balance sheet missing")
    else:
        checks_passed += 1
    if cash is None or cash.empty:
        issues.append("Cash flow statement missing")
    else:
        checks_passed += 1

    # --- Required-row checks ---
    for row_set in REQUIRED_INCOME_ROWS:
        total_checks += 1
        if _has_any_row(income, row_set):
            checks_passed += 1
        else:
            issues.append(f"Income statement missing: {row_set[0]}")

    for row_set in REQUIRED_BALANCE_ROWS:
        total_checks += 1
        if _has_any_row(balance, row_set):
            checks_passed += 1
        else:
            issues.append(f"Balance sheet missing: {row_set[0]}")

    # --- Year coverage ---
    if income is not None and not income.empty:
        years_available = len(income.columns)
        total_checks += 1
        if years_available >= 2:
            checks_passed += 1
        else:
            issues.append(f"Only {years_available} year(s) of data available")
    else:
        years_available = 0

    # --- Sanity check: revenue should not be negative ---
    if income is not None and not income.empty:
        for row_name in ["Total Revenue", "TotalRevenue", "Revenue"]:
            if row_name in income.index:
                rev = income.loc[row_name]
                if (rev < 0).any():
                    issues.append("Negative revenue detected (data anomaly)")
                break

    completeness = checks_passed / total_checks if total_checks else 0
    status = "pass" if completeness >= CONFIG.MIN_DATA_COMPLETENESS else "fail"

    return {
        "ticker": ticker,
        "completeness": round(completeness, 2),
        "checks_passed": checks_passed,
        "total_checks": total_checks,
        "years_available": years_available,
        "issues": issues,
        "status": status,
    }


def validator_agent(state: AnalysisState) -> AnalysisState:
    """Run validation on every retrieved ticker."""
    log = state.get("log", [])
    raw = state.get("raw_data", {})

    quality: dict = {}
    any_passed = False

    for ticker, data in raw.items():
        report = _validate_one(ticker, data)
        quality[ticker] = report
        if report["status"] == "pass":
            any_passed = True
        log.append(
            f"Validator: {ticker} completeness={report['completeness']*100:.0f}% "
            f"status={report['status']} issues={len(report['issues'])}"
        )

    return {
        **state,
        "data_quality": quality,
        "validation_passed": any_passed,
        "error": None if any_passed else "All tickers failed data quality checks",
        "log": log,
    }

"""Retriever Agent.

Fetches financial statements from Yahoo Finance using yfinance.
No LLM is involved here - this is pure data plumbing.
"""
import yfinance as yf
from state import AnalysisState


def retriever_agent(state: AnalysisState) -> AnalysisState:
    """Pull income statement, balance sheet, cash flow, and meta info for each ticker."""
    log = state.get("log", [])
    tickers = state.get("tickers", [])
    raw_data: dict = {}
    errors: list[str] = []

    for ticker in tickers:
        try:
            t = yf.Ticker(ticker)
            # .financials and .income_stmt are aliases in newer yfinance versions
            income = t.income_stmt
            balance = t.balance_sheet
            cash = t.cashflow

            # info call can sometimes fail / be slow; wrap separately
            try:
                info = t.info or {}
            except Exception:
                info = {}

            if income is None or income.empty:
                errors.append(f"{ticker}: no income statement available")
                continue

            raw_data[ticker] = {
                "income_stmt": income,
                "balance_sheet": balance,
                "cash_flow": cash,
                "info": {
                    "longName": info.get("longName") or info.get("shortName") or ticker,
                    "sector": info.get("sector", "Unknown"),
                    "industry": info.get("industry", "Unknown"),
                    "currency": info.get("currency", "USD"),
                    "marketCap": info.get("marketCap"),
                    "country": info.get("country", "Unknown"),
                },
            }
            log.append(
                f"Retriever: {ticker} -> {len(income.columns)} years of statements"
            )

        except Exception as e:
            errors.append(f"{ticker}: {type(e).__name__}: {e}")
            log.append(f"Retriever: failed for {ticker} ({e})")

    if not raw_data:
        return {
            **state,
            "raw_data": {},
            "retrieval_errors": errors,
            "error": "Could not retrieve data for any ticker. " + " | ".join(errors),
            "log": log,
        }

    return {
        **state,
        "raw_data": raw_data,
        "retrieval_errors": errors,
        "log": log,
    }

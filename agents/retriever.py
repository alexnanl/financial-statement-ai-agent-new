"""Retriever Agent. Fetches financial statements from Yahoo Finance."""
import time
import yfinance as yf
from state import AnalysisState


# --- In-memory data cache (per running process) -------------------------
# So repeated runs of the same ticker don't re-hit Yahoo Finance. Only the
# DATA FETCH is cached; the analysis still re-runs on every request, so code
# and prompt changes always take effect. Cache is keyed by ticker, expires
# after the TTL, resets on app reboot, and can be cleared from the UI.
_DATA_CACHE: dict = {}              # {ticker: (fetched_at_epoch, data_dict)}
_CACHE_TTL_SECONDS = 6 * 3600       # 6 hours


def clear_data_cache() -> int:
    """Empty the data cache. Returns how many tickers were cleared."""
    n = len(_DATA_CACHE)
    _DATA_CACHE.clear()
    return n


def data_cache_status() -> dict:
    """Report what's currently cached (for the UI)."""
    now = time.time()
    fresh = [t for t, (ts, _) in _DATA_CACHE.items()
             if now - ts < _CACHE_TTL_SECONDS]
    return {"cached": len(_DATA_CACHE), "fresh": len(fresh),
            "tickers": sorted(_DATA_CACHE.keys())}


def _fetch_one(ticker: str):
    """Fetch a single ticker's statements. Returns (data_dict, error_str).

    Serves a cached copy when one exists and is younger than the TTL.
    """
    cached = _DATA_CACHE.get(ticker)
    if cached is not None:
        fetched_at, data = cached
        if time.time() - fetched_at < _CACHE_TTL_SECONDS:
            return data, None

    try:
        t = yf.Ticker(ticker)
        income = t.income_stmt
        balance = t.balance_sheet
        cash = t.cashflow
        try:
            info = t.info or {}
        except Exception:
            info = {}

        if income is None or income.empty:
            return None, f"{ticker}: no income statement available"

        data = {
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
        _DATA_CACHE[ticker] = (time.time(), data)   # cache on success only
        return data, None
    except Exception as e:
        return None, f"{ticker}: {type(e).__name__}: {e}"


def retriever_agent(state: AnalysisState) -> AnalysisState:
    """Pull income statement, balance sheet, cash flow, and meta info for each ticker."""
    log = state.get("log", [])
    tickers = state.get("tickers", [])
    raw_data: dict = {}
    errors: list[str] = []

    for ticker in tickers:
        data, err = _fetch_one(ticker)
        if data is None:
            errors.append(err)
            log.append(f"Retriever: failed for {ticker}")
        else:
            raw_data[ticker] = data
            log.append(f"Retriever: {ticker} -> {len(data['income_stmt'].columns)} years")

    if not raw_data:
        return {**state, "raw_data": {}, "retrieval_errors": errors,
                "error": "Could not retrieve data for any ticker. " + " | ".join(errors),
                "log": log}

    return {**state, "raw_data": raw_data, "retrieval_errors": errors, "log": log}


def peer_retriever_agent(state: AnalysisState) -> AnalysisState:
    """Second-pass retriever for peer companies selected by the Peer Selector."""
    log = state.get("log", [])
    peers_map = state.get("peers", {})
    peer_data: dict = {}

    # Collect unique peer tickers (a peer might be shared across primaries)
    unique_peers = set()
    for primary, peer_list in peers_map.items():
        for p in peer_list:
            unique_peers.add(p)

    for peer in unique_peers:
        data, err = _fetch_one(peer)
        if data is None:
            log.append(f"Peer Retriever: failed for {peer} ({err})")
        else:
            peer_data[peer] = data
            log.append(f"Peer Retriever: fetched {peer}")

    return {**state, "peer_raw_data": peer_data, "log": log}

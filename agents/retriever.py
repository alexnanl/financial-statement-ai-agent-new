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


def _row_latest(df, names):
    """Latest-column value for the first matching row (no pandas import needed)."""
    if df is None or getattr(df, "empty", True):
        return None
    for n in names:
        if n in df.index:
            try:
                v = df.loc[n, df.columns[0]]
                if v is not None and v == v:  # v == v is False for NaN
                    return float(v)
            except Exception:
                continue
    return None


def _fast_get(fi, *keys):
    """Read a value from yfinance fast_info, tolerant of key/attr styles."""
    if fi is None:
        return None
    for k in keys:
        v = None
        try:
            v = fi[k]
        except Exception:
            try:
                v = getattr(fi, k)
            except Exception:
                v = None
        if v is not None:
            return v
    return None


def _resolve_meta(t, ticker, income, balance):
    """Build the info dict, resilient to Yahoo's flaky .info endpoint.

    Market cap (and name/sector) often come back empty from t.info even when
    the statements load fine — which silently dropped the Valuation section.
    Fall back to t.fast_info, then to shares x price, so market cap is
    available whenever the statements are.
    """
    try:
        info = t.info or {}
    except Exception:
        info = {}
    try:
        fi = t.fast_info
    except Exception:
        fi = None

    mcap = info.get("marketCap") or _fast_get(fi, "market_cap", "marketCap")
    if not mcap:
        price = _fast_get(fi, "last_price", "lastPrice", "previous_close", "previousClose")
        shares = (_fast_get(fi, "shares", "shares_outstanding")
                  or _row_latest(balance, ["Ordinary Shares Number", "Share Issued"])
                  or _row_latest(income, ["Diluted Average Shares", "Basic Average Shares"]))
        if price and shares:
            try:
                mcap = float(price) * float(shares)
            except (TypeError, ValueError):
                mcap = None

    return {
        "longName": info.get("longName") or info.get("shortName") or ticker,
        "sector": info.get("sector") or "Unknown",
        "industry": info.get("industry") or "Unknown",
        "currency": info.get("currency") or _fast_get(fi, "currency") or "USD",
        "marketCap": mcap,
        "country": info.get("country") or "Unknown",
    }


def _fetch_one(ticker: str):
    """Fetch a single ticker's statements + meta. Returns (data_dict, error_str).

    Serves a cached copy when one exists and is younger than the TTL. Retries
    the statement fetch once to ride out transient Yahoo throttling.
    """
    cached = _DATA_CACHE.get(ticker)
    if cached is not None:
        fetched_at, data = cached
        if time.time() - fetched_at < _CACHE_TTL_SECONDS:
            return data, None

    last_err = None
    for attempt in range(2):
        try:
            t = yf.Ticker(ticker)
            income = t.income_stmt
            if income is None or income.empty:
                last_err = f"{ticker}: no income statement available"
            else:
                balance = t.balance_sheet
                cash = t.cashflow
                data = {
                    "income_stmt": income,
                    "balance_sheet": balance,
                    "cash_flow": cash,
                    "info": _resolve_meta(t, ticker, income, balance),
                }
                _DATA_CACHE[ticker] = (time.time(), data)  # cache on success only
                return data, None
        except Exception as e:
            last_err = f"{ticker}: {type(e).__name__}: {e}"
        if attempt == 0:
            time.sleep(1.0)

    return None, last_err


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

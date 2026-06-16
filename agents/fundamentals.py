"""Fundamentals Agent.

Computes valuation multiples, growth, and capital-allocation metrics for each
primary ticker (deterministically, no LLM), plus a valuation comparison against
the same peer set used elsewhere. Fills the biggest gaps vs a professional
equity-research report.

Runs after Peer Analyzer (so peer statements are available) and before the
Chart Builder / Analyst.
"""
from __future__ import annotations
import statistics
from state import AnalysisState
from utils.fundamentals import (
    compute_valuation, compute_growth, compute_capital_allocation,
    VALUATION_METRICS,
)


def _percentile(value: float, peers: list[float], higher_is_better: bool) -> float:
    if not peers:
        return 50.0
    if higher_is_better:
        below = sum(1 for v in peers if value >= v)
    else:
        below = sum(1 for v in peers if value <= v)
    return round(100 * below / len(peers), 1)


def fundamentals_agent(state: AnalysisState) -> AnalysisState:
    log = state.get("log", [])
    tickers = state.get("tickers", [])
    raw = state.get("raw_data", {})
    peers_map = state.get("peers", {})
    peer_raw = state.get("peer_raw_data", {})
    ratios = state.get("ratios", {})

    fundamentals: dict = {}
    valuation_peers: dict = {}

    for t in tickers:
        if t not in ratios or t not in raw:
            continue
        data = raw[t]
        mcap = data.get("info", {}).get("marketCap")

        val = compute_valuation(data, mcap)
        fundamentals[t] = {
            "valuation": val,
            "growth": compute_growth(data),
            "capital_allocation": compute_capital_allocation(data, mcap),
        }
        log.append(f"Fundamentals: {t} valuation/growth/capital computed")

        # ---- Valuation peer comparison ----
        peer_list = peers_map.get(t, [])
        if not peer_list or not val:
            continue
        peer_vals_by_metric: dict[str, list] = {m: [] for m in VALUATION_METRICS}
        for peer in peer_list:
            pdata = peer_raw.get(peer)
            if not pdata:
                continue
            pmcap = pdata.get("info", {}).get("marketCap")
            pval = compute_valuation(pdata, pmcap)
            for m in VALUATION_METRICS:
                pv = pval.get(m)
                # Skip broken/negative multiples (e.g. negative-equity peers)
                if pv is None:
                    continue
                if m in ("pe", "ps", "pb", "ev_ebitda") and pv <= 0:
                    continue
                peer_vals_by_metric[m].append(pv)

        comp: dict = {}
        for m, (label, hib) in VALUATION_METRICS.items():
            cv = val.get(m)
            pvs = peer_vals_by_metric[m]
            if cv is None or not pvs:
                continue
            comp[m] = {
                "label": label,
                "company": cv,
                "peer_average": statistics.mean(pvs),
                "peer_median": statistics.median(pvs),
                "peer_count": len(pvs),
                "percentile_rank": _percentile(cv, pvs, hib),
                "higher_is_better": hib,
            }
        if comp:
            valuation_peers[t] = comp

    return {**state,
            "fundamentals": fundamentals,
            "valuation_peers": valuation_peers,
            "log": log}

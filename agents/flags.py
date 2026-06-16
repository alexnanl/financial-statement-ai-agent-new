"""Flags Agent.

Runs the deterministic Flags & Signals rule engine for each primary ticker,
turning the computed ratios / trends / fundamentals into a structured set of
strengths, watch items and concerns (with an overall tilt). No LLM.

Runs after Fundamentals (so valuation/growth/capital figures are available) and
before the Chart Builder / Analyst, so the Analyst can ground its
"Strengths & Concerns" and "Risks" prose in these signals.
"""
from __future__ import annotations
from state import AnalysisState
from utils.flags import compute_flags


def flags_agent(state: AnalysisState) -> AnalysisState:
    log = state.get("log", [])
    tickers = state.get("tickers", [])
    ratios = state.get("ratios", {})
    trends = state.get("trends", {})
    fundamentals = state.get("fundamentals", {})
    valuation_peers = state.get("valuation_peers", {})

    flags: dict = {}
    for t in tickers:
        if t not in ratios:
            continue
        f = compute_flags(
            ratios[t], trends.get(t, {}),
            fundamentals.get(t, {}), valuation_peers.get(t, {}),
        )
        flags[t] = f
        s = f["summary"]
        log.append(f"Flags: {t} -> {s['positive']} positive / "
                   f"{s['watch']} watch / {s['concern']} concern")

    return {**state, "flags": flags, "log": log}

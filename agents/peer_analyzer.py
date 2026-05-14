"""Peer Analyzer Agent.

For each primary ticker, computes how it ranks vs its peer set on each ratio.
Outputs primary value, peer average, peer median, percentile rank, and the
peer values themselves so charts can be drawn.
"""
from __future__ import annotations
import statistics
from state import AnalysisState
from utils.ratios import RATIO_LABELS, compute_ratios_all_years


def _latest_year(by_year: dict) -> str | None:
    if not by_year:
        return None
    try:
        return max(by_year.keys(), key=lambda y: int(y))
    except ValueError:
        return max(by_year.keys())


def _percentile_rank(value: float, all_values: list[float]) -> float:
    """Percentile rank: % of peers that the primary is >= than."""
    if not all_values:
        return 50.0
    below = sum(1 for v in all_values if value >= v)
    return round(100 * below / len(all_values), 1)


def peer_analyzer_agent(state: AnalysisState) -> AnalysisState:
    log = state.get("log", [])
    peers_map = state.get("peers", {})
    peer_raw = state.get("peer_raw_data", {})
    primary_ratios = state.get("ratios", {})

    if not peers_map or not peer_raw:
        log.append("Peer Analyzer: no peers available, skipping")
        return {**state, "peer_analysis": {}, "log": log}

    # First, compute ratios for each peer
    peer_ratios: dict = {}
    for peer_ticker, data in peer_raw.items():
        try:
            peer_ratios[peer_ticker] = compute_ratios_all_years(data)
        except Exception as e:
            log.append(f"Peer Analyzer: ratio compute failed for {peer_ticker} ({e})")

    # Build the comparison structure
    peer_analysis: dict = {}

    for primary, peer_list in peers_map.items():
        if primary not in primary_ratios:
            continue

        primary_year = _latest_year(primary_ratios[primary])
        if not primary_year:
            continue
        primary_values = primary_ratios[primary][primary_year]

        # Gather peer most-recent values
        analysis_for_primary: dict = {}
        for ratio_key in RATIO_LABELS.keys():
            primary_val = primary_values.get(ratio_key)
            if primary_val is None:
                continue

            peer_vals = {}
            for peer in peer_list:
                if peer not in peer_ratios:
                    continue
                py = _latest_year(peer_ratios[peer])
                if py is None:
                    continue
                v = peer_ratios[peer][py].get(ratio_key)
                if v is not None:
                    peer_vals[peer] = v

            if not peer_vals:
                continue

            peer_values_list = list(peer_vals.values())
            analysis_for_primary[ratio_key] = {
                "primary_value": primary_val,
                "peer_average": statistics.mean(peer_values_list),
                "peer_median": statistics.median(peer_values_list),
                "peer_min": min(peer_values_list),
                "peer_max": max(peer_values_list),
                "peer_count": len(peer_values_list),
                "peer_values": peer_vals,
                "percentile_rank": _percentile_rank(primary_val, peer_values_list),
            }

        peer_analysis[primary] = analysis_for_primary
        log.append(f"Peer Analyzer: {primary} benchmarked on "
                   f"{len(analysis_for_primary)} ratios vs {len(peer_list)} peers")

    return {**state, "peer_analysis": peer_analysis, "log": log}

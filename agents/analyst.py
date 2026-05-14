"""Analyst Agent (Insight Generator) with VISION.

Reads the generated PNG charts using GPT-4o's vision capability, then writes
narrative insights grounded in both numerical tables AND the visual trends
shown in the charts.

May run twice: initial draft + revision after Critic feedback.
"""
import json
from state import AnalysisState
from utils.llm import chat_with_images
from utils.ratios import RATIO_LABELS


SYSTEM_PROMPT = """You are a senior financial analyst. You receive:
  1. Numerical tables (ratios, DuPont decomposition, trend metrics, peer benchmarks)
  2. Chart images showing trends, decompositions, and peer comparisons

Write clear, evidence-based insights for a business reader.

Rules:
1. Cite specific numbers from the tables. Never invent figures.
2. Reference what you SEE in the charts (e.g., "the upward slope in the ROE chart shows...").
3. Use the DuPont decomposition to explain WHY ROE moved (margin? turnover? leverage?).
4. Use the trend metrics to flag direction (improving / deteriorating / stable / volatile).
5. Use peer benchmarks to contextualize: is the company above/below peer average? Top quartile?
6. Use markdown with these REQUIRED sections:
   - ## Executive Summary  (3-4 sentences)
   - ## Profitability Analysis
   - ## DuPont Decomposition  (explain ROE drivers)
   - ## Trend Analysis  (multi-year direction with citations)
   - ## Peer Comparison  (how the company ranks vs peers)
   - ## Liquidity & Leverage
   - ## Risks & Caveats
7. Be concise - aim for 600-1000 words.
8. Embed chart references using this exact syntax: [CHART: chart_name] on its own line.
   Use the chart names listed in the user message. Place them where they support the text.
"""


def _format_ratios(ratios: dict) -> str:
    out = {}
    for ticker, by_year in ratios.items():
        out[ticker] = {}
        for year, ratio_dict in by_year.items():
            clean = {}
            for k, v in ratio_dict.items():
                if k.startswith("_") or v is None:
                    continue
                clean[RATIO_LABELS.get(k, k)] = round(v, 4)
            out[ticker][year] = clean
    return json.dumps(out, indent=2)


def _format_dupont(ratios: dict) -> str:
    """Pull DuPont data into a focused block."""
    out = {}
    for ticker, by_year in ratios.items():
        out[ticker] = {}
        for year, ratio_dict in by_year.items():
            d = ratio_dict.get("_dupont", {})
            if d:
                out[ticker][year] = {k: round(v, 4) if v is not None else None
                                     for k, v in d.items()}
    return json.dumps(out, indent=2)


def _format_trends(trends: dict) -> str:
    """Compact trend summary."""
    out = {}
    for ticker, ratio_trends in trends.items():
        out[ticker] = {}
        for ratio_key, t in ratio_trends.items():
            if t["direction"] == "insufficient_data":
                continue
            out[ticker][RATIO_LABELS.get(ratio_key, ratio_key)] = {
                "direction": t["direction"],
                "cagr": round(t["cagr"], 4) if t["cagr"] is not None else None,
                "first": f"{t['first_year']}={round(t['first_value'], 4)}" if t['first_value'] else None,
                "last": f"{t['last_year']}={round(t['last_value'], 4)}" if t['last_value'] else None,
            }
    return json.dumps(out, indent=2)


def _format_peers(peer_analysis: dict, peers_map: dict) -> str:
    out = {}
    for primary, ratios_dict in peer_analysis.items():
        out[primary] = {
            "peers": peers_map.get(primary, []),
            "benchmarks": {},
        }
        for ratio_key, data in ratios_dict.items():
            out[primary]["benchmarks"][RATIO_LABELS.get(ratio_key, ratio_key)] = {
                "primary": round(data["primary_value"], 4),
                "peer_avg": round(data["peer_average"], 4),
                "peer_median": round(data["peer_median"], 4),
                "percentile_rank": data["percentile_rank"],
            }
    return json.dumps(out, indent=2)


def analyst_agent(state: AnalysisState) -> AnalysisState:
    log = state.get("log", [])
    ratios = state.get("ratios", {})
    trends = state.get("trends", {})
    peer_analysis = state.get("peer_analysis", {})
    peers_map = state.get("peers", {})
    comparison = state.get("comparison", {})
    charts = state.get("charts", {})
    analysis_type = state.get("analysis_type", "single")
    focus = state.get("focus_areas", [])
    critique = state.get("critique", "")
    tickers = list(ratios.keys())

    if not ratios:
        return {**state, "insights": "_No ratios were computed; cannot generate insights._",
                "log": log + ["Analyst: no ratios available"]}

    is_revision = bool(critique)
    chart_paths = list(charts.values())[:10]  # cap to avoid huge payloads
    chart_names = list(charts.keys())[:10]

    parts = [
        f"Analysis type: {analysis_type}",
        f"Companies: {', '.join(tickers)}",
        f"Focus areas: {', '.join(focus)}",
        "",
        "=== Ratio data (by ticker / year) ===",
        _format_ratios(ratios),
        "",
        "=== DuPont decomposition data ===",
        _format_dupont(ratios),
        "",
        "=== Trend analysis ===",
        _format_trends(trends),
    ]

    if peer_analysis:
        parts += ["", "=== Peer benchmarking ===", _format_peers(peer_analysis, peers_map)]

    if comparison:
        parts += ["", "=== Multi-company comparison summary ===",
                  json.dumps(comparison.get("win_tally", {}), indent=2)]

    parts += [
        "",
        "=== Charts available for reference (use [CHART: name] syntax) ===",
        "\n".join(f"  - {name}" for name in chart_names),
        "",
        "The chart images are also attached for your visual reference. "
        "Describe what they actually show.",
    ]

    if is_revision:
        parts += ["", "=== Critic feedback to address ===", critique,
                  "", "Revise to address every point above."]

    parts += ["", "Write the analysis now in markdown with the required sections."]
    user_prompt = "\n".join(parts)

    try:
        insights = chat_with_images(SYSTEM_PROMPT, user_prompt, chart_paths,
                                    temperature=0.3)
        log.append(
            f"Analyst: produced {'revised' if is_revision else 'initial'} "
            f"insights ({len(insights)} chars, {len(chart_paths)} charts viewed)"
        )
        return {**state, "insights": insights, "log": log}
    except Exception as e:
        return {**state, "insights": f"_Analyst failed: {e}_",
                "log": log + [f"Analyst: error {e}"]}

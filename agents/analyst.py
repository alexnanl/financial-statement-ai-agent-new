"""Analyst Agent (Insight Generator) with VISION — v3 section-based.

Instead of producing one monolithic markdown blob with [CHART:] markers, the
analyst now writes a SEPARATE, focused analysis for each report section. Each
section's prose is grounded in exactly the tables and chart images that belong
to that section, so the report writer can interleave data + chart + AI text
in the right place (no more dumping everything at the end).

Sections produced (when data is available):
  - executive_summary
  - profitability           (per primary ticker, profitability dashboard chart)
  - dupont                  (per ticker, DuPont chart)
  - trend                   (per ticker, trend tables/charts)
  - peer                    (per primary ticker, peer benchmark tables/charts)
  - liquidity_leverage
  - comparison              (multi-company, only for comparison analyses)
  - risks

May run twice: initial draft + revision after Critic feedback.
"""
import json
from state import AnalysisState
from utils.llm import chat_with_images, chat
from utils.ratios import RATIO_LABELS


BASE_SYSTEM = """You are a senior financial analyst writing one section of a \
professional financial analysis report.

You receive the numerical tables AND the chart image(s) for THIS SECTION ONLY.

Rules:
1. Write ONLY the prose for this one section. Do NOT write a heading — the report
   already has one. Do NOT write '[CHART: ...]' markers — charts are placed
   automatically.
2. Cite specific numbers from the tables provided. Never invent figures.
3. Reference what the chart actually shows (slopes, gaps, turning points).
4. Be concise and concrete: 2-4 short paragraphs, business-reader tone.
5. Plain prose only. No markdown headings, no bullet lists unless genuinely
   needed, no '##'. Just clean paragraphs.
6. Do not restate the raw table verbatim — interpret it.
"""

SECTION_BRIEFS = {
    "executive_summary": (
        "Write the EXECUTIVE SUMMARY. 3-5 sentences. Summarize the most important "
        "findings across profitability, trend direction, DuPont drivers, leverage "
        "and (if present) peer standing. Lead with the headline conclusion."
    ),
    "profitability": (
        "Write the PROFITABILITY ANALYSIS for {ticker}. Discuss gross, operating "
        "and net margins, their levels and direction over the years shown, and what "
        "the margin chart reveals."
    ),
    "dupont": (
        "Write the DUPONT DECOMPOSITION analysis for {ticker}. Explain WHY ROE moved "
        "the way it did — attribute it to net margin, asset turnover and/or equity "
        "multiplier (leverage). Use the 3-step and 5-step figures."
    ),
    "trend": (
        "Write the TREND ANALYSIS for {ticker}. Describe multi-year direction "
        "(improving / deteriorating / stable / volatile) and cite CAGR and "
        "first vs last values for the key ratios."
    ),
    "peer": (
        "Write the PEER COMPARISON for {ticker}. State whether the company is above "
        "or below peer average/median and cite its percentile rank for the key "
        "ratios. Note where it leads and where it lags."
    ),
    "liquidity_leverage": (
        "Write the LIQUIDITY & LEVERAGE analysis for {ticker}. Discuss current/quick/"
        "cash ratios and debt/equity, debt/assets, interest coverage. Comment on "
        "financial-risk posture. If the current ratio is below 1, note whether that "
        "is a genuine concern or normal for a company with strong operating cash flow."
    ),
    "growth": (
        "Write the GROWTH & SCALE analysis for {ticker}. Use the ABSOLUTE revenue, "
        "net income, EPS and free-cash-flow figures and their year-over-year and CAGR "
        "growth. Comment on the top-line and bottom-line trajectory and the scale of "
        "the business. These are REPORTED HISTORICAL figures — never call them "
        "'expected' or 'projected'."
    ),
    "valuation": (
        "Write the VALUATION analysis for {ticker}. Discuss the P/E, P/S, P/B, "
        "EV/EBITDA, FCF yield and dividend yield, and how they compare to the peer "
        "average/median where given. Say whether the stock looks rich or cheap on "
        "these multiples relative to peers. Do NOT give a price target or a buy/sell "
        "recommendation; this is descriptive valuation context only."
    ),
    "capital_allocation": (
        "Write the CAPITAL ALLOCATION analysis for {ticker}. Use the buyback, "
        "dividend, total-cash-returned, payout-ratio and share-count-change figures. "
        "Explain how aggressive buybacks shrink shareholders' equity and can inflate "
        "ROE — connecting this to the DuPont/leverage story where relevant."
    ),
    "comparison": (
        "Write the SIDE-BY-SIDE COMPARISON analysis. Compare the companies head-to-"
        "head on the ranked ratios, note who wins on what, and give an overall read."
    ),
    "risks": (
        "Write the RISKS & CAVEATS section. Note data-quality limitations, any "
        "volatile or deteriorating metrics, and what a reader should treat with "
        "caution. All figures provided are REPORTED HISTORICAL values, not forecasts "
        "— do NOT describe them as 'expected' or 'projected'. When a metric like ROE "
        "declines because of LOWER leverage, say so plainly rather than framing it as "
        "pure deterioration. End with a one-line reminder this is not investment advice."
    ),
}


# ---------- formatting helpers (compact, section-scoped) ----------

def _ratios_block(by_year: dict) -> str:
    out = {}
    for year, ratio_dict in by_year.items():
        clean = {}
        for k, v in ratio_dict.items():
            if k.startswith("_") or v is None:
                continue
            clean[RATIO_LABELS.get(k, k)] = round(v, 4)
        out[year] = clean
    return json.dumps(out, indent=2)


def _dupont_block(by_year: dict) -> str:
    out = {}
    for year, ratio_dict in by_year.items():
        d = ratio_dict.get("_dupont", {})
        if d:
            out[year] = {k: (round(v, 4) if v is not None else None)
                         for k, v in d.items()}
    return json.dumps(out, indent=2)


def _trend_block(ticker_trends: dict) -> str:
    out = {}
    for ratio_key, t in ticker_trends.items():
        if t["direction"] == "insufficient_data":
            continue
        out[RATIO_LABELS.get(ratio_key, ratio_key)] = {
            "direction": t["direction"],
            "cagr": round(t["cagr"], 4) if t["cagr"] is not None else None,
            "first": f"{t['first_year']}={round(t['first_value'], 4)}" if t['first_value'] else None,
            "last": f"{t['last_year']}={round(t['last_value'], 4)}" if t['last_value'] else None,
        }
    return json.dumps(out, indent=2)


def _growth_block(growth: dict) -> str:
    out = {}
    for key, g in (growth or {}).items():
        if not g:
            continue
        out[g["label"]] = {
            "first": f"{g['first_year']}={g['first']:.4g}" if g.get("first") is not None else None,
            "last": f"{g['last_year']}={g['last']:.4g}" if g.get("last") is not None else None,
            "cagr": round(g["cagr"], 4) if g.get("cagr") is not None else None,
            "yoy": [round(s["yoy"], 4) for s in g["series"] if s["yoy"] is not None],
        }
    return json.dumps(out, indent=2)


def _valuation_block(valuation: dict, val_peers: dict) -> str:
    out = {"multiples": {k: (round(v, 4) if isinstance(v, (int, float)) else v)
                         for k, v in (valuation or {}).items() if v is not None},
           "vs_peers": {}}
    for m, d in (val_peers or {}).items():
        out["vs_peers"][d["label"]] = {
            "company": round(d["company"], 4),
            "peer_avg": round(d["peer_average"], 4),
            "peer_median": round(d["peer_median"], 4),
            "percentile_rank": d["percentile_rank"],
        }
    return json.dumps(out, indent=2)


def _capalloc_block(cap: dict) -> str:
    return json.dumps({k: (round(v, 4) if isinstance(v, (int, float)) else v)
                       for k, v in (cap or {}).items() if v is not None}, indent=2)


def _peer_block(ratios_dict: dict, peers: list) -> str:
    out = {"peers": peers, "benchmarks": {}}
    for ratio_key, data in ratios_dict.items():
        out["benchmarks"][RATIO_LABELS.get(ratio_key, ratio_key)] = {
            "company": round(data["primary_value"], 4),
            "peer_avg": round(data["peer_average"], 4),
            "peer_median": round(data["peer_median"], 4),
            "percentile_rank": data["percentile_rank"],
        }
    return json.dumps(out, indent=2)


def _write_section(section_id: str, brief: str, data_text: str,
                    chart_paths: list[str], critique: str = "") -> str:
    """Call the LLM (with vision if charts exist) for one section."""
    system = BASE_SYSTEM
    parts = [brief, "", "=== Data for this section ===", data_text]
    if chart_paths:
        parts += ["", "The chart image(s) for this section are attached. "
                  "Describe what they actually show."]
    if critique:
        parts += ["", "=== Critic feedback to address ===", critique,
                  "Revise to address every relevant point."]
    parts += ["", "Write the section prose now."]
    user_text = "\n".join(parts)

    try:
        if chart_paths:
            return chat_with_images(system, user_text, chart_paths, temperature=0.3).strip()
        return chat(system, user_text, temperature=0.3).strip()
    except Exception as e:
        return f"_Analysis for this section could not be generated: {e}_"


def analyst_agent(state: AnalysisState) -> AnalysisState:
    log = state.get("log", [])
    ratios = state.get("ratios", {})
    trends = state.get("trends", {})
    peer_analysis = state.get("peer_analysis", {})
    peers_map = state.get("peers", {})
    comparison = state.get("comparison", {})
    fundamentals = state.get("fundamentals", {})
    valuation_peers = state.get("valuation_peers", {})
    charts = state.get("charts", {})
    analysis_type = state.get("analysis_type", "single")
    critique = state.get("critique", "")
    tickers = list(ratios.keys())

    if not ratios:
        return {**state,
                "section_analysis": {},
                "insights": "_No ratios were computed; cannot generate insights._",
                "log": log + ["Analyst: no ratios available"]}

    is_revision = bool(critique)
    sections: dict[str, str] = {}

    # ----- Executive summary (sees the highest-level data, no charts) -----
    overview = {
        "tickers": tickers,
        "ratios": {t: _ratios_block(ratios[t]) for t in tickers},
        "trends": {t: _trend_block(trends.get(t, {})) for t in tickers},
    }
    sections["executive_summary"] = _write_section(
        "executive_summary", SECTION_BRIEFS["executive_summary"],
        json.dumps(overview, indent=2)[:6000], [], critique)

    # ----- Per-ticker sections -----
    for t in tickers:
        by_year = ratios[t]

        # Profitability
        prof_charts = [charts[k] for k in [f"profitability_{t}"] if k in charts]
        sections[f"profitability_{t}"] = _write_section(
            "profitability", SECTION_BRIEFS["profitability"].format(ticker=t),
            _ratios_block(by_year), prof_charts, critique)

        # DuPont
        dp_charts = [charts[k] for k in [f"dupont_{t}"] if k in charts]
        sections[f"dupont_{t}"] = _write_section(
            "dupont", SECTION_BRIEFS["dupont"].format(ticker=t),
            _dupont_block(by_year), dp_charts, critique)

        # Trend
        if t in trends:
            tr_charts = [charts[k] for k in
                         [f"trend_{t}_roe", f"trend_{t}_roa", f"trend_{t}_net_margin"]
                         if k in charts]
            sections[f"trend_{t}"] = _write_section(
                "trend", SECTION_BRIEFS["trend"].format(ticker=t),
                _trend_block(trends[t]), tr_charts, critique)

        # Liquidity & leverage
        sections[f"liquidity_leverage_{t}"] = _write_section(
            "liquidity_leverage", SECTION_BRIEFS["liquidity_leverage"].format(ticker=t),
            _ratios_block(by_year), [], critique)

        # Fundamentals: growth, valuation, capital allocation (v3.1)
        fund = fundamentals.get(t, {})
        if fund.get("growth"):
            sections[f"growth_{t}"] = _write_section(
                "growth", SECTION_BRIEFS["growth"].format(ticker=t),
                _growth_block(fund["growth"]), [], critique)
        if fund.get("valuation"):
            sections[f"valuation_{t}"] = _write_section(
                "valuation", SECTION_BRIEFS["valuation"].format(ticker=t),
                _valuation_block(fund["valuation"], valuation_peers.get(t, {})),
                [], critique)
        if fund.get("capital_allocation"):
            sections[f"capital_allocation_{t}"] = _write_section(
                "capital_allocation", SECTION_BRIEFS["capital_allocation"].format(ticker=t),
                _capalloc_block(fund["capital_allocation"]), [], critique)

        # Peer comparison
        if t in peer_analysis:
            pchart_keys = [k for k in charts if k.startswith(f"peer_{t}_")]
            pcharts = [charts[k] for k in pchart_keys[:4]]
            sections[f"peer_{t}"] = _write_section(
                "peer", SECTION_BRIEFS["peer"].format(ticker=t),
                _peer_block(peer_analysis[t], peers_map.get(t, [])),
                pcharts, critique)

    # ----- Multi-company comparison -----
    if comparison and analysis_type == "comparison":
        comp_charts = [charts[k] for k in
                       ["win_tally", "compare_roe", "compare_net_margin"]
                       if k in charts]
        comp_data = {
            "rankings": {
                k: {"label": r["label"], "values": r["values"], "best": r["best"]}
                for k, r in comparison.get("rankings", {}).items()
            },
            "win_tally": comparison.get("win_tally", {}),
        }
        sections["comparison"] = _write_section(
            "comparison", SECTION_BRIEFS["comparison"],
            json.dumps(comp_data, indent=2)[:6000], comp_charts, critique)

    # ----- Risks & caveats -----
    risk_data = {
        "data_quality": state.get("data_quality", {}),
        "trends": {t: _trend_block(trends.get(t, {})) for t in tickers},
    }
    sections["risks"] = _write_section(
        "risks", SECTION_BRIEFS["risks"],
        json.dumps(risk_data, indent=2)[:5000], [], critique)

    # Legacy concatenated blob (some downstream code / the critic still reads it)
    blob_parts = []
    for sid, text in sections.items():
        blob_parts.append(f"## {sid}\n\n{text}\n")
    insights_blob = "\n".join(blob_parts)

    log.append(
        f"Analyst: produced {'revised' if is_revision else 'initial'} "
        f"section analyses ({len(sections)} sections)"
    )
    return {**state,
            "section_analysis": sections,
            "insights": insights_blob,
            "log": log}

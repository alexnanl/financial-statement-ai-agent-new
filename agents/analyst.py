"""Analyst Agent (Insight Generator).

Takes the structured ratios + comparisons and asks the LLM to write
prose insights. May be invoked twice: once for the initial draft, then
again to revise after the Critic gives feedback.
"""
import json
from state import AnalysisState
from utils.llm import chat
from utils.ratios import RATIO_LABELS, RATIO_CATEGORIES


SYSTEM_PROMPT = """You are a senior financial analyst. Given quantitative \
ratio data, write clear, evidence-based insights for a business reader.

Rules:
1. Cite specific numbers from the provided data. Never invent figures.
2. Compare across years to flag trends (improving / deteriorating / stable).
3. If comparing companies, name which is stronger on each dimension and why.
4. Acknowledge limitations: missing data, single-year context, etc.
5. Use markdown with clear section headings.
6. Be concise. Aim for ~400-700 words. Prioritize the most material findings.
7. Avoid generic disclaimers. Avoid hedging language like "could potentially perhaps".
"""


def _format_ratios_for_llm(ratios: dict) -> str:
    """Render ratios as a compact JSON-ish block the LLM can parse."""
    out = {}
    for ticker, by_year in ratios.items():
        out[ticker] = {}
        for year, ratio_dict in by_year.items():
            # Strip _raw for prompt brevity; round for legibility
            clean = {}
            for k, v in ratio_dict.items():
                if k == "_raw" or v is None:
                    continue
                clean[RATIO_LABELS.get(k, k)] = round(v, 4)
            out[ticker][year] = clean
    return json.dumps(out, indent=2)


def _format_comparison(comp: dict) -> str:
    if not comp:
        return ""
    rankings = comp.get("rankings", {})
    win_tally = comp.get("win_tally", {})
    lines = ["Win tally (number of ratios where each company ranks #1):"]
    for ticker, wins in sorted(win_tally.items(), key=lambda x: -x[1]):
        lines.append(f"  - {ticker}: {wins}")
    lines.append("\nPer-ratio best performer:")
    for key, r in rankings.items():
        lines.append(f"  - {r['label']}: best={r['best']}, worst={r['worst']}")
    return "\n".join(lines)


def analyst_agent(state: AnalysisState) -> AnalysisState:
    log = state.get("log", [])
    ratios = state.get("ratios", {})
    comparison = state.get("comparison", {})
    analysis_type = state.get("analysis_type", "single")
    focus = state.get("focus_areas", [])
    critique = state.get("critique", "")
    tickers = list(ratios.keys())

    if not ratios:
        return {
            **state,
            "insights": "_No ratios were computed; cannot generate insights._",
            "log": log + ["Analyst: no ratios available"],
        }

    # Build prompt
    parts = [
        f"Analysis type: {analysis_type}",
        f"Companies: {', '.join(tickers)}",
        f"Focus areas: {', '.join(focus)}",
        "",
        "=== Ratio data (by ticker / year) ===",
        _format_ratios_for_llm(ratios),
    ]
    comp_text = _format_comparison(comparison)
    if comp_text:
        parts += ["", "=== Comparison summary ===", comp_text]

    # If this is a revision pass, include the critic's notes
    is_revision = bool(critique)
    if is_revision:
        parts += [
            "",
            "=== Critic feedback to address in this revision ===",
            critique,
            "",
            "Revise your previous analysis to address every point above.",
        ]

    parts += [
        "",
        "Write the analysis now in markdown.",
        "Required sections: ## Overview, ## Key Findings, ## Per-Company Analysis "
        "(one subsection per company), "
        + ("## Head-to-Head Comparison, " if analysis_type == "comparison" else "")
        + "## Risks & Caveats."
    ]

    user_prompt = "\n".join(parts)

    try:
        insights = chat(SYSTEM_PROMPT, user_prompt, temperature=0.3)
        log.append(
            f"Analyst: produced {'revised' if is_revision else 'initial'} "
            f"insights ({len(insights)} chars)"
        )
        return {**state, "insights": insights, "log": log}
    except Exception as e:
        return {
            **state,
            "insights": f"_Analyst failed: {e}_",
            "log": log + [f"Analyst: error {e}"],
        }

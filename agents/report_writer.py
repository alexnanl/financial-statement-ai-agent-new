"""Report Writer Agent.

Assembles four output formats from the agent state:
  - Markdown (.md): text with [CHART: name] placeholders preserved
  - HTML (.html): images embedded base64; styled for clean viewing
  - DOCX (.docx): proper Word document with embedded chart images
  - PDF (.pdf): converted from HTML using WeasyPrint or fallback to reportlab

The Analyst's insights contain [CHART: name] markers; each format resolves
these to the appropriate image inclusion.
"""
import os
import re
import base64
from datetime import datetime
from pathlib import Path

import markdown as md_lib
from state import AnalysisState
from utils.ratios import RATIO_LABELS, RATIO_CATEGORIES, PERCENT_RATIOS


# ===== Helpers =====

def _fmt(val, as_pct: bool = False) -> str:
    if val is None:
        return "—"
    if as_pct:
        return f"{val * 100:.1f}%"
    return f"{val:.2f}"


def _make_ratio_table_md(by_year: dict) -> str:
    """Markdown ratio table for one ticker."""
    if not by_year:
        return "_No data._"
    years = sorted(by_year.keys(), reverse=True)
    header = "| Ratio | " + " | ".join(years) + " |"
    sep = "|" + "---|" * (len(years) + 1)
    rows = [header, sep]
    for category, keys in RATIO_CATEGORIES.items():
        rows.append(f"| **{category}** |" + " |" * len(years))
        for key in keys:
            label = RATIO_LABELS[key]
            as_pct = key in PERCENT_RATIOS
            cells = [_fmt(by_year[y].get(key), as_pct) for y in years]
            rows.append(f"| {label} | " + " | ".join(cells) + " |")
    return "\n".join(rows)


def _make_dupont_table_md(by_year: dict) -> str:
    """DuPont decomposition table."""
    years = sorted(by_year.keys(), reverse=True)
    if not years:
        return "_No DuPont data._"

    components = [
        ("Net Margin", "net_margin", True),
        ("Asset Turnover", "asset_turnover", False),
        ("Equity Multiplier", "equity_multiplier", False),
        ("→ ROE (3-step product)", "roe_3step", True),
        ("Tax Burden", "tax_burden", False),
        ("Interest Burden", "interest_burden", False),
        ("Operating Margin", "operating_margin", True),
        ("→ ROE (5-step product)", "roe_5step", True),
    ]
    header = "| Component | " + " | ".join(years) + " |"
    sep = "|" + "---|" * (len(years) + 1)
    rows = [header, sep]
    for label, key, as_pct in components:
        cells = []
        for y in years:
            d = by_year[y].get("_dupont", {})
            cells.append(_fmt(d.get(key), as_pct))
        rows.append(f"| {label} | " + " | ".join(cells) + " |")
    return "\n".join(rows)


def _make_trend_table_md(trends_for_ticker: dict) -> str:
    """Trend summary table."""
    rows = ["| Ratio | Direction | CAGR | First | Last |",
            "|---|---|---|---|---|"]
    for ratio_key, t in trends_for_ticker.items():
        if t["direction"] == "insufficient_data":
            continue
        label = RATIO_LABELS.get(ratio_key, ratio_key)
        cagr = f"{t['cagr']*100:.1f}%" if t["cagr"] is not None else "—"
        as_pct = ratio_key in PERCENT_RATIOS
        first = f"{t['first_year']}: {_fmt(t['first_value'], as_pct)}" if t["first_value"] is not None else "—"
        last = f"{t['last_year']}: {_fmt(t['last_value'], as_pct)}" if t["last_value"] is not None else "—"
        direction = t["direction"].replace("_", " ")
        rows.append(f"| {label} | {direction} | {cagr} | {first} | {last} |")
    if len(rows) == 2:
        return "_Insufficient data for trend analysis._"
    return "\n".join(rows)


def _make_peer_table_md(peer_analysis_for_primary: dict) -> str:
    """Peer benchmark table."""
    rows = ["| Ratio | Company | Peer Avg | Peer Median | Percentile |",
            "|---|---|---|---|---|"]
    for ratio_key, d in peer_analysis_for_primary.items():
        label = RATIO_LABELS.get(ratio_key, ratio_key)
        as_pct = ratio_key in PERCENT_RATIOS
        rows.append(
            f"| {label} | {_fmt(d['primary_value'], as_pct)} "
            f"| {_fmt(d['peer_average'], as_pct)} "
            f"| {_fmt(d['peer_median'], as_pct)} "
            f"| {d['percentile_rank']:.0f}th |"
        )
    return "\n".join(rows) if len(rows) > 2 else "_No peer benchmarks available._"


def _make_comparison_table_md(comparison: dict) -> str:
    if not comparison:
        return ""
    rankings = comparison.get("rankings", {})
    snapshots = comparison.get("snapshots", {})
    tickers = list(snapshots.keys())
    if not tickers:
        return ""
    header = "| Ratio | " + " | ".join(tickers) + " | Best |"
    sep = "|" + "---|" * (len(tickers) + 2)
    rows = [header, sep]
    for key, r in rankings.items():
        as_pct = key in PERCENT_RATIOS
        cells = [_fmt(r["values"].get(t), as_pct) for t in tickers]
        rows.append(f"| {r['label']} | " + " | ".join(cells) + f" | **{r['best']}** |")
    return "\n".join(rows)


def _build_markdown(state: AnalysisState) -> str:
    """Build the full markdown report. [CHART: name] markers stay in place."""
    tickers = state.get("tickers", [])
    raw = state.get("raw_data", {})
    quality = state.get("data_quality", {})
    ratios = state.get("ratios", {})
    trends = state.get("trends", {})
    peers_map = state.get("peers", {})
    peer_analysis = state.get("peer_analysis", {})
    comparison = state.get("comparison", {})
    insights = state.get("insights", "_No insights generated._")
    critique = state.get("critique", "")
    query = state.get("user_query", "")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    parts = [
        "# Financial Statement Analysis Report",
        f"*Generated {now}*",
        "",
        f"**Original request:** {query}",
        "",
        "---",
        "",
        "## Companies Analyzed",
        "",
    ]
    for t in tickers:
        info = raw.get(t, {}).get("info", {})
        name = info.get("longName", t)
        sector = info.get("sector", "Unknown")
        industry = info.get("industry", "Unknown")
        mcap = info.get("marketCap")
        mcap_str = f" — ${mcap/1e9:.1f}B market cap" if mcap else ""
        parts.append(f"- **{t}** — {name} *({sector} / {industry}{mcap_str})*")
    parts.append("")

    # Peers
    if peers_map:
        parts += ["", "## Peer Companies (AI-Selected)", ""]
        for primary, peer_list in peers_map.items():
            if peer_list:
                parts.append(f"- **{primary}** peers: {', '.join(peer_list)}")
        parts.append("")

    # Data quality
    parts += ["---", "", "## Data Quality Review", "",
              "| Ticker | Completeness | Status | Issues |",
              "|---|---|---|---|"]
    for t, q in quality.items():
        issues = "; ".join(q.get("issues", [])) or "None"
        parts.append(
            f"| {t} | {q['completeness']*100:.0f}% | "
            f"{'✅ Pass' if q['status'] == 'pass' else '❌ Fail'} | {issues} |"
        )
    parts.append("")

    # Insights (with chart markers preserved)
    parts += ["---", "", "## Analyst Insights", "", insights, ""]

    if critique:
        parts += ["---", "", "## Critic Review", "",
                  "_The critic agent reviewed the analyst's draft for accuracy "
                  "and completeness before approval._", "", f"> {critique}", ""]

    # Detailed ratios per ticker
    parts += ["---", "", "## Detailed Ratios", ""]
    for t in tickers:
        if t in ratios:
            parts += [f"### {t}", "", _make_ratio_table_md(ratios[t]), ""]
            parts += [f"#### {t}: DuPont Decomposition", "",
                      _make_dupont_table_md(ratios[t]), ""]
            parts += [f"[CHART: dupont_{t}]", ""]
            if t in trends:
                parts += [f"#### {t}: Trend Analysis", "",
                          _make_trend_table_md(trends[t]), ""]
                parts += [f"[CHART: profitability_{t}]", ""]
            if t in peer_analysis:
                parts += [f"#### {t}: Peer Benchmarking", "",
                          _make_peer_table_md(peer_analysis[t]), ""]

    # Multi-company comparison
    comp_table = _make_comparison_table_md(comparison)
    if comp_table:
        parts += ["---", "", "## Side-by-Side Comparison (Most Recent Year)",
                  "", comp_table, "", "[CHART: win_tally]", ""]

    # Methodology
    parts += ["---", "", "## Methodology", "",
              "This report was generated by a multi-agent workflow: Planner → "
              "Retriever → Peer Selector → Peer Retriever → Validator → "
              "Ratios → Trend Analyzer → Comparator → Peer Analyzer → "
              "Chart Builder → Analyst (with vision) → Critic → Report Writer. "
              "Data: Yahoo Finance. Ratios and DuPont decomposition computed "
              "deterministically; narrative insights generated by AI from numerical "
              "tables and chart images, then reviewed by a critic agent.",
              "", "*Not investment advice.*"]

    return "\n".join(parts)


def _resolve_charts_for_html(md_text: str, charts: dict) -> str:
    """Replace [CHART: name] with <img> tags containing base64-embedded PNGs."""
    def repl(match):
        name = match.group(1).strip()
        path = charts.get(name)
        if not path or not os.path.exists(path):
            return f"<!-- chart {name} unavailable -->"
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return (f'<div class="chart"><img src="data:image/png;base64,{b64}" '
                f'alt="{name}" style="max-width:100%;height:auto;"/></div>')
    return re.sub(r"\[CHART:\s*([a-zA-Z0-9_]+)\s*\]", repl, md_text)


HTML_TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Financial Analysis Report</title>
<style>
  body {{ font-family: -apple-system, "Segoe UI", Helvetica, sans-serif;
         max-width: 920px; margin: 40px auto; padding: 0 20px; color: #1a1d23;
         line-height: 1.55; }}
  h1 {{ color: #1F3A68; border-bottom: 3px solid #1F3A68; padding-bottom: 8px; }}
  h2 {{ color: #2E5994; margin-top: 32px; border-bottom: 1px solid #e0e4e8; padding-bottom: 4px; }}
  h3 {{ color: #333; margin-top: 24px; }}
  h4 {{ color: #555; }}
  table {{ border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 14px; }}
  th {{ background: #1F3A68; color: white; padding: 8px 12px; text-align: left; }}
  td {{ padding: 6px 12px; border-bottom: 1px solid #e0e4e8; }}
  tr:nth-child(even) td {{ background: #f8f9fa; }}
  code {{ background: #f4f6f8; padding: 2px 6px; border-radius: 3px; font-size: 90%; }}
  blockquote {{ border-left: 4px solid #f2b400; background: #fff8e1;
                padding: 8px 16px; margin: 12px 0; }}
  .chart {{ margin: 20px 0; text-align: center; }}
  .chart img {{ border: 1px solid #e0e4e8; border-radius: 4px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.06); }}
  hr {{ border: none; border-top: 1px solid #e0e4e8; margin: 24px 0; }}
</style></head>
<body>
{body}
</body></html>"""


def _build_html(md_text: str, charts: dict) -> str:
    """Convert markdown -> HTML with embedded charts."""
    md_with_imgs = _resolve_charts_for_html(md_text, charts)
    body = md_lib.markdown(md_with_imgs, extensions=["tables", "fenced_code"])
    return HTML_TEMPLATE.format(body=body)


def _build_docx(state: AnalysisState, md_text: str, charts: dict, out_path: str) -> str:
    """Build a Word document with embedded chart images."""
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()
    # Default style
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    # Process markdown line-by-line - simple but works for our generated content
    lines = md_text.split("\n")
    in_table = False
    table_rows = []

    def flush_table():
        nonlocal table_rows, in_table
        if not table_rows:
            in_table = False
            return
        # Parse cells
        rows_data = []
        for row in table_rows:
            cells = [c.strip() for c in row.strip("|").split("|")]
            rows_data.append(cells)
        # Skip alignment separator row
        rows_data = [r for r in rows_data if not all(set(c) <= set("-: ") for c in r)]
        if not rows_data:
            table_rows = []
            in_table = False
            return
        ncols = max(len(r) for r in rows_data)
        table = doc.add_table(rows=len(rows_data), cols=ncols)
        table.style = "Light Grid Accent 1"
        for i, row_data in enumerate(rows_data):
            for j, cell_text in enumerate(row_data):
                if j < ncols:
                    cell = table.cell(i, j)
                    cell.text = cell_text.replace("**", "")
                    if i == 0:
                        for run in cell.paragraphs[0].runs:
                            run.bold = True
        doc.add_paragraph()
        table_rows = []
        in_table = False

    for line in lines:
        stripped = line.strip()

        # Tables
        if stripped.startswith("|") and stripped.endswith("|"):
            in_table = True
            table_rows.append(line)
            continue
        elif in_table:
            flush_table()

        # Headings
        if stripped.startswith("# "):
            p = doc.add_heading(stripped[2:], level=0)
        elif stripped.startswith("## "):
            doc.add_heading(stripped[3:], level=1)
        elif stripped.startswith("### "):
            doc.add_heading(stripped[4:], level=2)
        elif stripped.startswith("#### "):
            doc.add_heading(stripped[5:], level=3)
        # Horizontal rule
        elif stripped == "---":
            p = doc.add_paragraph()
            p_run = p.add_run("─" * 40)
            p_run.font.color.rgb = RGBColor(0xCC, 0xCC, 0xCC)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        # Chart marker
        elif stripped.startswith("[CHART:") and stripped.endswith("]"):
            chart_name = stripped[7:-1].strip()
            path = charts.get(chart_name)
            if path and os.path.exists(path):
                try:
                    doc.add_picture(path, width=Inches(6.0))
                    # Center the image
                    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
                except Exception:
                    pass
        # Blockquote
        elif stripped.startswith("> "):
            p = doc.add_paragraph()
            run = p.add_run(stripped[2:])
            run.italic = True
            p.paragraph_format.left_indent = Inches(0.4)
        # Bullet
        elif stripped.startswith("- "):
            p = doc.add_paragraph(stripped[2:].replace("**", ""), style="List Bullet")
        # Italic-only line
        elif stripped.startswith("*") and stripped.endswith("*") and not stripped.startswith("**"):
            p = doc.add_paragraph()
            run = p.add_run(stripped[1:-1])
            run.italic = True
        elif stripped:
            # Regular paragraph - handle **bold** inline
            p = doc.add_paragraph()
            parts = re.split(r"(\*\*.+?\*\*)", stripped)
            for part in parts:
                if part.startswith("**") and part.endswith("**"):
                    run = p.add_run(part[2:-2])
                    run.bold = True
                else:
                    p.add_run(part)

    if in_table:
        flush_table()

    doc.save(out_path)
    return out_path


def _build_pdf(html_content: str, out_path: str) -> str | None:
    """Convert HTML to PDF using WeasyPrint."""
    try:
        from weasyprint import HTML
        HTML(string=html_content).write_pdf(out_path)
        return out_path
    except Exception as e:
        # Fallback: write a note that PDF generation failed
        print(f"PDF generation failed: {e}")
        return None


def report_writer_agent(state: AnalysisState) -> AnalysisState:
    log = state.get("log", [])
    working_dir = state.get("working_dir", "/tmp")
    charts = state.get("charts", {})

    md_text = _build_markdown(state)
    html_text = _build_html(md_text, charts)

    docx_path = os.path.join(working_dir, "financial_analysis.docx")
    pdf_path = os.path.join(working_dir, "financial_analysis.pdf")

    try:
        _build_docx(state, md_text, charts, docx_path)
        log.append(f"Report Writer: DOCX written -> {docx_path}")
    except Exception as e:
        docx_path = ""
        log.append(f"Report Writer: DOCX failed ({e})")

    pdf_result = _build_pdf(html_text, pdf_path)
    if pdf_result:
        log.append(f"Report Writer: PDF written -> {pdf_path}")
    else:
        pdf_path = ""
        log.append("Report Writer: PDF generation failed (WeasyPrint missing?)")

    log.append(f"Report Writer: markdown {len(md_text)} chars, HTML {len(html_text)} chars")

    return {**state,
            "final_report_md": md_text,
            "final_report_html": html_text,
            "final_report_docx_path": docx_path,
            "final_report_pdf_path": pdf_path,
            "log": log}

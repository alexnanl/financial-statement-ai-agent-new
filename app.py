"""Streamlit web interface v2 for the Financial Statement Analysis Agent.

Key changes vs v1:
  - No API key UI input (read only from environment/secrets for security)
  - Inline chart rendering in the report tab
  - Multi-format download: MD, HTML, DOCX, PDF
  - DuPont, Trend, and Peer analysis tabs
"""
import os
import re
import streamlit as st
import pandas as pd

from workflow import run_analysis
from utils.ratios import RATIO_LABELS, RATIO_CATEGORIES
from config import get_openai_key


# ---------- Page setup ----------
st.set_page_config(
    page_title="Financial Statement Analyst",
    page_icon="📊",
    layout="wide",
)

st.markdown("""
<style>
    .main-title { font-size: 2.4rem; font-weight: 700; margin-bottom: 0; }
    .subtitle { color: #6c7080; margin-top: 0; font-size: 1rem; }
    .agent-step {
        padding: 6px 10px; border-left: 3px solid #4f8cff;
        background: #f5f8ff; margin: 4px 0; font-family: monospace;
        font-size: 0.85rem; border-radius: 2px;
    }
    div[data-testid="stMetric"] {
        background: #fafbfc; padding: 12px; border-radius: 8px;
        border: 1px solid #e8eaed;
    }
</style>
""", unsafe_allow_html=True)

# ---------- Header ----------
st.markdown('<p class="main-title">📊 Financial Statement Analyst</p>',
            unsafe_allow_html=True)
st.markdown('<p class="subtitle">Multi-agent workflow with DuPont · Trend · '
            'Peer analysis · Vision-enabled AI</p>',
            unsafe_allow_html=True)

# ---------- API key check (silent unless missing) ----------
api_key_present = bool(get_openai_key())

# ---------- Sidebar ----------
with st.sidebar:
    st.header("⚙️ Status")
    if api_key_present:
        st.success("✅ API key configured")
    else:
        st.error("❌ OpenAI API key not configured")
        st.markdown(
            "The app requires `OPENAI_API_KEY` to be set in:\n"
            "- Environment variable, OR\n"
            "- `.streamlit/secrets.toml` (local), OR\n"
            "- Streamlit Cloud → App Settings → Secrets"
        )
        st.markdown(
            "**Security note:** keys are never accepted via the UI to prevent "
            "accidental exposure in shared sessions."
        )

    st.divider()
    st.subheader("💡 Example Queries")
    examples = [
        "Analyze Apple's financial health over the last 4 years",
        "Compare Microsoft and Google on profitability and DuPont",
        "How is Tesla's ROE trending? Decompose with DuPont and compare to peers",
        "Compare NVDA, AMD, and INTC financial performance with peer benchmarks",
    ]
    for ex in examples:
        if st.button(ex, key=f"ex_{ex}", use_container_width=True):
            st.session_state["pending_query"] = ex
            st.rerun()

    st.divider()
    st.caption(
        "Data: Yahoo Finance · LLM: OpenAI (gpt-4o + vision) · "
        "Orchestration: LangGraph · UI: Streamlit"
    )

# ---------- Query input ----------
query = st.text_area(
    "What would you like to analyze?",
    value=st.session_state.pop("pending_query", ""),
    height=80,
    placeholder="e.g., Compare Apple and Microsoft with DuPont decomposition and peer benchmarks",
)

run = st.button("🚀 Run Analysis", type="primary", use_container_width=True,
                disabled=not api_key_present)

if not api_key_present and run:
    st.error("Cannot run: OpenAI API key not configured.")
    st.stop()

# ---------- Execute ----------
if run:
    if not query.strip():
        st.warning("Please enter a query first.")
        st.stop()

    with st.status("🤖 Running agent workflow...", expanded=True) as status:
        st.write("Workflow has 13 agents - this may take 30-90 seconds...")
        try:
            result = run_analysis(query)
            status.update(label="✅ Analysis complete", state="complete")
        except Exception as e:
            status.update(label="❌ Workflow error", state="error")
            st.exception(e)
            st.stop()

    st.session_state["last_result"] = result


# ---------- Helper: render markdown with embedded chart images ----------
def render_md_with_charts(md_text: str, charts: dict):
    """Split markdown on [CHART: name] markers and render mixed content."""
    chunks = re.split(r"(\[CHART:\s*[a-zA-Z0-9_]+\s*\])", md_text)
    for chunk in chunks:
        m = re.match(r"\[CHART:\s*([a-zA-Z0-9_]+)\s*\]", chunk)
        if m:
            name = m.group(1)
            path = charts.get(name)
            if path and os.path.exists(path):
                st.image(path, use_column_width=True)
        else:
            if chunk.strip():
                st.markdown(chunk)


# ---------- Render results ----------
if "last_result" in st.session_state:
    result = st.session_state["last_result"]

    if result.get("error") and not result.get("ratios"):
        st.error(f"⚠️ {result['error']}")
        with st.expander("Show workflow log"):
            for line in result.get("log", []):
                st.markdown(f'<div class="agent-step">{line}</div>',
                            unsafe_allow_html=True)
        st.stop()

    # Summary metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Companies", len(result.get("tickers", [])))
    col2.metric("Analysis Type", result.get("analysis_type", "—").title())
    col3.metric("Years", result.get("years", "—"))
    col4.metric("Critic Rounds", result.get("critic_round", 0))
    col5.metric("Charts", len(result.get("charts", {})))

    # Tabs
    tab_report, tab_dupont, tab_trends, tab_peers, tab_ratios, tab_compare, tab_dl, tab_log = st.tabs([
        "📄 Report", "🔬 DuPont", "📈 Trends", "👥 Peers",
        "📊 Ratios", "⚖️ Comparison", "💾 Download", "🔍 Workflow Log",
    ])

    # ----- REPORT tab -----
    with tab_report:
        md_text = result.get("final_report_md", "_No report._")
        charts = result.get("charts", {})
        render_md_with_charts(md_text, charts)

    # ----- DUPONT tab -----
    with tab_dupont:
        ratios = result.get("ratios", {})
        charts = result.get("charts", {})
        if not ratios:
            st.info("No DuPont data available.")
        else:
            for ticker, by_year in ratios.items():
                st.subheader(f"{ticker} — DuPont Decomposition")
                years = sorted(by_year.keys(), reverse=True)
                rows = []
                components = [
                    ("Net Margin", "net_margin", True),
                    ("Asset Turnover", "asset_turnover", False),
                    ("Equity Multiplier", "equity_multiplier", False),
                    ("ROE (3-step)", "roe_3step", True),
                    ("Tax Burden", "tax_burden", False),
                    ("Interest Burden", "interest_burden", False),
                    ("Operating Margin", "operating_margin", True),
                    ("ROE (5-step)", "roe_5step", True),
                ]
                for label, key, as_pct in components:
                    row = {"Component": label}
                    for y in years:
                        d = by_year[y].get("_dupont", {})
                        v = d.get(key)
                        if v is None:
                            row[y] = "—"
                        elif as_pct:
                            row[y] = f"{v*100:.2f}%"
                        else:
                            row[y] = f"{v:.3f}"
                    rows.append(row)
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

                chart_path = charts.get(f"dupont_{ticker}")
                if chart_path and os.path.exists(chart_path):
                    st.image(chart_path, use_column_width=True)

    # ----- TRENDS tab -----
    with tab_trends:
        trends = result.get("trends", {})
        charts = result.get("charts", {})
        if not trends:
            st.info("No trend data available.")
        else:
            for ticker, ticker_trends in trends.items():
                st.subheader(f"{ticker} — Trend Analysis")
                rows = []
                for ratio_key, t in ticker_trends.items():
                    if t["direction"] == "insufficient_data":
                        continue
                    rows.append({
                        "Ratio": RATIO_LABELS.get(ratio_key, ratio_key),
                        "Direction": t["direction"].replace("_", " "),
                        "CAGR": f"{t['cagr']*100:.1f}%" if t["cagr"] is not None else "—",
                        "First Year": t["first_year"] or "—",
                        "Last Year": t["last_year"] or "—",
                        "Volatility": f"{t['volatility']:.2f}" if t["volatility"] else "—",
                    })
                if rows:
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

                # Profitability chart
                p_chart = charts.get(f"profitability_{ticker}")
                if p_chart and os.path.exists(p_chart):
                    st.image(p_chart, use_column_width=True)

    # ----- PEERS tab -----
    with tab_peers:
        peers = result.get("peers", {})
        peer_analysis = result.get("peer_analysis", {})
        charts = result.get("charts", {})
        if not peer_analysis:
            st.info("No peer analysis available.")
        else:
            for primary, ratios_dict in peer_analysis.items():
                st.subheader(f"{primary} — Peer Benchmarking")
                st.write(f"**AI-selected peers:** {', '.join(peers.get(primary, []))}")
                rows = []
                for ratio_key, d in ratios_dict.items():
                    as_pct = ratio_key in {"gross_margin", "operating_margin",
                                           "net_margin", "roa", "roe", "fcf_margin"}
                    def fmt(v):
                        return f"{v*100:.1f}%" if as_pct else f"{v:.2f}"
                    rows.append({
                        "Ratio": RATIO_LABELS.get(ratio_key, ratio_key),
                        primary: fmt(d["primary_value"]),
                        "Peer Avg": fmt(d["peer_average"]),
                        "Peer Median": fmt(d["peer_median"]),
                        "Percentile Rank": f"{d['percentile_rank']:.0f}th",
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

                # Display first few peer charts
                for ratio_key in ["roe", "roa", "net_margin", "debt_to_equity"]:
                    chart_path = charts.get(f"peer_{primary}_{ratio_key}")
                    if chart_path and os.path.exists(chart_path):
                        st.image(chart_path, use_column_width=True)

    # ----- RATIOS tab -----
    with tab_ratios:
        ratios = result.get("ratios", {})
        if not ratios:
            st.info("No ratios computed.")
        else:
            for ticker, by_year in ratios.items():
                st.subheader(ticker)
                years = sorted(by_year.keys(), reverse=True)
                rows = []
                for category, keys in RATIO_CATEGORIES.items():
                    for key in keys:
                        row = {"Category": category, "Ratio": RATIO_LABELS[key]}
                        for y in years:
                            v = by_year[y].get(key)
                            row[y] = round(v, 4) if v is not None else None
                        rows.append(row)
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # ----- COMPARISON tab -----
    with tab_compare:
        comp = result.get("comparison", {})
        charts = result.get("charts", {})
        if not comp:
            st.info("Comparison view is only populated for multi-company analyses.")
        else:
            rankings = comp.get("rankings", {})
            snapshots = comp.get("snapshots", {})
            tickers = list(snapshots.keys())

            st.subheader("Side-by-side ratios (most recent year)")
            rows = []
            for key, r in rankings.items():
                row = {"Ratio": r["label"]}
                for t in tickers:
                    v = r["values"].get(t)
                    row[t] = round(v, 4) if v is not None else None
                row["Best"] = r["best"]
                rows.append(row)
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            # Win tally chart
            wt_chart = charts.get("win_tally")
            if wt_chart and os.path.exists(wt_chart):
                st.image(wt_chart, use_column_width=True)

            # Comparison line charts
            for ratio_key in ["roe", "roa", "net_margin", "debt_to_equity"]:
                cp = charts.get(f"compare_{ratio_key}")
                if cp and os.path.exists(cp):
                    st.image(cp, use_column_width=True)

    # ----- DOWNLOAD tab -----
    with tab_dl:
        st.subheader("Download Report")
        st.write("The report contains all tables, charts, and AI-generated insights.")

        col_a, col_b = st.columns(2)

        with col_a:
            # Markdown
            md = result.get("final_report_md", "")
            st.download_button(
                "📝 Markdown (.md)",
                data=md,
                file_name="financial_analysis.md",
                mime="text/markdown",
                use_container_width=True,
            )

            # HTML
            html = result.get("final_report_html", "")
            st.download_button(
                "🌐 HTML (.html) — embedded charts",
                data=html,
                file_name="financial_analysis.html",
                mime="text/html",
                use_container_width=True,
            )

        with col_b:
            # DOCX
            docx_path = result.get("final_report_docx_path", "")
            if docx_path and os.path.exists(docx_path):
                with open(docx_path, "rb") as f:
                    st.download_button(
                        "📄 Word (.docx) — embedded charts",
                        data=f.read(),
                        file_name="financial_analysis.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True,
                    )
            else:
                st.button("📄 Word (.docx) — unavailable", disabled=True,
                          use_container_width=True)

            # PDF
            pdf_path = result.get("final_report_pdf_path", "")
            if pdf_path and os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        "📕 PDF (.pdf) — embedded charts",
                        data=f.read(),
                        file_name="financial_analysis.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )
            else:
                st.button("📕 PDF — install WeasyPrint to enable",
                          disabled=True, use_container_width=True)

    # ----- LOG tab -----
    with tab_log:
        st.markdown("**Agent execution trail:**")
        for line in result.get("log", []):
            st.markdown(f'<div class="agent-step">{line}</div>',
                        unsafe_allow_html=True)

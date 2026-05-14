"""Streamlit web interface for the Financial Statement Analysis Agent.

Run with:
    streamlit run app.py
"""
import os
import streamlit as st
import pandas as pd

from workflow import run_analysis
from utils.ratios import RATIO_LABELS, RATIO_CATEGORIES


# ---------- Page setup ----------
st.set_page_config(
    page_title="Financial Statement Analyst",
    page_icon="📊",
    layout="wide",
)

# Light custom styling
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
st.markdown('<p class="subtitle">Multi-agent workflow • Planner → Retriever → '
            'Validator → Ratios → Comparator → Analyst → Critic → Report</p>',
            unsafe_allow_html=True)

# ---------- Sidebar: API key + examples ----------
with st.sidebar:
    st.header("⚙️ Configuration")

    api_key_input = st.text_input(
        "OpenAI API Key",
        type="password",
        value=os.getenv("OPENAI_API_KEY", ""),
        help="Stored only in session memory; never written to disk.",
    )
    if api_key_input:
        os.environ["OPENAI_API_KEY"] = api_key_input

    st.divider()
    st.subheader("💡 Example Queries")
    examples = [
        "Analyze Apple's financial health over the last 4 years",
        "Compare Microsoft and Google on profitability and cash flow",
        "How is Tesla's liquidity and leverage trending?",
        "Compare NVDA, AMD, and INTC financial performance",
    ]
    for ex in examples:
        if st.button(ex, key=f"ex_{ex}", use_container_width=True):
            st.session_state["pending_query"] = ex
            st.rerun()

    st.divider()
    st.caption(
        "Data: Yahoo Finance · LLM: OpenAI · "
        "Orchestration: LangGraph · UI: Streamlit"
    )

# ---------- Query input ----------
query = st.text_area(
    "What would you like to analyze?",
    value=st.session_state.pop("pending_query", ""),
    height=80,
    placeholder="e.g., Compare Apple and Microsoft's profitability and liquidity over the last 3 years",
)

run = st.button("🚀 Run Analysis", type="primary", use_container_width=True)

# ---------- Execute ----------
if run:
    if not query.strip():
        st.warning("Please enter a query first.")
        st.stop()
    if not os.getenv("OPENAI_API_KEY"):
        st.error("Please enter your OpenAI API key in the sidebar.")
        st.stop()

    with st.status("🤖 Running agent workflow...", expanded=True) as status:
        st.write("Initializing workflow graph...")
        try:
            result = run_analysis(query)
            status.update(label="✅ Analysis complete", state="complete")
        except Exception as e:
            status.update(label=f"❌ Workflow error", state="error")
            st.exception(e)
            st.stop()

    # Store in session so it survives reruns
    st.session_state["last_result"] = result

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

    # Top-level summary metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Companies", len(result.get("tickers", [])))
    col2.metric("Analysis Type", result.get("analysis_type", "—").title())
    col3.metric("Years", result.get("years", "—"))
    col4.metric("Critic Rounds", result.get("critic_round", 0))

    # Tabs for the different views
    tab_report, tab_ratios, tab_compare, tab_log = st.tabs([
        "📄 Report",
        "📈 Ratios",
        "⚖️ Comparison",
        "🔬 Workflow Log",
    ])

    with tab_report:
        st.markdown(result.get("final_report", "_No report generated._"))
        st.download_button(
            "💾 Download Report (Markdown)",
            data=result.get("final_report", ""),
            file_name="financial_analysis.md",
            mime="text/markdown",
        )

    with tab_ratios:
        ratios = result.get("ratios", {})
        if not ratios:
            st.info("No ratios were computed.")
        else:
            for ticker, by_year in ratios.items():
                st.subheader(ticker)
                # Build a clean DataFrame for display
                years = sorted(by_year.keys(), reverse=True)
                rows = []
                for category, keys in RATIO_CATEGORIES.items():
                    for key in keys:
                        row = {"Category": category, "Ratio": RATIO_LABELS[key]}
                        for y in years:
                            v = by_year[y].get(key)
                            row[y] = round(v, 4) if v is not None else None
                        rows.append(row)
                df = pd.DataFrame(rows)
                st.dataframe(df, use_container_width=True, hide_index=True)

                # Trend chart for key margins
                if len(years) > 1:
                    chart_keys = ["gross_margin", "operating_margin", "net_margin", "roe"]
                    chart_rows = []
                    for y in sorted(years):
                        for k in chart_keys:
                            v = by_year[y].get(k)
                            if v is not None:
                                chart_rows.append({
                                    "Year": y,
                                    "Metric": RATIO_LABELS[k],
                                    "Value": v,
                                })
                    if chart_rows:
                        chart_df = pd.DataFrame(chart_rows)
                        pivot = chart_df.pivot(index="Year", columns="Metric",
                                               values="Value")
                        st.line_chart(pivot)

    with tab_compare:
        comp = result.get("comparison", {})
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

            st.subheader("Win tally (ratios where each company ranks #1)")
            tally_df = pd.DataFrame(
                [{"Company": t, "Wins": w}
                 for t, w in sorted(comp["win_tally"].items(),
                                    key=lambda x: -x[1])]
            )
            st.bar_chart(tally_df.set_index("Company"))

    with tab_log:
        st.markdown("**Agent execution trail** — each line is one decision/step:")
        for line in result.get("log", []):
            st.markdown(f'<div class="agent-step">{line}</div>',
                        unsafe_allow_html=True)
        with st.expander("Raw state (for debugging)"):
            debug = {k: v for k, v in result.items()
                     if k not in {"raw_data", "final_report"}}
            st.json(debug, expanded=False)

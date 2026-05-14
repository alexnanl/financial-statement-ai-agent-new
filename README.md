# Financial Statement Analysis AI Agent — v2

A **multi-agent workflow** for end-to-end financial statement analysis with **DuPont decomposition, trend analysis, and AI-driven peer benchmarking**. The Analyst is vision-enabled: it reads the generated charts and writes insights from them.

## What's new in v2

- **🔒 Security:** API key never accepted via UI — read only from env / secrets
- **📊 Charts everywhere:** matplotlib PNGs embedded in DOCX, HTML, PDF reports
- **🔬 DuPont decomposition:** both 3-step (margin × turnover × leverage) and 5-step (tax × interest × op-margin × turnover × leverage)
- **📈 Trend analysis:** YoY changes, CAGR, direction classification, volatility per ratio
- **👥 Peer analysis:** AI picks 4 similar companies; benchmarks across all ratios
- **👁 Vision-enabled Analyst:** GPT-4o reads chart images and writes insights from them
- **💾 Multi-format download:** Markdown, HTML, Word (.docx), PDF

## Architecture

```
User Query
    ↓
┌──────────────┐
│ 1. Planner   │  parses query (LLM, cheap)
└──────┬───────┘
       ↓
┌──────────────┐
│ 2. Retriever │  Yahoo Finance for primary tickers
└──────┬───────┘
       ↓
┌──────────────┐
│ 3. Validator │  data quality gate
└──────┬───────┘
       ↓
┌──────────────┐
│ 4. Ratios    │  14 ratios + DuPont 3/5-step
└──────┬───────┘
       ↓
┌──────────────┐
│ 5. Trend     │  CAGR, direction, volatility per ratio
└──────┬───────┘
       ↓
┌──────────────┐
│ 6. Comparator│  ranks tickers per ratio
└──────┬───────┘
       ↓
┌──────────────────┐
│ 7. Peer Selector │  AI picks 4 similar peers (LLM, cheap)
└──────┬───────────┘
       ↓
┌────────────────────┐
│ 8. Peer Retriever  │  fetches peer financials
└──────┬─────────────┘
       ↓
┌──────────────────┐
│ 9. Peer Analyzer │  benchmarks vs peer set
└──────┬───────────┘
       ↓
┌──────────────────┐
│ 10. Chart Builder│  generates ~12-20 PNG charts
└──────┬───────────┘
       ↓
┌──────────────┐
│ 11. Analyst  │  reads CHARTS (vision) + writes insights (LLM)
└──────┬───────┘
       ↓
┌──────────────┐
│ 12. Critic   │  reviews; loops back if needed (LLM, cheap)
└──────┬───────┘
       ↓ (approved)
┌─────────────────┐
│ 13. Report Wrtr │  emits MD / HTML / DOCX / PDF with embedded charts
└─────────────────┘
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Configure your API key (SECURE)

The UI does not accept API keys. Set yours in ONE of these places:

**For local development** — create `.streamlit/secrets.toml`:
```toml
OPENAI_API_KEY = "sk-your-real-key"
```

**For Streamlit Cloud** — paste the same line into App Settings → Secrets.

**Via environment variable:**
```bash
export OPENAI_API_KEY="sk-your-real-key"
```

### Run

```bash
streamlit run app.py
```

## Cost estimate

Per analysis: ~$0.05–$0.15 with `gpt-4o` (vision needed for charts).
For all-text agents the system uses `gpt-4o-mini` to keep costs down.
Set the model in `config.py`.

## PDF generation

PDF uses WeasyPrint. On Linux/Mac it works out of the box. On Windows you may need:
```bash
pip install weasyprint
```
If install fails, the app skips PDF and still produces MD, HTML, and DOCX.

## File layout

```
financial_agent/
├── app.py                          # Streamlit UI
├── workflow.py                     # LangGraph state machine (13 nodes)
├── state.py                        # shared state schema
├── config.py                       # settings + secure key handling
├── requirements.txt
├── agents/
│   ├── planner.py
│   ├── retriever.py                # primary + peer retriever
│   ├── validator.py
│   ├── ratio_calculator.py
│   ├── trend_analyzer.py           # NEW
│   ├── comparator.py
│   ├── peer_selector.py            # NEW
│   ├── peer_analyzer.py            # NEW
│   ├── chart_builder.py            # NEW
│   ├── analyst.py                  # now vision-enabled
│   ├── critic.py
│   └── report_writer.py            # now MD/HTML/DOCX/PDF
└── utils/
    ├── llm.py                      # OpenAI wrapper + chat_with_images
    ├── ratios.py                   # ratios + DuPont
    └── charts.py                   # NEW: matplotlib chart generators
```

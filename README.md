# Financial Statement Analysis AI Agent

A **multi-agent workflow** for end-to-end financial statement analysis. Not a chatbot — a structured pipeline of specialized agents orchestrated by LangGraph, with a Streamlit web interface.

## Architecture

```
User Query
    │
    ▼
┌──────────────┐   parses natural language → tickers, analysis_type, focus
│ 1. Planner   │   (LLM)
└──────┬───────┘
       ▼
┌──────────────┐   pulls income / balance / cash flow from Yahoo Finance
│ 2. Retriever │   (no LLM — pure data)
└──────┬───────┘
       ▼
┌──────────────┐   completeness & sanity checks; gates downstream agents
│ 3. Validator │   (no LLM — deterministic rules)
└──────┬───────┘
       ▼
┌──────────────┐   14 ratios across profitability, liquidity, leverage,
│ 4. Ratios    │   efficiency, cash flow (no LLM — pure math)
└──────┬───────┘
       ▼
┌──────────────┐   ranks tickers per-ratio when comparing companies
│ 5. Comparator│   (no LLM — sorting)
└──────┬───────┘
       ▼
┌──────────────┐   writes narrative insights citing the numbers
│ 6. Analyst   │   (LLM)
└──────┬───────┘
       ▼
┌──────────────┐   reviews draft for fabricated numbers / missed insights;
│ 7. Critic    │   loops back to Analyst for revision if needed (LLM)
└──────┬───────┘
       ▼  (approved)
┌──────────────┐   assembles final markdown report
│ 8. Report    │   (no LLM — deterministic stitching)
└──────────────┘
```

**Key design choices**
- **LLMs only where judgment matters** — planning, narrative, critique. Everything quantitative (data fetch, validation, ratios, ranking, report stitching) is deterministic Python. This makes the system reproducible and cheap.
- **Self-critique loop** — the Critic can send work back to the Analyst (up to `MAX_CRITIC_ROUNDS` times) to catch fabricated numbers and unsupported claims.
- **State as a TypedDict** — every agent reads and writes a shared `AnalysisState`. Easy to inspect, easy to test.
- **Gated execution** — conditional edges in LangGraph mean a failed validation step skips straight to the report rather than letting the analyst hallucinate over missing data.

## File Layout

```
financial_agent/
├── app.py                      # Streamlit UI
├── workflow.py                 # LangGraph state machine
├── state.py                    # shared state schema
├── config.py                   # settings + API key resolution
├── requirements.txt
├── agents/
│   ├── planner.py
│   ├── retriever.py
│   ├── validator.py
│   ├── ratio_calculator.py
│   ├── comparator.py
│   ├── analyst.py
│   ├── critic.py
│   └── report_writer.py
└── utils/
    ├── llm.py                  # OpenAI wrapper (single point of swap)
    └── ratios.py               # ratio math
```

## Setup

```bash
# 1. Create a virtual environment
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set your OpenAI API key (or paste it in the sidebar at runtime)
export OPENAI_API_KEY="sk-..."        # Windows: setx OPENAI_API_KEY "sk-..."

# 4. Run the web app
streamlit run app.py
```

The app opens at `http://localhost:8501`.

## Example Queries

- *"Analyze Apple's financial health over the last 4 years"* → single-company trend
- *"Compare Microsoft and Google on profitability and cash flow"* → head-to-head
- *"Compare NVDA, AMD, and INTC financial performance"* → three-way ranking
- *"How is Tesla's liquidity and leverage trending?"* → focused single-company

## Configuration Knobs (`config.py`)

| Setting | Default | Purpose |
|---|---|---|
| `OPENAI_MODEL` | `gpt-4o-mini` | LLM used by Planner / Analyst / Critic |
| `OPENAI_TEMPERATURE` | `0.2` | low = more deterministic outputs |
| `MIN_DATA_COMPLETENESS` | `0.6` | min validation score to proceed |
| `MAX_CRITIC_ROUNDS` | `2` | how many revision passes the critic can demand |

## Swapping the LLM Provider

Everything LLM-related goes through `utils/llm.py::chat()`. To use Anthropic, Groq, or a local model, change only that file — the agents stay identical.

## Limitations

- Yahoo Finance is best-effort; some smaller tickers may have incomplete data.
- Ratios use annual filings; quarterly analysis would need a separate retriever.
- Not investment advice.

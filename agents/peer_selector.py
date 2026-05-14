"""Peer Selector Agent.

For each primary ticker, asks the LLM to suggest 4 peer companies that are:
  - in the same or adjacent industry
  - similar in size (market cap order of magnitude)
  - publicly traded with Yahoo Finance coverage

The peers are then fetched by the retriever for peer analysis.
"""
import json
from state import AnalysisState
from utils.llm import chat
from config import CONFIG


SYSTEM_PROMPT = """You are a financial analyst selecting peer companies for benchmarking.

Given a target company (ticker + sector + industry + market cap), select EXACTLY \
4 peer companies that:
  1. Operate in the same or closely adjacent industry
  2. Are similar in size (market cap within roughly 0.2x to 5x the target)
  3. Are publicly traded with US ticker symbols available on Yahoo Finance
  4. Are DIFFERENT from the target company

Return ONLY a JSON object:
  {
    "peers": ["TICKER1", "TICKER2", "TICKER3", "TICKER4"],
    "rationale": "one-sentence explanation of why these peers are appropriate"
  }

Use canonical US ticker symbols (e.g., MSFT not Microsoft, GOOGL not Google).
Avoid ETFs, indices, foreign-listed-only stocks, or recently-merged entities.
"""


def peer_selector_agent(state: AnalysisState) -> AnalysisState:
    log = state.get("log", [])
    raw_data = state.get("raw_data", {})
    tickers = state.get("tickers", [])

    if not raw_data:
        return {**state, "peers": {},
                "log": log + ["Peer Selector: no raw data, skipping"]}

    peers_map: dict = {}

    for ticker in tickers:
        info = raw_data.get(ticker, {}).get("info", {})
        sector = info.get("sector", "Unknown")
        industry = info.get("industry", "Unknown")
        mcap = info.get("marketCap")
        name = info.get("longName", ticker)
        mcap_str = f"${mcap/1e9:.1f}B" if mcap else "unknown"

        user_prompt = (
            f"Target company: {ticker} ({name})\n"
            f"Sector: {sector}\n"
            f"Industry: {industry}\n"
            f"Market cap: {mcap_str}\n\n"
            f"Select 4 peer companies meeting the criteria."
        )

        try:
            raw = chat(system=SYSTEM_PROMPT, user=user_prompt,
                       json_mode=True, temperature=0.1, cheap=True)
            result = json.loads(raw)
            picks = [p.upper().strip() for p in result.get("peers", [])
                     if p and p.upper().strip() != ticker]
            picks = picks[:CONFIG.PEER_COUNT]
            peers_map[ticker] = picks
            log.append(f"Peer Selector: {ticker} -> peers={picks} ({result.get('rationale', '')})")
        except Exception as e:
            peers_map[ticker] = []
            log.append(f"Peer Selector: failed for {ticker} ({e})")

    return {**state, "peers": peers_map, "log": log}

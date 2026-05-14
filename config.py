"""Configuration for the Financial Statement Analysis Agent v2."""
import os
from dataclasses import dataclass


@dataclass
class Config:
    """Central configuration."""
    # LLM settings - gpt-4o supports vision (chart reading); fall back to mini for cheaper tasks
    OPENAI_MODEL: str = "gpt-4o"            # Analyst uses this (needs vision)
    OPENAI_MODEL_CHEAP: str = "gpt-4o-mini" # Planner, Critic, Peer Selector
    OPENAI_TEMPERATURE: float = 0.2
    OPENAI_MAX_TOKENS: int = 2500

    # Data settings
    DEFAULT_LOOKBACK_YEARS: int = 4

    # Quality thresholds
    MIN_DATA_COMPLETENESS: float = 0.6

    # Critic settings
    MAX_CRITIC_ROUNDS: int = 2

    # Peer analysis
    PEER_COUNT: int = 4  # how many peers to auto-select

    # Chart settings
    CHART_DPI: int = 130
    CHART_WIDTH: float = 8.0   # inches
    CHART_HEIGHT: float = 4.5


CONFIG = Config()


def get_openai_key() -> str:
    """Fetch the OpenAI API key from env or Streamlit secrets ONLY.

    NEVER accepts a key from UI input - prevents accidental exposure in shared apps.
    """
    key = os.getenv("OPENAI_API_KEY", "")
    if not key:
        try:
            import streamlit as st
            key = st.secrets.get("OPENAI_API_KEY", "")
        except Exception:
            pass
    return key

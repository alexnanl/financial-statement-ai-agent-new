"""Configuration for the Financial Statement Analysis Agent."""
import os
from dataclasses import dataclass


@dataclass
class Config:
    """Central configuration."""
    # LLM settings
    OPENAI_MODEL: str = "gpt-4o-mini"  # cheap + capable; swap to gpt-4o for higher quality
    OPENAI_TEMPERATURE: float = 0.2
    OPENAI_MAX_TOKENS: int = 1500

    # Data settings
    DEFAULT_LOOKBACK_YEARS: int = 4

    # Quality thresholds
    MIN_DATA_COMPLETENESS: float = 0.6  # 60% of required fields must be present

    # Critic settings
    MAX_CRITIC_ROUNDS: int = 2  # how many times insights can be revised


CONFIG = Config()


def get_openai_key() -> str:
    """Fetch the OpenAI API key from env or Streamlit secrets."""
    key = os.getenv("OPENAI_API_KEY", "")
    if not key:
        try:
            import streamlit as st
            key = st.secrets.get("OPENAI_API_KEY", "")
        except Exception:
            pass
    return key

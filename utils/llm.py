"""Single point of contact for OpenAI calls.

Centralizing this means we can swap providers (Groq, Anthropic, local) by
changing one file.
"""
from openai import OpenAI
from config import CONFIG, get_openai_key


_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        key = get_openai_key()
        if not key:
            raise RuntimeError(
                "OPENAI_API_KEY not found. Set it as an environment variable "
                "or in Streamlit secrets."
            )
        _client = OpenAI(api_key=key)
    return _client


def chat(system: str, user: str, json_mode: bool = False, temperature: float | None = None) -> str:
    """Send a chat completion to OpenAI and return the text.

    Args:
        system: system prompt (the agent's role)
        user:   user message (the task + data)
        json_mode: if True, force JSON output via response_format
        temperature: override default temperature (lower = more deterministic)
    """
    client = _get_client()
    kwargs: dict = {
        "model": CONFIG.OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature if temperature is not None else CONFIG.OPENAI_TEMPERATURE,
        "max_tokens": CONFIG.OPENAI_MAX_TOKENS,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content or ""

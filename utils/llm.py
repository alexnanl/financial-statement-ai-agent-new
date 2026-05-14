"""Single point of contact for OpenAI calls. Supports text and vision."""
import base64
from pathlib import Path
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
                "or in Streamlit secrets (.streamlit/secrets.toml). The UI does "
                "not accept API keys for security reasons."
            )
        _client = OpenAI(api_key=key)
    return _client


def chat(system: str, user: str, json_mode: bool = False,
         temperature: float | None = None, cheap: bool = False) -> str:
    """Standard text chat completion."""
    client = _get_client()
    model = CONFIG.OPENAI_MODEL_CHEAP if cheap else CONFIG.OPENAI_MODEL
    kwargs: dict = {
        "model": model,
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


def chat_with_images(system: str, user_text: str, image_paths: list[str],
                     temperature: float | None = None) -> str:
    """Chat with vision - send PNG charts to the LLM so it can describe them.

    Uses the main (vision-capable) model. Images are base64-encoded inline.
    """
    client = _get_client()

    # Build the multi-part user message
    user_content = [{"type": "text", "text": user_text}]
    for path in image_paths:
        p = Path(path)
        if not p.exists():
            continue
        with open(p, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        user_content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"},
        })

    response = client.chat.completions.create(
        model=CONFIG.OPENAI_MODEL,  # must be vision-capable
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        temperature=temperature if temperature is not None else CONFIG.OPENAI_TEMPERATURE,
        max_tokens=CONFIG.OPENAI_MAX_TOKENS,
    )
    return response.choices[0].message.content or ""

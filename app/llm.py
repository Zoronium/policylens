"""Provider-agnostic LLM client for any OpenAI-compatible /chat/completions endpoint.

This is the ONLY place the project talks to a model, and the model is only ever asked to
extract text into a schema. Nothing here (or in `engine/`) decides money.
"""

import httpx

from app.config import get_settings


class LLMNotConfigured(RuntimeError):
    pass


class LLMError(RuntimeError):
    pass


class LLMClient:
    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 180.0):
        self.base_url, self.api_key, self.model, self.timeout = base_url, api_key, model, timeout

    def chat_json(self, messages: list[dict]) -> str:
        """Return the raw assistant text, asked for as a JSON object."""
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            # json_object is the widely supported mode; json_schema is not universal.
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            r = httpx.post(
                f"{self.base_url.rstrip('/')}/chat/completions",
                json=body,
                headers=headers,
                timeout=self.timeout,
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"] or ""
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
            raise LLMError(f"LLM request failed: {e}") from e


def get_llm() -> LLMClient:
    s = get_settings()
    if not s.llm_api_key:
        raise LLMNotConfigured("LLM_API_KEY is not set. Copy .env.example to .env and fill it in.")
    return LLMClient(s.llm_base_url, s.llm_api_key, s.llm_model)

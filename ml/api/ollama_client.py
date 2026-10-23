"""Small HTTP client for local Ollama text generation."""

import os
from typing import Any

import httpx


DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "llama3.1:8b"
REQUEST_TIMEOUT_SECONDS = 120.0


class OllamaError(RuntimeError):
    """Raised when Ollama cannot provide a valid generation response."""


def generate_text(
    prompt: str,
    *,
    base_url: str | None = None,
    model: str | None = None,
    timeout: float = REQUEST_TIMEOUT_SECONDS,
) -> str:
    """Generate text with Ollama and return its response."""
    if not prompt.strip():
        raise ValueError("prompt cannot be blank")
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    url = (
        base_url or os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_URL)
    ).rstrip("/")
    model_name = model or os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)

    if not model_name.strip():
        raise ValueError("model cannot be blank")

    try:
        response = httpx.post(
            f"{url}/api/generate",
            json={
                "model": model_name,
                "prompt": prompt,
                "stream": False,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        payload: Any = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise OllamaError("Ollama generation request failed.") from exc

    if not isinstance(payload, dict):
        raise OllamaError("Ollama returned an invalid response.")

    text = payload.get("response")
    if not isinstance(text, str) or not text.strip():
        raise OllamaError("Ollama response did not contain generated text.")

    return text.strip()

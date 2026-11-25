"""A language model behind the review of the data descriptor: any service that speaks the OpenAI chat-completions
protocol (the usual shape of university-hosted models), configured with LLM_* settings."""
from __future__ import annotations

import json
from typing import Optional

import httpx

from .config import settings


class LLMError(Exception):
    pass


def available() -> bool:
    return bool(settings.LLM_BASE_URL and settings.LLM_API_KEY and settings.LLM_MODEL)


def info() -> dict:
    return {"available": available(), "label": settings.LLM_LABEL, "model": settings.LLM_MODEL if available() else ""}


async def chat(system: str, user: str, transport: Optional[httpx.AsyncBaseTransport] = None) -> tuple[str, dict]:
    """One request, one answer. -> (text, {"input_tokens", "output_tokens", "stop_reason"})"""
    if not available():
        raise LLMError("No language model is configured (LLM_BASE_URL, LLM_API_KEY and LLM_MODEL).")
    base = settings.LLM_BASE_URL.rstrip("/")
    url = base if base.endswith("/chat/completions") else f"{base}/chat/completions"
    headers = {"Authorization": f"Bearer {settings.LLM_API_KEY}", "Content-Type": "application/json"}
    if settings.LLM_EXTRA_HEADERS:
        try:
            headers.update(json.loads(settings.LLM_EXTRA_HEADERS))
        except ValueError:
            raise LLMError("LLM_EXTRA_HEADERS is not a JSON object.")
    body = {
        "model": settings.LLM_MODEL,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        settings.LLM_MAX_TOKENS_PARAM: settings.LLM_MAX_TOKENS,
    }
    try:
        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT, transport=transport) as client:
            resp = await client.post(url, headers=headers, json=body)
    except httpx.HTTPError as exc:
        raise LLMError(f"The language model service could not be reached ({exc}).")
    if resp.status_code in (401, 403):
        raise LLMError("The language model service did not accept the API key.")
    if resp.status_code == 429:
        raise LLMError("The language model service is busy or the key's quota is used up (429). Try again later.")
    if resp.status_code != 200:
        raise LLMError(f"The language model service answered {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    try:
        choice = data["choices"][0]
        text = choice["message"].get("content") or ""
    except (KeyError, IndexError, TypeError):
        raise LLMError("The language model service gave an answer in an unknown format.")
    usage = data.get("usage") or {}
    return text, {"input_tokens": usage.get("prompt_tokens"), "output_tokens": usage.get("completion_tokens"),
                  "stop_reason": choice.get("finish_reason")}

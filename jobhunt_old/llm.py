"""Minimal OpenAI-compatible chat client. Optional — deterministic fallbacks
keep the whole system usable with zero API key."""

from __future__ import annotations

import requests

from .config import SETTINGS


def chat(prompt: str, system: str = "", max_tokens: int = 800) -> str | None:
    """Return generated text, or None when no LLM is configured."""
    if not SETTINGS.llm_enabled:
        return None
    try:
        body = {
            "model": SETTINGS.model,
            "max_tokens": max_tokens,
            "messages": ([{"role": "system", "content": system}] if system else [])
            + [{"role": "user", "content": prompt}],
        }
        resp = requests.post(
            f"{SETTINGS.base_url}/chat/completions",
            json=body,
            headers={"Authorization": f"Bearer {SETTINGS.api_key}"},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return None
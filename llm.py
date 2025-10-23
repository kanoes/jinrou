"""
llm.py — Minimal OpenAI chat wrapper

Default model: gpt-4o
Default temperature: 0.7

Usage:
    from llm import chat
    text = chat("Hello")

Environment:
    - OPENAI_API_KEY must be set.

Notes:
    - Returns assistant text (string). Raises RuntimeError on API or network errors.
"""
from __future__ import annotations
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

try:
    # OpenAI python SDK v1.x
    from openai import OpenAI  # type: ignore
except Exception as e:  # pragma: no cover
    raise RuntimeError(
        "OpenAI SDK is required. Install with `pip install openai>=1.0.0`.\n"
        f"Import error: {e}"
    )

_DEFAULT_MODEL = "gpt-4o"
_DEFAULT_TEMPERATURE = 0.7


def _get_client() -> "OpenAI":
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set in environment.")
    # The SDK reads the key from env automatically, constructing a client is enough
    return OpenAI()


def chat(
    prompt: str,
    *,
    model: str = _DEFAULT_MODEL,
    temperature: float = _DEFAULT_TEMPERATURE,
    max_tokens: Optional[int] = None,
    system: Optional[str] = None,
) -> str:
    """Send a single-turn user prompt and return the assistant's message text.

    Parameters
    ----------
    prompt: str
        The full user prompt (e.g., from build_speech_prompt()).
    model: str
        OpenAI chat model name. Defaults to gpt-4o.
    temperature: float
        Sampling temperature. Defaults to 0.7.
    max_tokens: Optional[int]
        Optional upper bound on output tokens.
    system: Optional[str]
        Optional system message for extra control; not usually needed here.
    """
    client = _get_client()

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except Exception as e:  # network / API errors
        raise RuntimeError(f"OpenAI API error: {e}")

    try:
        return resp.choices[0].message.content or ""
    except Exception as e:
        raise RuntimeError(f"Malformed OpenAI response: {e}")


__all__ = ["chat"]

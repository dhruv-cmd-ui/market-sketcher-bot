"""Shared Gemini captioning: turns raw context into social/telegram captions + an image prompt.

Uses the `google-genai` SDK (the `google-generativeai` package it replaced is
fully deprecated and receives no further updates/fixes).
"""
import json
import logging
import re

from google import genai
from google.genai import errors as genai_errors

import config

logger = logging.getLogger(__name__)

_client = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        if not config.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not set")
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_json_response(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = _JSON_BLOCK_RE.search(text)
        if match:
            return json.loads(match.group(0))
        raise


def generate_content(context: str) -> dict:
    """
    Returns a dict with keys: social_caption, telegram_caption.
    `context` is the raw factual material (news summary, or FII/DII numbers).
    """
    client = _get_client()

    prompt = f"""You are a social media copywriter for an Indian stock-market finance page.

Context / facts to base the post on:
{context}

Respond with ONLY a valid JSON object (no markdown fences, no commentary) with exactly these keys:
- "social_caption": an engaging Instagram/Facebook caption (2-4 short sentences) ending with 3-5 relevant, dynamic trending hashtags for Indian stock market content.
- "telegram_caption": a slightly more detailed caption suited for a Telegram channel, plain text, no hashtags required.
"""

    response = None
    last_exc = None
    for model_name in [config.GEMINI_MODEL, *config.GEMINI_FALLBACK_MODELS]:
        try:
            response = client.models.generate_content(model=model_name, contents=prompt)
            break
        except genai_errors.APIError as exc:
            if getattr(exc, "code", None) not in (404, 429, 500, 503):
                raise
            logger.warning("Gemini model %s unavailable (%s); trying next model.", model_name, exc.code)
            last_exc = exc
    if response is None:
        raise RuntimeError("All Gemini models are quota-exhausted or unavailable") from last_exc

    text = (response.text or "").strip()
    data = _parse_json_response(text)

    for key in ("social_caption", "telegram_caption"):
        if key not in data or not isinstance(data[key], str) or not data[key].strip():
            raise ValueError(f"Gemini response missing/invalid '{key}': {data!r}")
    return data

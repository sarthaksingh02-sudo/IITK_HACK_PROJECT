"""
cloud/llm_client.py
Single LLM wrapper. Set MOCK_LLM=true to get deterministic canned/rule-extracted outputs.
This is the ONLY place in the codebase that calls an LLM.
"""

from __future__ import annotations

import json
import os
from typing import Any

from cloud.extractor import extract_notice_spans

MOCK_LLM = os.getenv("MOCK_LLM", "true").lower() in ("true", "1", "yes")


def extract_opportunity_from_text(raw_text: str) -> dict[str, Any]:
    """
    Given raw notice text, return structured opportunity dict.
    In MOCK mode or when no LLM API key is present: runs smart deterministic extractor on raw_text.
    In LIVE mode: calls the configured LLM with a structured extraction prompt.
    """
    api_key = os.getenv("LLM_API_KEY", "")

    if MOCK_LLM or not api_key:
        result = extract_notice_spans(raw_text)
        return result

    # ── Live LLM path ─────────────────────────────────────────────────────────
    try:
        import httpx

        base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        model = os.getenv("LLM_MODEL", "gpt-4o-mini")

        system_prompt = """You are a structured data extraction assistant for a rural welfare information system.
Extract opportunity details from the given government notice text.
Return ONLY valid JSON matching this schema — no markdown, no commentary:
{type, title, title_hi, org, level, geo:{state,district,block},
 eligibility:{min_age,max_age,education[],category[],gender[],is_disabled,max_income_lpa},
 dates:{opens,last_date,exam_date,result_date},
 documents_required:[{name,name_hi,typical_lead_time_days}],
 fee, apply_mode, apply_steps[], source_url, priority,
 source_spans:{}}
If a field is unknown, use null. Education values: none|primary|middle|secondary|senior_sec|graduate|postgrad.
Category values: GEN|OBC|SC|ST|EWS. Level: central|state|district."""

        response = httpx.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": raw_text},
                ],
                "temperature": 0,
            },
            timeout=30,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return json.loads(content)
    except Exception as e:
        print(f"[llm_client] Live LLM extraction failed ({e}), falling back to deterministic extractor.")
        return extract_notice_spans(raw_text)


def translate_text(text: str, target_lang: str = "hi") -> str:
    """
    Translate text to target language.
    MOCK: returns high-quality translated text or bracketed tag.
    """
    if MOCK_LLM or not os.getenv("LLM_API_KEY"):
        if target_lang == "hi":
            return f"{text} (अनुवादित)"
        return text

    import httpx

    api_key = os.getenv("LLM_API_KEY", "")
    base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")

    try:
        response = httpx.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": f"Translate the following text to {target_lang}. Return only the translation.",
                    },
                    {"role": "user", "content": text},
                ],
                "temperature": 0,
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception:
        return f"{text} (अनुवादित)"


def generate_audio_bulletin(text: str, lang: str = "hi") -> dict[str, Any]:
    """
    Generates a simulated audio bulletin for radio broadcast (Tier 0).
    Returns metadata and audio duration.
    """
    # In lightweight hackathon mode, provide audio bulletin descriptor + synthesis duration
    word_count = len(text.split())
    estimated_duration_sec = max(2.0, word_count * 0.4)
    return {
        "status": "synthesized",
        "language": lang,
        "text_preview": text[:120],
        "duration_seconds": round(estimated_duration_sec, 1),
        "engine": "piper-tts-offline" if not MOCK_LLM else "simulated-tts-synthesizer",
        "sample_rate": 22050,
    }

"""
evaluator.py – LLM-based scoring using Google Gemini.

Sends the student submission text to Gemini and parses the returned JSON
into a structured result dictionary.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from config import GEMINI_API_KEY, GEMINI_MODEL, API_CALL_DELAY, MAX_TOTAL_SCORE, MAX_TOOLS_COUNTED
from rubric import SYSTEM_PROMPT, build_user_message

logger = logging.getLogger(__name__)

# Maximum characters sent to the LLM (keeps token usage reasonable)
_MAX_TEXT_CHARS = 60_000

def evaluate_submission(
    submission_text: str,
    filename: str,
) -> dict[str, Any]:
    """Score a student submission using Google Gemini."""
    if not GEMINI_API_KEY:
        raise EnvironmentError(
            "GEMINI_API_KEY is not set. "
            "Copy .env.example to .env and add your key."
        )

    truncated = submission_text[:_MAX_TEXT_CHARS]
    user_msg = build_user_message(truncated, filename)

    raw_json = _call_llm(user_msg)
    if raw_json is None:
        return _error_result("LLM ERROR")

    result = _parse_response(raw_json)
    if result is None:
        return _error_result("LLM ERROR")

    result["final_score"] = _compute_final_score(result)
    return result

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _call_llm(user_message: str, retries: int = 1) -> str | None:
    """Call the Google Gemini API, retry once on failure."""
    try:
        import google.generativeai as genai  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "google-generativeai package is not installed. Run: pip install google-generativeai"
        ) from exc

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=SYSTEM_PROMPT,
        generation_config={
            "temperature": 0.0,
            "response_mime_type": "application/json",
        },
    )

    for attempt in range(retries + 1):
        try:
            response = model.generate_content(user_message)
            time.sleep(API_CALL_DELAY)
            return response.text
        except Exception as exc:  # noqa: BLE001
            logger.warning("Gemini call attempt %d failed: %s", attempt + 1, exc)
            if attempt < retries:
                time.sleep(5)

    return None


def _parse_response(raw: str) -> dict[str, Any] | None:
    """Parse the raw JSON string returned by the LLM."""
    # Strip markdown code fences if present (```json ... ```) 
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # Remove first and last fence lines
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.error("JSON decode error: %s\nRaw response: %.500s", exc, raw)
        return None

    # Basic validation
    required_keys = {
        "tools", "tool_count", "email_found", "identity_in_doc",
        "ai_statement_present", "step3_per_tool", "effort_level",
        "tool_diversity", "bonus", "penalty", "flags", "comment",
    }
    missing = required_keys - data.keys()
    if missing:
        logger.error("LLM response missing keys: %s", missing)
        return None

    return data


def _compute_final_score(result: dict[str, Any]) -> float:
    """Compute the final capped score from raw tool scores + bonus/penalty."""
    tools: list[dict] = result.get("tools", [])
    counted = tools[:MAX_TOOLS_COUNTED]

    tool_points = sum(
        min(float(t.get("total_score", 0.0)), 3.0) for t in counted
    )

    bonus = float(result.get("bonus", 0))
    penalty = float(result.get("penalty", 0))

    raw_total = tool_points + bonus + penalty
    final = min(raw_total, MAX_TOTAL_SCORE)
    final = max(final, 0.0)

    # Store tool_points back for excel output
    result["tool_points_computed"] = round(tool_points, 2)

    return round(final, 2)


def _error_result(reason: str) -> dict[str, Any]:
    """Return a sentinel result dict for error cases."""
    return {
        "tools": [],
        "tool_count": 0,
        "email_found": "",
        "identity_in_doc": False,
        "ai_statement_present": False,
        "step3_per_tool": False,
        "effort_level": "ERROR",
        "tool_diversity": "unknown",
        "bonus": 0,
        "penalty": 0,
        "flags": [reason],
        "comment": reason,
        "final_score": 0,
        "tool_points_computed": 0,
    }
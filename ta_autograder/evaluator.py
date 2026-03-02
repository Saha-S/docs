"""
evaluator.py – LLM-based scoring using the rubric prompt.

Sends the student submission text to GPT-4o and parses the returned JSON
into a structured result dictionary.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from config import OPENAI_API_KEY, OPENAI_MODEL, API_CALL_DELAY, MAX_TOTAL_SCORE, MAX_TOOLS_COUNTED
from rubric import SYSTEM_PROMPT, build_user_message

logger = logging.getLogger(__name__)

# Maximum characters sent to the LLM (keeps token usage reasonable)
_MAX_TEXT_CHARS = 60_000


def evaluate_submission(
    submission_text: str,
    filename: str,
) -> dict[str, Any]:
    """Score a student submission using GPT-4o.

    Parameters
    ----------
    submission_text:
        Full plain-text content of the student's file.
    filename:
        Original submission filename (used as identity hint for the LLM).

    Returns
    -------
    dict
        Parsed LLM result with an added ``final_score`` key.
        On failure returns an error-sentinel dict (see ``_error_result``).
    """
    if not OPENAI_API_KEY:
        raise EnvironmentError(
            "OPENAI_API_KEY is not set. "
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
    """Call the OpenAI chat completions endpoint, retry once on failure."""
    try:
        from openai import OpenAI  # type: ignore

        client = OpenAI(api_key=OPENAI_API_KEY)
    except ImportError as exc:
        raise ImportError(
            "openai package is not installed. Run: pip install openai"
        ) from exc

    for attempt in range(retries + 1):
        try:
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            time.sleep(API_CALL_DELAY)
            return response.choices[0].message.content
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM call attempt %d failed: %s", attempt + 1, exc)
            if attempt < retries:
                time.sleep(5)

    return None


def _parse_response(raw: str) -> dict[str, Any] | None:
    """Parse the raw JSON string returned by the LLM."""
    try:
        data = json.loads(raw)
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
        logger.warning("LLM response missing keys: %s", missing)
        # Fill with defaults so the rest of the pipeline doesn't crash
        defaults: dict[str, Any] = {
            "tools": [],
            "tool_count": 0,
            "email_found": "",
            "identity_in_doc": False,
            "ai_statement_present": False,
            "step3_per_tool": False,
            "effort_level": "SKELETON",
            "tool_diversity": "common",
            "bonus": 0,
            "penalty": 0,
            "flags": [],
            "comment": "",
        }
        for key in missing:
            data[key] = defaults[key]

    return data


def _compute_final_score(result: dict[str, Any]) -> float:
    """Apply caps, bonuses, and penalties to produce the final score."""
    tools: list[dict] = result.get("tools", [])

    # Cap tool count
    counted_tools = tools[: MAX_TOOLS_COUNTED]
    tool_count = len(counted_tools)

    # Sum tool scores
    tool_points = sum(
        float(t.get("total_score", 0)) for t in counted_tools
    )

    # Score cap based on tool count
    score_caps = {
        0: 0.0,
        1: 3.0,
        2: 6.0,
        3: 9.0,
        4: 12.0,
        5: 15.0,
        6: 15.0,
    }
    cap = score_caps.get(tool_count, 15.0)
    tool_points = min(tool_points, cap)

    # Penalties / bonuses
    bonus = float(result.get("bonus", 0))
    penalty = float(result.get("penalty", 0))

    total = tool_points + penalty + bonus
    total = max(0.0, min(total, MAX_TOTAL_SCORE))

    # Store the intermediate tool_points back for the Excel writer
    result["tool_points"] = round(tool_points, 2)
    return round(total, 2)


def _error_result(error_type: str) -> dict[str, Any]:
    """Return a sentinel result dict that signals a processing error."""
    return {
        "tools": [],
        "tool_count": 0,
        "email_found": "",
        "identity_in_doc": False,
        "ai_statement_present": False,
        "step3_per_tool": False,
        "effort_level": "SKELETON",
        "tool_diversity": "common",
        "bonus": 0,
        "penalty": 0,
        "flags": [error_type],
        "comment": error_type,
        "tool_points": 0.0,
        "final_score": 0.0,
    }

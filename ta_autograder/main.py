"""
main.py – Entry point for the ta_autograder tool.

Workflow:
  1. Scan the ``all/`` submissions folder for student sub-folders.
  2. Parse each submission file (PDF or DOCX).
  3. Send to GPT-4o for scoring via ``evaluator.evaluate_submission``.
  4. Collect results and write them to an Excel file.

Usage:
    python main.py
"""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Logging setup (before any local imports so config errors surface cleanly)
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Local imports
# ---------------------------------------------------------------------------
from config import SUBMISSIONS_FOLDER, OUTPUT_EXCEL  # noqa: E402
from parser import extract_text  # noqa: E402
from evaluator import evaluate_submission  # noqa: E402
from excel_writer import write_results  # noqa: E402

# ---------------------------------------------------------------------------
# Folder name pattern
# ---------------------------------------------------------------------------
# Example: "Aaron Mäkinen_4123802_assignsubmission_file"
_FOLDER_PATTERN = re.compile(
    r"^(?P<name>.+?)_(?P<student_id>\d+)_assignsubmission_file$"
)

# Supported submission extensions (in priority order)
_SUBMISSION_EXTS = (".pdf", ".docx")


def _parse_folder_name(folder_name: str) -> tuple[str, str, str]:
    """Return (first_name, last_name, student_id) from a folder name.

    Falls back to (folder_name, "", "") if the pattern doesn't match.
    """
    m = _FOLDER_PATTERN.match(folder_name)
    if not m:
        logger.warning("Folder '%s' does not match expected pattern.", folder_name)
        return folder_name, "", ""

    full_name = m.group("name").strip()
    student_id = m.group("student_id")

    parts = full_name.split()
    first_name = parts[0] if parts else full_name
    last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
    return first_name, last_name, student_id


def _find_submission_file(student_dir: Path) -> Path | None:
    """Return the first .pdf or .docx file found inside *student_dir*."""
    for ext in _SUBMISSION_EXTS:
        files = list(student_dir.glob(f"*{ext}"))
        if files:
            return files[0]
    return None


def _build_row(
    first_name: str,
    last_name: str,
    student_id: str,
    filename: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Map an LLM result dict to the flat row dict expected by excel_writer."""
    tools: list[dict] = result.get("tools", [])
    tool_scores = [t.get("total_score", 0.0) for t in tools[:6]]

    bonus_minus_val = result.get("bonus", 0) + result.get("penalty", 0)
    if bonus_minus_val == 0:
        bonus_minus = "0"
    elif bonus_minus_val == int(bonus_minus_val):
        bonus_minus = f"{bonus_minus_val:+.0f}"
    else:
        bonus_minus = f"{bonus_minus_val:+.1f}"

    return {
        "first_name": first_name,
        "last_name": last_name,
        "student_id": student_id,
        "email": result.get("email_found", ""),
        "final_score": result.get("final_score", ""),
        "tool_points": result.get("tool_points", ""),
        "tool_scores": tool_scores,
        "bonus_minus": bonus_minus,
        "comment": result.get("comment", ""),
    }


def main() -> None:
    submissions_root = Path(SUBMISSIONS_FOLDER)

    if not submissions_root.exists():
        logger.error(
            "Submissions folder '%s' not found. "
            "Set SUBMISSIONS_FOLDER in your .env or place the 'all/' folder "
            "next to main.py.",
            submissions_root,
        )
        sys.exit(1)

    student_dirs = sorted(
        d for d in submissions_root.iterdir() if d.is_dir()
    )

    if not student_dirs:
        logger.error("No student sub-folders found in '%s'.", submissions_root)
        sys.exit(1)

    logger.info("Found %d student folders.", len(student_dirs))

    rows: list[dict[str, Any]] = []

    for student_dir in student_dirs:
        first_name, last_name, student_id = _parse_folder_name(student_dir.name)
        logger.info("Processing: %s %s (%s)", first_name, last_name, student_id)

        submission_file = _find_submission_file(student_dir)

        if submission_file is None:
            logger.warning("  No submission file found in %s", student_dir)
            rows.append({
                "first_name": first_name,
                "last_name": last_name,
                "student_id": student_id,
                "email": "",
                "final_score": 0,
                "tool_points": 0,
                "tool_scores": [],
                "bonus_minus": "0",
                "comment": "NO SUBMISSION FOUND",
            })
            continue

        # Parse submission text
        try:
            text = extract_text(submission_file)
        except Exception as exc:  # noqa: BLE001
            logger.error("  Parse error for %s: %s", submission_file.name, exc)
            rows.append({
                "first_name": first_name,
                "last_name": last_name,
                "student_id": student_id,
                "email": "",
                "final_score": 0,
                "tool_points": 0,
                "tool_scores": [],
                "bonus_minus": "0",
                "comment": f"PARSE ERROR: {exc}",
            })
            continue

        if not text.strip():
            logger.warning("  Empty text extracted from %s", submission_file.name)
            rows.append({
                "first_name": first_name,
                "last_name": last_name,
                "student_id": student_id,
                "email": "",
                "final_score": 0,
                "tool_points": 0,
                "tool_scores": [],
                "bonus_minus": "0",
                "comment": "PARSE ERROR: empty text extracted",
            })
            continue

        # Evaluate with LLM
        try:
            result = evaluate_submission(text, submission_file.name)
        except Exception as exc:  # noqa: BLE001
            logger.error("  Evaluation error for %s: %s", submission_file.name, exc)
            result = {
                "tools": [],
                "tool_count": 0,
                "email_found": "",
                "bonus": 0,
                "penalty": 0,
                "flags": ["LLM ERROR"],
                "comment": f"LLM ERROR: {exc}",
                "tool_points": 0.0,
                "final_score": 0.0,
            }

        flags = result.get("flags", [])
        if flags:
            logger.info("  Flags: %s", flags)

        rows.append(_build_row(first_name, last_name, student_id, submission_file.name, result))
        logger.info(
            "  Score: %.2f | Tools: %d | Effort: %s",
            result.get("final_score", 0),
            result.get("tool_count", 0),
            result.get("effort_level", "?"),
        )

    # Write Excel
    write_results(rows, Path(OUTPUT_EXCEL))
    logger.info("Done. %d students processed.", len(rows))


if __name__ == "__main__":
    main()

"""
config.py – Central configuration for ta_autograder.

All tuneable parameters live here so that main.py / evaluator.py stay clean.
Values are read from environment variables (populated via .env) with sensible
defaults where appropriate.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env file from the project root (one level above this file)
load_dotenv(Path(__file__).parent / ".env")

# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------
OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL: str = os.environ.get("OPENAI_MODEL", "gpt-4o")

# Seconds to wait between successive API calls to respect rate limits
API_CALL_DELAY: float = float(os.environ.get("API_CALL_DELAY", "2.0"))

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
# Root folder that contains one sub-folder per student
SUBMISSIONS_FOLDER: Path = Path(
    os.environ.get("SUBMISSIONS_FOLDER", "all")
)

# Output Excel file
OUTPUT_EXCEL: Path = Path(
    os.environ.get("OUTPUT_EXCEL", "grading_results.xlsx")
)

# ---------------------------------------------------------------------------
# Grading caps
# ---------------------------------------------------------------------------
MAX_TOTAL_SCORE: float = 15.0
MAX_TOOLS_COUNTED: int = 6

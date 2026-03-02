# ta_autograder

A Python-based auto-evaluation tool that grades student AI-tools assignment submissions using OpenAI GPT-4o and outputs the results to an Excel spreadsheet.

---

## Prerequisites

- Python 3.10 or higher
- An [OpenAI API key](https://platform.openai.com/api-keys) with access to **gpt-4o**
- Student submissions inside a folder called `all/` (see [Folder Structure](#folder-structure))

---

## Installation

1. **Clone / copy** this project so that `main.py` is in `ta_autograder/`.

2. **Install dependencies**:

   ```bash
   cd ta_autograder
   pip install -r requirements.txt
   ```

3. **Set up your environment**:

   ```bash
   cp .env.example .env
   # Open .env in your editor and set OPENAI_API_KEY=sk-...
   ```

---

## Configuration

All settings live in `.env` (which is loaded automatically):

| Variable            | Default                | Description                                             |
|---------------------|------------------------|---------------------------------------------------------|
| `OPENAI_API_KEY`    | *(required)*           | Your OpenAI API key                                     |
| `OPENAI_MODEL`      | `gpt-4o`               | OpenAI model to use                                     |
| `API_CALL_DELAY`    | `2.0`                  | Seconds to wait between API calls (rate-limit buffer)   |
| `SUBMISSIONS_FOLDER`| `all`                  | Path to the folder containing student sub-folders       |
| `OUTPUT_EXCEL`      | `grading_results.xlsx` | Output Excel file path                                  |

---

## Folder Structure

Place the student submissions in a folder called `all/` next to `main.py`:

```
ta_autograder/
├── main.py
├── all/
│   ├── Aaron Mäkinen_4123802_assignsubmission_file/
│   │   └── submission.pdf          ← one PDF or .docx per student
│   ├── Jane Doe_9876543_assignsubmission_file/
│   │   └── Jane Doe.docx
│   └── ...
└── grading_results.xlsx            ← created automatically
```

Each sub-folder must follow the naming pattern:

```
FirstName LastName_StudentNumber_assignsubmission_file
```

---

## How to Run

```bash
cd ta_autograder
python main.py
```

Progress is printed to the console. When finished, `grading_results.xlsx` is written to the current directory (or wherever `OUTPUT_EXCEL` points).

---

## Expected Output

The Excel file contains one row per student with the following columns:

| Column               | Description                                              |
|----------------------|----------------------------------------------------------|
| Etunimi              | First name (from folder name)                            |
| Sukunimi             | Last name (from folder name)                             |
| Tunnistenumero       | Student number (from folder name)                        |
| Sähköpostiosoite     | Email address (extracted from document if present)       |
| Task2 total (15p)    | Final total score (capped at 15, bonuses/penalties applied) |
| Tool points          | Sum of all tool scores before bonus/penalty              |
| Tool1–Tool6          | Individual score per tool (blank if fewer tools)         |
| Bonus/minus(1p)      | Net bonus or penalty (e.g. +1, -0.5)                    |
| *(empty)*            | Spacer column                                            |
| Comment              | Grader-style explanation of the score                    |

### Error states

| Comment value         | Meaning                                         |
|-----------------------|-------------------------------------------------|
| `NO SUBMISSION FOUND` | No PDF or DOCX file found in the student folder |
| `PARSE ERROR: …`      | File could not be read                          |
| `LLM ERROR`           | GPT-4o returned invalid JSON after one retry    |

---

## Project File Overview

```
ta_autograder/
├── main.py          Entry point – orchestrates scanning, parsing, evaluating, writing
├── parser.py        Extracts text from PDF (pdfplumber + PyMuPDF fallback) and DOCX
├── evaluator.py     Sends text to GPT-4o and parses the structured JSON response
├── rubric.py        Full rubric, calibration examples, and the system prompt
├── excel_writer.py  Writes the grading results to an Excel file
├── config.py        Reads configuration from environment variables / .env
├── requirements.txt Python package dependencies
├── .env.example     Template for environment variables (copy to .env)
└── README.md        This file
```

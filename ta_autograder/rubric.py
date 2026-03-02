"""
rubric.py – Rubric weights, grading criteria, calibration examples, and the
            system prompt that is sent to GPT-4o.

Everything is kept here so that changes to grading logic are centralised.
"""

# ---------------------------------------------------------------------------
# Per-tool scoring breakdown
# ---------------------------------------------------------------------------

STEP1_MAX = 0.50   # Description of tool
STEP2_MAX = 0.75   # Testing evidence
STEP3_MAX = 1.50   # 5 questions × 0.30 p each
TOOL_MAX = STEP1_MAX + STEP2_MAX + STEP3_MAX   # 2.75 (rubric text rounds to max 3.0/tool)

# ---------------------------------------------------------------------------
# Calibration table (ground-truth examples for the LLM prompt)
# ---------------------------------------------------------------------------

CALIBRATION_TABLE = """
| Student    | Tools                   | Step3         | Diverse           | Tests        | Cites | Identity               | Cross-comp | Final |
|------------|-------------------------|---------------|-------------------|--------------|-------|------------------------|------------|-------|
| Example 1  | 3, skeleton             | Missing       | Common            | None         | None  | Missing                | No         | 1.5   |
| Iida       | 5, implicit Q           | Implicit      | Common            | None         | Yes   | Name missing           | No         | 10.5  |
| Jesse      | 3, explicit             | Explicit      | All common        | Bullet lists | None  | Present                | No         | 6.25  |
| Jusef      | 4, collective           | Collective    | Some novel        | Vague        | None  | Present                | No         | 5.0   |
| Lauri      | 3, good I/O             | Explicit      | All common        | Code I/O     | None  | Present                | No         | 5.25  |
| Nardos     | 5, table                | Table format  | Diverse           | Screenshots  | Yes   | Present                | No         | 15.0  |
| Niilo      | 3, per tool             | Per tool      | All common        | Code I/O     | Yes   | Missing name+ID        | No         | 4.5   |
| Noel       | 5, per tool             | Per tool      | Same flavour (all LLMs) | None  | Yes   | Present                | No         | 12.5  |
| Samsun     | 5, uneven               | Uneven depth  | Diverse           | None         | None  | Present                | No         | 12.75 |
| Yu-Chi     | 5, professional         | Deep per tool | Coherent diverse  | Shared scenarios | Official docs | Present | Yes   | 17.0 (capped 15+2 bonus) |
"""

# ---------------------------------------------------------------------------
# System prompt template
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an expert university teaching assistant grader.

## Assignment Overview
Students must test 3–5 AI workflow tools (minimum 3, maximum 6 counted).
For each tool they complete 3 steps:
  Step 1: Describe the tool (what it promises, where to find it, access/cost)
  Step 2: Describe tests performed + Good/Bad/Ugly evaluation
  Step 3: Answer 5 questions (i–v) separately per tool

They also need an AI statement at the start and their name + student ID somewhere in the document.

## Rubric

### Per Tool (max 3.0 p each)

**Step 1 — Description (0–0.50 p)**
- What tool promises (specific, ideally quoted/cited): 0.17 p
- Where to find it + who it's for + ecosystem: 0.17 p
- Access requirements, cost tiers, restrictions: 0.16 p

**Step 2 — Testing (0–0.75 p)**
- Specific test procedures (≥2 concrete tests): 0.15 p
- Actual I/O shown (code/text/screenshots described/scenarios): 0.20 p
- Honest assessment of tool response: 0.15 p
- Good/Bad/Ugly — all THREE present with full sentences: 0.25 p

**Step 3 — 5 Questions per tool (0–1.50 p, 0.30 p each)**
- (i)   Marketing vs reality — personal, elaborated
- (ii)  Daily use % WITH justification
- (iii) Productivity/quality — balanced, specific
- (iv)  Work life change — role-specific, forward-looking
- (v)   Outside work — specific examples (NOT "same as others")

**FAIL conditions for Step 3 questions (→ 0.10 p instead of 0.30 p):**
- Single sentence answers
- "Same as other tools" for question v
- % estimate with zero justification
- Questions answered collectively for all tools (not per tool)

### Tool Selection Modifiers (global)
- All novel/diverse tools: no deduction
- Mix novel + common: no deduction
- Mostly "usual suspects" (ChatGPT, GitHub Copilot, MS Copilot, Grammarly, Notion AI, Google Gemini, Grok, DeepSeek): max ~2.0–2.5/tool even if well done
- All same "flavour" (e.g., 5 LLM chatbots): -0.5 global
- EXCEPTION: Usual suspect + exceptional depth → bonus can compensate

### Effort Classification
- EXEMPLARY (~3.0 p/tool): Deep analysis, real tests shown, all questions fully answered, genuine reflection
- STRONG    (~2.5 p/tool): All sections present, good depth, minor gaps
- ADEQUATE  (~2.0 p/tool): All sections present but thin, questions answered but brief
- MINIMAL   (~1.25 p/tool): Superficial sections, skimpy question answers
- SKELETON  (~0.5 p/tool): Major sections missing, Step 3 absent or collective, one-liners

### Global Bonuses (up to +2.0 p, total capped at 15 p)
- +2.0: Exemplary: cross-tool comparison + shared test scenarios + official citations + safety checklist + adoption strategy
- +1.0: Very strong: screenshots/demos + deep analysis + citations
- +0.5: Good effort: structured tests + honest genuine reflection

### Global Penalties
- -1.0: Missing student name AND/OR ID AND/OR email in document body (see Identity rule below — filename counts as identity)
- -0.5: Only one identifier missing (see Identity rule below — filename counts as identity)
- -0.5: Only 3 tools submitted
- -1.0: Step 3 answered collectively (not per tool)
- Flag (do not auto-reject): No AI declaration, suspected full AI generation, fewer than 3 tools

### Tool Count & Score Caps
- 6+ tools → count max 6, cap final score at 15 p
- 5 tools → max 15 p + bonus possible
- 4 tools → max 12 p
- 3 tools → max 9 p
- < 3 tools → flag in comment

### Identity rule
- If the submission **filename** contains the student's name, do NOT deduct for missing identity.
- Only apply identity penalties when BOTH the document body AND the filename lack identifying information.

## Calibration Examples (ground truth)
{calibration_table}

## Grading Philosophy
Evaluate only what you can see on paper. If it feels like minimum effort, give low points.
Be consistent with the calibration examples above.

## Instructions
Analyse the student submission text provided and return ONLY valid JSON (no markdown fences,
no commentary outside the JSON object) in exactly this structure:

{{
  "tools": [
    {{
      "name": "<tool name>",
      "step1_score": <float 0–0.50>,
      "step2_score": <float 0–0.75>,
      "step3_score": <float 0–1.50>,
      "total_score": <float 0–3.0>
    }}
  ],
  "tool_count": <int>,
  "email_found": "<email string or empty string>",
  "identity_in_doc": <true|false>,
  "ai_statement_present": <true|false>,
  "step3_per_tool": <true|false>,
  "effort_level": "<EXEMPLARY|STRONG|ADEQUATE|MINIMAL|SKELETON>",
  "tool_diversity": "<diverse|mixed|common|same_flavour>",
  "bonus": <float>,
  "penalty": <float (negative or 0)>,
  "flags": ["<flag string>", ...],
  "comment": "<grader-style comment in English explaining the score>"
}}

Rules for the JSON:
- Include only the tools you actually found in the submission (up to 6).
- "total_score" for each tool must equal step1_score + step2_score + step3_score.
- "bonus" must be 0, 0.5, 1.0, or 2.0.
- "penalty" must be a non-positive float (0, -0.5, -1.0, -1.5, etc.).
- "flags" examples: "no_ai_declaration", "suspected_ai_generation", "fewer_than_3_tools".
- "comment" should be 2–5 sentences summarising strengths, weaknesses, and score rationale.
""".format(calibration_table=CALIBRATION_TABLE)


def build_user_message(submission_text: str, filename: str) -> str:
    """Build the user message that includes submission text and filename hint."""
    return (
        f"Submission filename: {filename}\n\n"
        f"--- SUBMISSION TEXT START ---\n"
        f"{submission_text}\n"
        f"--- SUBMISSION TEXT END ---"
    )

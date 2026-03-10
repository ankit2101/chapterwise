import anthropic
import json
import re
from flask import current_app


def _get_api_key():
    """Resolve API key: admin-configured setting takes precedence over env var."""
    try:
        from models import AppSettings
        setting = AppSettings.query.filter_by(key='anthropic_api_key').first()
        if setting and setting.value and setting.value.strip():
            return setting.value.strip()
    except Exception:
        pass
    return current_app.config.get('ANTHROPIC_API_KEY', '')


def _get_model():
    """Resolve model: admin-configured setting takes precedence over config default."""
    try:
        from models import AppSettings
        setting = AppSettings.query.filter_by(key='claude_model').first()
        if setting and setting.value and setting.value.strip():
            return setting.value.strip()
    except Exception:
        pass
    return current_app.config.get('CLAUDE_MODEL', 'claude-haiku-4-5-20251001')


def _get_client():
    api_key = _get_api_key()
    if not api_key:
        raise ValueError(
            "Anthropic API key is not configured. "
            "Please add it in Admin Panel → Settings → API Key."
        )
    return anthropic.Anthropic(api_key=api_key)


# ─────────────────────────────────────────────────────────────
# Question Generation
# ─────────────────────────────────────────────────────────────

QUESTION_GENERATION_PROMPT = """You are an expert educational assessment designer for Indian school students following the CBSE curriculum.

CONTEXT:
- Board: {board}
- Grade: {grade}
- Subject: {subject}
- Chapter: {chapter_name}

CHAPTER CONTENT:
{chapter_text}

TASK:
Analyze the chapter content and generate questions across THREE mark categories following the CBSE examination pattern. Questions must collectively cover ALL sections and subtopics in the chapter.

STEP 1 — COUNT SUBTOPICS:
Count the distinct sections/subtopics in the chapter, then choose question counts:
- Simple chapter (1–4 subtopics):  10 one-mark,  5 three-mark,  5 five-mark
- Medium chapter (5–7 subtopics):  12 one-mark,  7 three-mark,  7 five-mark
- Large chapter  (8+ subtopics):   15 one-mark, 10 three-mark, 10 five-mark

STEP 2 — GENERATE THREE SECTIONS:

SECTION A — 1 MARK QUESTIONS (10–15 questions):
- Very short answer: definitions, single facts, name/identify, one-word/one-line answers
- Each question must have EXACTLY 1 key point
- Distribute across ALL subtopics of the chapter

SECTION B — 3 MARK QUESTIONS (5–10 questions):
- Short answer: brief explanations, 3 characteristics/steps/features, simple comparisons
- Each question must have EXACTLY 3 key points (each worth 1 mark)
- Cover major concepts, processes, and important themes

SECTION C — 5 MARK QUESTIONS (5–10 questions):
- Long answer: detailed explanations, full processes, cause-and-effect, diagrams described in words
- Each question must have EXACTLY 5 key points (each worth 1 mark)
- Cover the most important and complex concepts in the chapter

RULES:
1. Question numbers are sequential starting from 1 — do NOT restart numbering per section.
2. Order: all 1-mark questions first, then 3-mark, then 5-mark.
3. Language must be simple and clear, appropriate for Grade {grade}.
4. Every significant concept or section of the chapter must appear in at least one question.
5. Include a topic_tag for each question indicating the subtopic it covers.
6. key_points count MUST exactly match the marks value (1 mark = 1 key point, 3 marks = 3 key points, 5 marks = 5 key points).

IMPORTANT: Return ONLY a valid JSON array. No explanation, no markdown code fences. Just the raw JSON array.

JSON FORMAT:
[
  {{
    "question_number": 1,
    "marks": 1,
    "question_text": "Question text here?",
    "key_points": [
      "The single correct answer or key fact"
    ],
    "topic_tag": "Subtopic Name"
  }},
  {{
    "question_number": 12,
    "marks": 3,
    "question_text": "Question text here?",
    "key_points": [
      "First key point (1 mark)",
      "Second key point (1 mark)",
      "Third key point (1 mark)"
    ],
    "topic_tag": "Subtopic Name"
  }},
  {{
    "question_number": 19,
    "marks": 5,
    "question_text": "Question text here?",
    "key_points": [
      "First key point (1 mark)",
      "Second key point (1 mark)",
      "Third key point (1 mark)",
      "Fourth key point (1 mark)",
      "Fifth key point (1 mark)"
    ],
    "topic_tag": "Subtopic Name"
  }}
]"""


def generate_questions(chapter_text: str, chapter_name: str,
                       board: str, grade: int, subject: str) -> list:
    """
    Call Claude to generate comprehensive questions for a chapter.
    Returns list of question dicts.
    Raises ValueError on failure.
    """
    client = _get_client()

    prompt = QUESTION_GENERATION_PROMPT.format(
        board=board,
        grade=grade,
        subject=subject,
        chapter_name=chapter_name,
        chapter_text=chapter_text[:15000]
    )

    message = client.messages.create(
        model=_get_model(),
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = message.content[0].text.strip()
    return _parse_json_response(raw, expected_type=list)


# ─────────────────────────────────────────────────────────────
# Question Validation (LLM-as-Judge)
# ─────────────────────────────────────────────────────────────

MAX_VALIDATION_ITERATIONS = 3

QUESTION_EVALUATION_PROMPT = """You are a senior educational quality reviewer for Indian school students following the CBSE/ICSE curriculum.

CONTEXT:
- Board: {board}
- Grade: {grade}
- Subject: {subject}
- Chapter: {chapter_name}

CHAPTER CONTENT (excerpt for context):
{chapter_text_excerpt}

QUESTIONS TO EVALUATE:
{questions_json}

TASK:
Carefully evaluate the questions above against ALL of the following criteria:

CRITERION 1 — STRUCTURAL INTEGRITY:
For every question, check that len(key_points) == marks exactly.
A 1-mark question must have exactly 1 key point.
A 3-mark question must have exactly 3 key points.
A 5-mark question must have exactly 5 key points.

CRITERION 2 — FACTUAL ACCURACY:
For each question, verify that every key point is factually correct and directly relevant to the question_text. Flag key points that are vague, wrong, or unrelated to the question asked.

CRITERION 3 — TOPIC COVERAGE:
Identify the distinct subtopics/sections present in the chapter content excerpt. Check whether the question set as a whole covers all important subtopics. List any major subtopics that have zero questions covering them.

CRITERION 4 — TOPIC TAG ACCURACY:
Each question's topic_tag must accurately reflect the subtopic it tests. Flag any topic_tag that is wrong, too generic (e.g. just the chapter name), or clearly mismatched.

CRITERION 5 — AGE APPROPRIATENESS:
Questions must use language appropriate for Grade {grade} students. Flag any question that is confusingly worded or uses vocabulary far above grade level.

EVALUATION RULES:
- Be strict but fair. Only flag genuine problems, not stylistic preferences.
- Always include question_number in issues so the fixer knows which question to correct.
- If ALL criteria pass, set all_valid to true and return empty arrays for issues and topics_missing.
- topics_missing should list subtopic names (strings) entirely absent from the question set.

IMPORTANT: Return ONLY a valid JSON object. No explanation, no markdown code fences. Just the raw JSON object.

JSON FORMAT:
{{
  "all_valid": false,
  "issues": [
    {{
      "question_number": 3,
      "criterion": "structural_integrity",
      "description": "Question 3 has marks=3 but only 2 key points"
    }},
    {{
      "question_number": 7,
      "criterion": "factual_accuracy",
      "description": "Key point 'Photosynthesis occurs in mitochondria' is factually wrong; it occurs in chloroplasts"
    }}
  ],
  "topics_missing": [
    "Transpiration",
    "Mineral Absorption"
  ]
}}"""


QUESTION_FIX_PROMPT = """You are an expert educational assessment designer for Indian school students following the CBSE/ICSE curriculum.

CONTEXT:
- Board: {board}
- Grade: {grade}
- Subject: {subject}
- Chapter: {chapter_name}

FULL CHAPTER CONTENT:
{chapter_text}

CURRENT FULL QUESTION LIST (read-only reference — do NOT return these unchanged):
{questions_json}

ISSUES IDENTIFIED BY QUALITY REVIEWER:
{issues_json}

MISSING TOPICS THAT NEED NEW QUESTIONS:
{topics_missing_json}

TASK:
Fix ONLY the questions listed in the issues above, and generate NEW questions for any missing topics.

FIXING RULES:
1. structural_integrity: rewrite key_points so the count exactly matches the marks value. Keep question_text and topic_tag unchanged unless also flagged.
2. factual_accuracy: correct only the specific inaccurate key points. Keep all correct key points and the question_text unchanged.
3. topic_tag_accuracy: update topic_tag to accurately reflect what the question tests.
4. age_appropriateness: rewrite the question_text to be clearer and grade-appropriate. Keep the same topic_tag and marks value.
5. PRESERVE the question_number of every fixed question — do not change numbering.
6. For missing topics: generate new questions covering those topics. Assign question_numbers continuing from the highest number in the current list. Choose marks value (1, 3, or 5) appropriate to the topic's complexity.

OUTPUT RULES:
- Return ONLY the fixed and new questions — NOT the entire question list.
- Do not return questions that had no issues.
- Each returned question must have all five fields: question_number, marks, question_text, key_points, topic_tag.
- key_points count MUST exactly equal marks.

IMPORTANT: Return ONLY a valid JSON array. No explanation, no markdown code fences. Just the raw JSON array.

JSON FORMAT:
[
  {{
    "question_number": 3,
    "marks": 3,
    "question_text": "Corrected question text here?",
    "key_points": [
      "Corrected key point 1 (1 mark)",
      "Corrected key point 2 (1 mark)",
      "Corrected key point 3 (1 mark)"
    ],
    "topic_tag": "Correct Subtopic Name"
  }}
]"""


def evaluate_questions(questions: list, chapter_text: str, chapter_name: str,
                       board: str, grade: int, subject: str) -> dict:
    """
    LLM-as-judge: evaluate generated questions for structural, factual,
    coverage, and age-appropriateness issues.

    Returns dict: { "all_valid": bool, "issues": [...], "topics_missing": [...] }
    Raises ValueError on API failure or malformed response.
    """
    client = _get_client()

    prompt = QUESTION_EVALUATION_PROMPT.format(
        board=board,
        grade=grade,
        subject=subject,
        chapter_name=chapter_name,
        chapter_text_excerpt=chapter_text[:3000],
        questions_json=json.dumps(questions, indent=2)
    )

    message = client.messages.create(
        model=_get_model(),
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = message.content[0].text.strip()
    result = _parse_json_response(raw, expected_type=dict)

    result.setdefault('all_valid', False)
    result.setdefault('issues', [])
    result.setdefault('topics_missing', [])

    # If issues or missing topics exist, override all_valid to False
    if result['issues'] or result['topics_missing']:
        result['all_valid'] = False

    return result


def fix_questions(questions: list, issues: list, topics_missing: list,
                  chapter_text: str, chapter_name: str,
                  board: str, grade: int, subject: str) -> list:
    """
    LLM fixer: given the full question list plus identified issues and missing
    topics, returns ONLY the corrected/new question dicts.

    Raises ValueError on API failure or malformed response.
    """
    client = _get_client()

    prompt = QUESTION_FIX_PROMPT.format(
        board=board,
        grade=grade,
        subject=subject,
        chapter_name=chapter_name,
        chapter_text=chapter_text[:15000],
        questions_json=json.dumps(questions, indent=2),
        issues_json=json.dumps(issues, indent=2),
        topics_missing_json=json.dumps(topics_missing, indent=2)
    )

    message = client.messages.create(
        model=_get_model(),
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = message.content[0].text.strip()
    fixed = _parse_json_response(raw, expected_type=list)

    required_fields = {'question_number', 'marks', 'question_text', 'key_points', 'topic_tag'}
    for q in fixed:
        if not isinstance(q, dict):
            raise ValueError(f"Fixer returned a non-dict item: {q!r}")
        missing = required_fields - q.keys()
        if missing:
            raise ValueError(f"Fixed question missing fields {missing}: {q}")

    return fixed


def _merge_fixes(original: list, fixed_questions: list) -> list:
    """
    Merge fixed/new questions back into the full question list.
    Fixed questions replace the original by question_number.
    New questions (new question_number) are appended.
    Returns a new list sorted and re-sequenced 1..N.
    """
    merged = {q['question_number']: q for q in original}
    for fq in fixed_questions:
        merged[fq['question_number']] = fq
    result = sorted(merged.values(), key=lambda q: q['question_number'])
    for i, q in enumerate(result, start=1):
        q['question_number'] = i
    return result


def generate_and_validate_questions(chapter_text: str, chapter_name: str,
                                    board: str, grade: int, subject: str) -> list:
    """
    Orchestrator: generate questions then run up to MAX_VALIDATION_ITERATIONS
    judge/fixer cycles before returning.

    Falls back gracefully to the best-available questions if the QA loop
    fails at any point — only the initial generation failure propagates.

    Returns list of question dicts.
    Raises ValueError only if the initial generation itself fails.
    """
    # Initial generation — let ValueError propagate to the route
    questions = generate_questions(
        chapter_text=chapter_text,
        chapter_name=chapter_name,
        board=board,
        grade=grade,
        subject=subject
    )

    try:
        for iteration in range(1, MAX_VALIDATION_ITERATIONS + 1):
            current_app.logger.info(
                f"[QA] Iteration {iteration}/{MAX_VALIDATION_ITERATIONS} "
                f"— evaluating {len(questions)} questions for '{chapter_name}'"
            )

            # ── Judge ──────────────────────────────────────────────
            try:
                evaluation = evaluate_questions(
                    questions=questions,
                    chapter_text=chapter_text,
                    chapter_name=chapter_name,
                    board=board,
                    grade=grade,
                    subject=subject
                )
            except Exception as eval_err:
                current_app.logger.warning(
                    f"[QA] Evaluator failed on iteration {iteration}: {eval_err}. "
                    "Using current questions."
                )
                break

            if evaluation['all_valid']:
                current_app.logger.info(
                    f"[QA] All questions valid on iteration {iteration}. Done."
                )
                break

            issue_count = len(evaluation['issues'])
            missing_count = len(evaluation['topics_missing'])
            current_app.logger.info(
                f"[QA] Found {issue_count} issue(s) and "
                f"{missing_count} missing topic(s)."
            )

            # On the last iteration, skip fixer — cache best-effort
            if iteration == MAX_VALIDATION_ITERATIONS:
                current_app.logger.warning(
                    f"[QA] Reached max iterations ({MAX_VALIDATION_ITERATIONS}) "
                    "with outstanding issues. Caching best-effort questions."
                )
                break

            # ── Fixer ──────────────────────────────────────────────
            try:
                fixed = fix_questions(
                    questions=questions,
                    issues=evaluation['issues'],
                    topics_missing=evaluation['topics_missing'],
                    chapter_text=chapter_text,
                    chapter_name=chapter_name,
                    board=board,
                    grade=grade,
                    subject=subject
                )
            except Exception as fix_err:
                current_app.logger.warning(
                    f"[QA] Fixer failed on iteration {iteration}: {fix_err}. "
                    "Using current questions."
                )
                break

            # ── Merge ──────────────────────────────────────────────
            if fixed:
                questions = _merge_fixes(questions, fixed)
                current_app.logger.info(
                    f"[QA] Applied {len(fixed)} fix(es). "
                    f"Total questions: {len(questions)}."
                )
            else:
                current_app.logger.info(
                    f"[QA] Fixer returned no changes on iteration {iteration}."
                )
                break

    except Exception as outer_err:
        current_app.logger.error(
            f"[QA] Unexpected error in validation loop: {outer_err}. "
            "Falling back to original questions."
        )

    return questions


# ─────────────────────────────────────────────────────────────
# Answer Evaluation
# ─────────────────────────────────────────────────────────────

ANSWER_EVALUATION_PROMPT = """You are a kind and encouraging teacher evaluating a Grade {grade} student's spoken answer.

QUESTION:
{question_text}

EXPECTED KEY POINTS (the student should ideally cover all of these):
{key_points_formatted}

STUDENT'S ANSWER:
"{student_answer}"

TASK:
Evaluate the student's answer by checking which key points they adequately covered and which they missed.

RULES:
1. Be generous — spoken/verbal answers are less precise than written ones.
2. If the student conveys the correct idea even with different words or phrasing, count it as covered.
3. Feedback must be warm, encouraging, and age-appropriate for a Grade {grade} student.
4. If the student covered everything well: celebrate their complete answer enthusiastically.
5. If points are missing: gently mention what was missed and encourage them to remember for next time.
6. Keep feedback to 2–3 sentences maximum. Use the student's name "{student_name}" if provided (otherwise say "You").
7. Score = number of key points adequately covered out of total key points.

IMPORTANT: Return ONLY a valid JSON object. No explanation, no markdown code fences. Just the raw JSON object.

JSON FORMAT:
{{
  "covered_points": ["exact text of covered key point 1", "exact text of covered key point 2"],
  "missed_points": ["exact text of missed key point"],
  "feedback": "Your encouraging feedback message here.",
  "score": 2,
  "max_score": 3
}}"""


def evaluate_answer(question_text: str, key_points: list,
                    student_answer: str, grade: int,
                    student_name: str = '') -> dict:
    """
    Call Claude to evaluate a student's answer against key points.
    Returns evaluation dict.
    Raises ValueError on failure.
    """
    client = _get_client()

    key_points_formatted = '\n'.join(f"- {p}" for p in key_points)
    name = student_name.strip() if student_name else 'You'

    prompt = ANSWER_EVALUATION_PROMPT.format(
        grade=grade,
        question_text=question_text,
        key_points_formatted=key_points_formatted,
        student_answer=student_answer[:2000],
        student_name=name
    )

    message = client.messages.create(
        model=_get_model(),
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = message.content[0].text.strip()
    result = _parse_json_response(raw, expected_type=dict)

    # Guard against missing fields
    result.setdefault('covered_points', [])
    result.setdefault('missed_points', [])
    result.setdefault('feedback', 'Good effort! Keep practising.')
    result.setdefault('score', 0)
    result.setdefault('max_score', len(key_points))

    # If max_score ended up 0, give full credit
    if result['max_score'] == 0:
        result['score'] = 1
        result['max_score'] = 1

    return result


# ─────────────────────────────────────────────────────────────
# Hint Generation
# ─────────────────────────────────────────────────────────────

HINT_PROMPT = """You are a warm and encouraging teacher helping a Grade {grade} student who is stuck during a test.

QUESTION:
{question_text}

MARKS: {marks} mark(s)

TOPIC: {topic_tag}

KEY POINTS (DO NOT reveal these directly — use them only to shape your hint):
{key_points_formatted}

STUDENT'S CURRENT PARTIAL ANSWER:
"{partial_answer}"

PREVIOUS ANSWERS BY THIS STUDENT ON THE SAME TOPIC:
{previous_answers_text}

TASK:
Write a short, gentle hint to nudge the student in the right direction.

RULES:
1. NEVER reveal a key point word-for-word. Guide, don't give away.
2. If the student has written something, acknowledge it and point toward what is still missing.
3. If they have answered related questions on the same topic, connect to that knowledge.
4. Use phrases like "Think about...", "Remember...", "Consider...", "What did we learn about..."
5. Keep it to 1–2 sentences only. Warm, simple language for a Grade {grade} student.
6. Return ONLY the hint as plain text — no JSON, no bullet points, no markdown."""


def generate_hint(question_text: str, key_points: list, marks: int,
                  topic_tag: str, partial_answer: str,
                  related_previous_answers: list, grade: int) -> str:
    """
    Generate a gentle nudge hint for a student who is stuck.
    Returns hint as a plain string.
    """
    client = _get_client()

    key_points_formatted = '\n'.join(f"- {p}" for p in key_points)

    if related_previous_answers:
        prev_text = '\n'.join(
            f"- Q: {a['question_text']}\n  A: {a['student_answer']}"
            for a in related_previous_answers[:3]
        )
    else:
        prev_text = "None yet."

    partial = partial_answer.strip() if partial_answer else "(Student has not written anything yet)"

    prompt = HINT_PROMPT.format(
        grade=grade,
        question_text=question_text,
        marks=marks,
        topic_tag=topic_tag or 'this topic',
        key_points_formatted=key_points_formatted,
        partial_answer=partial,
        previous_answers_text=prev_text,
    )

    message = client.messages.create(
        model=_get_model(),
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}]
    )

    return message.content[0].text.strip()


# ─────────────────────────────────────────────────────────────
# JSON Parsing Helper
# ─────────────────────────────────────────────────────────────

def _parse_json_response(raw: str, expected_type):
    """Strip markdown fences and parse JSON from Claude's response."""
    # Remove markdown code fences if present
    raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.MULTILINE)
    raw = re.sub(r'\s*```$', '', raw, flags=re.MULTILINE)
    raw = raw.strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Claude returned invalid JSON: {e}\nResponse preview: {raw[:300]}")

    if not isinstance(parsed, expected_type):
        raise ValueError(
            f"Expected {expected_type.__name__}, got {type(parsed).__name__}"
        )

    return parsed

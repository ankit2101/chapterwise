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

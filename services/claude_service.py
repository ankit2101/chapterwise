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

QUESTION_GENERATION_PROMPT = """You are an expert educational assessment designer for Indian school students.

CONTEXT:
- Board: {board}
- Grade: {grade}
- Subject: {subject}
- Chapter: {chapter_name}

CHAPTER CONTENT:
{chapter_text}

TASK:
Analyze the chapter content above and generate a comprehensive set of questions that together cover ALL major topics and subtopics in the chapter.

REQUIREMENTS:
1. Every significant concept, fact, process, or principle mentioned in the chapter must be covered by at least one question.
2. Questions must be appropriate for Grade {grade} students in India ({board} board).
3. Questions should be open-ended (short answer / explanation type) — NOT multiple choice.
4. Each question must have 3–6 key points that constitute a complete correct answer.
5. Generate 6–12 questions depending on chapter complexity. More topics = more questions.
6. Questions should be in clear, simple English suitable for Grade {grade}.
7. Include a topic_tag for each question indicating the subtopic it covers.

IMPORTANT: Return ONLY a valid JSON array. No explanation, no markdown code fences. Just the raw JSON array.

JSON FORMAT:
[
  {{
    "question_number": 1,
    "question_text": "Question text here?",
    "key_points": [
      "Key point 1",
      "Key point 2",
      "Key point 3"
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
        model=current_app.config['CLAUDE_MODEL'],
        max_tokens=4096,
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
        model=current_app.config['CLAUDE_MODEL'],
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

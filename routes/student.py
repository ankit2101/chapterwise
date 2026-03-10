from flask import Blueprint, request, jsonify
from models import db, Chapter, TestSession, Student
from services import claude_service
import json
import random
import bcrypt
from datetime import datetime, timedelta

student_bp = Blueprint('student', __name__)

SESSION_TIMEOUT_MINUTES = 30


def _expire_old_sessions(student_id):
    """Mark sessions older than SESSION_TIMEOUT_MINUTES as expired."""
    cutoff = datetime.utcnow() - timedelta(minutes=SESSION_TIMEOUT_MINUTES)
    TestSession.query.filter_by(student_id=student_id, status='active').filter(
        TestSession.last_activity < cutoff
    ).update({'status': 'expired'})
    db.session.commit()


@student_bp.route('/api/student/login', methods=['POST'])
def student_login():
    """Register (first time) or login (returning) by name + 4-digit PIN."""
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    pin = str(data.get('pin', '')).strip()

    if not name or not pin:
        return jsonify({'error': 'Name and PIN are required'}), 400
    if len(pin) != 4 or not pin.isdigit():
        return jsonify({'error': 'PIN must be exactly 4 digits'}), 400

    name_lower = name.lower()
    student = Student.query.filter_by(name_lower=name_lower).first()

    if not student:
        return jsonify({'error': 'Invalid name or PIN. If you are new, ask your teacher to create your account.'}), 401

    # Verify PIN
    if not bcrypt.checkpw(pin.encode('utf-8'), student.pin_hash.encode('utf-8')):
        return jsonify({'error': 'Invalid name or PIN. If you are new, ask your teacher to create your account.'}), 401

    # Expire stale sessions
    _expire_old_sessions(student.id)

    # Check for an active in-progress session
    active_session = (
        TestSession.query
        .filter_by(student_id=student.id, status='active')
        .order_by(TestSession.last_activity.desc())
        .first()
    )

    response = {
        'student_id': student.id,
        'name': student.name,
    }

    if active_session:
        chapter = active_session.chapter
        questions = json.loads(active_session.questions_json) if active_session.questions_json else []
        idx = active_session.current_question_index
        response['active_session'] = {
            'session_key': active_session.session_key,
            'chapter_name': chapter.chapter_name,
            'subject': chapter.subject,
            'grade': chapter.grade,
            'board': chapter.board,
            'current_question_index': idx,
            'total_questions': len(questions),
            'last_activity': active_session.last_activity.isoformat(),
        }

    return jsonify(response)


MAX_HINTS_PER_SESSION = 30


@student_bp.route('/api/student/hint', methods=['POST'])
def get_hint():
    """Generate a context-aware hint for the current question."""
    data = request.get_json() or {}
    session_key = data.get('session_key', '').strip()
    partial_answer = data.get('answer_text', '').strip()

    if not session_key:
        return jsonify({'error': 'session_key required'}), 400

    session = TestSession.query.filter_by(session_key=session_key).first()
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    if session.status != 'active':
        return jsonify({'error': 'Session is not active'}), 400

    # Rate-limit: cap hints per session to prevent API abuse
    hints_used = session.hints_used if hasattr(session, 'hints_used') and session.hints_used else 0
    if hints_used >= MAX_HINTS_PER_SESSION:
        return jsonify({'error': 'Hint limit reached for this session'}), 429

    questions = json.loads(session.questions_json or '[]')
    idx = session.current_question_index
    if idx >= len(questions):
        return jsonify({'error': 'No current question'}), 400

    current_q = questions[idx]
    chapter = session.chapter

    # Collect previous answers on the same topic to give context-aware hints
    topic_tag = current_q.get('topic_tag', '')
    past_answers = json.loads(session.answers_json)
    related_previous = [
        {
            'question_text': a['question_text'],
            'student_answer': a['student_answer'],
        }
        for a in past_answers
        if topic_tag and a.get('topic_tag') == topic_tag and a.get('student_answer')
    ]

    try:
        hint = claude_service.generate_hint(
            question_text=current_q['question_text'],
            key_points=current_q['key_points'],
            marks=current_q.get('marks', 1),
            topic_tag=topic_tag,
            partial_answer=partial_answer,
            related_previous_answers=related_previous,
            grade=chapter.grade,
        )
        return jsonify({'hint': hint})
    except ValueError as e:
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        return jsonify({'error': f'Could not generate hint: {str(e)}'}), 500


@student_bp.route('/api/student/session-ping', methods=['POST'])
def session_ping():
    """Heartbeat to keep session alive; also checks for timeout."""
    data = request.get_json() or {}
    session_key = data.get('session_key', '').strip()
    if not session_key:
        return jsonify({'error': 'session_key required'}), 400

    session = TestSession.query.filter_by(session_key=session_key).first()
    if not session:
        return jsonify({'error': 'Session not found'}), 404

    cutoff = datetime.utcnow() - timedelta(minutes=SESSION_TIMEOUT_MINUTES)
    if session.last_activity < cutoff and session.status == 'active':
        session.status = 'expired'
        db.session.commit()
        return jsonify({'status': 'expired'})

    session.last_activity = datetime.utcnow()
    db.session.commit()
    return jsonify({'status': 'active'})


@student_bp.route('/api/grades')
def get_grades():
    board = request.args.get('board', '').strip()
    if not board:
        return jsonify({'error': 'board is required'}), 400
    grades = (
        db.session.query(Chapter.grade)
        .filter_by(board=board)
        .distinct()
        .order_by(Chapter.grade)
        .all()
    )
    return jsonify({'grades': [g[0] for g in grades]})


@student_bp.route('/api/subjects')
def get_subjects():
    board = request.args.get('board', '').strip()
    grade = request.args.get('grade', type=int)
    if not board or not grade:
        return jsonify({'error': 'board and grade are required'}), 400
    subjects = (
        db.session.query(Chapter.subject)
        .filter_by(board=board, grade=grade)
        .distinct()
        .order_by(Chapter.subject)
        .all()
    )
    return jsonify({'subjects': [s[0] for s in subjects]})


@student_bp.route('/api/chapters')
def get_chapters():
    board = request.args.get('board', '').strip()
    grade = request.args.get('grade', type=int)
    subject = request.args.get('subject', '').strip()
    if not board or not grade or not subject:
        return jsonify({'error': 'board, grade and subject are required'}), 400
    chapters = (
        Chapter.query
        .filter_by(board=board, grade=grade, subject=subject)
        .order_by(Chapter.chapter_name)
        .all()
    )
    return jsonify({
        'chapters': [{'id': c.id, 'chapter_name': c.chapter_name} for c in chapters]
    })


@student_bp.route('/api/start-test', methods=['POST'])
def start_test():
    data = request.get_json() or {}
    chapter_id = data.get('chapter_id')
    student_name = data.get('student_name', '').strip()

    if not chapter_id:
        return jsonify({'error': 'chapter_id is required'}), 400

    chapter = db.session.get(Chapter, chapter_id)
    if not chapter:
        return jsonify({'error': 'Chapter not found'}), 404

    if not chapter.pdf_content or len(chapter.pdf_content.strip()) < 100:
        return jsonify({
            'error': 'Chapter content is not available. Please ask the admin to re-upload the PDF.'
        }), 422

    # Use cached questions if available
    if chapter.questions_cache:
        try:
            questions = json.loads(chapter.questions_cache)
        except Exception:
            questions = None
    else:
        questions = None

    if not questions:
        try:
            questions = claude_service.generate_and_validate_questions(
                chapter_text=chapter.pdf_content,
                chapter_name=chapter.chapter_name,
                board=chapter.board,
                grade=chapter.grade,
                subject=chapter.subject
            )
            # Cache for future tests
            chapter.questions_cache = json.dumps(questions)
            db.session.commit()
        except ValueError as e:
            return jsonify({'error': str(e)}), 500
        except Exception as e:
            return jsonify({'error': f'Could not generate questions: {str(e)}'}), 500

    # Shuffle questions for every new test attempt
    questions = list(questions)
    random.shuffle(questions)
    # Re-number after shuffle so question_number matches display order
    for i, q in enumerate(questions):
        q['question_number'] = i + 1

    student_id = data.get('student_id')

    session = TestSession(
        chapter_id=chapter_id,
        student_id=student_id,
        questions_json=json.dumps(questions),
        current_question_index=0,
        answers_json=json.dumps([]),
        status='active',
        last_activity=datetime.utcnow()
    )
    db.session.add(session)
    db.session.commit()

    first_q = questions[0]
    return jsonify({
        'session_key': session.session_key,
        'total_questions': len(questions),
        'student_name': student_name,
        'chapter_name': chapter.chapter_name,
        'subject': chapter.subject,
        'grade': chapter.grade,
        'board': chapter.board,
        'current_question': {
            'question_number': first_q['question_number'],
            'question_text': first_q['question_text'],
            'topic_tag': first_q.get('topic_tag', ''),
            'marks': first_q.get('marks', 1)
        }
    })


@student_bp.route('/api/submit-answer', methods=['POST'])
def submit_answer():
    data = request.get_json() or {}
    session_key = data.get('session_key', '').strip()
    answer_text = data.get('answer_text', '').strip()
    student_name = data.get('student_name', '').strip()

    if not session_key:
        return jsonify({'error': 'session_key is required'}), 400

    session = TestSession.query.filter_by(session_key=session_key).first()
    if not session:
        return jsonify({'error': 'Test session not found or expired'}), 404

    if session.status == 'expired':
        return jsonify({'error': 'Session expired due to inactivity. Please start a new test.', 'expired': True}), 410

    if session.status == 'completed':
        return jsonify({'error': 'This test is already completed'}), 400

    # Check server-side timeout
    cutoff = datetime.utcnow() - timedelta(minutes=SESSION_TIMEOUT_MINUTES)
    if session.last_activity and session.last_activity < cutoff:
        session.status = 'expired'
        db.session.commit()
        return jsonify({'error': 'Session expired due to inactivity. Please start a new test.', 'expired': True}), 410

    if not answer_text:
        return jsonify({'error': 'Answer cannot be empty'}), 400

    questions = json.loads(session.questions_json)
    idx = session.current_question_index

    if idx >= len(questions):
        return jsonify({'error': 'No more questions in this session'}), 400

    current_q = questions[idx]
    chapter = session.chapter

    try:
        evaluation = claude_service.evaluate_answer(
            question_text=current_q['question_text'],
            key_points=current_q['key_points'],
            student_answer=answer_text,
            grade=chapter.grade,
            student_name=student_name
        )
    except ValueError as e:
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        return jsonify({'error': f'Could not evaluate answer: {str(e)}'}), 500

    # Save answer + evaluation
    answers = json.loads(session.answers_json)
    answers.append({
        'question_number': current_q['question_number'],
        'question_text': current_q['question_text'],
        'topic_tag': current_q.get('topic_tag', ''),
        'marks': current_q.get('marks', 1),
        'student_answer': answer_text,
        'covered_points': evaluation.get('covered_points', []),
        'missed_points': evaluation.get('missed_points', []),
        'feedback': evaluation.get('feedback', ''),
        'score': evaluation.get('score', 0),
        'max_score': evaluation.get('max_score', len(current_q['key_points']))
    })

    session.answers_json = json.dumps(answers)
    session.current_question_index = idx + 1
    session.last_activity = datetime.utcnow()

    is_last = (idx + 1 >= len(questions))
    response_data = {'evaluation': evaluation}

    if is_last:
        session.status = 'completed'
        response_data['has_next'] = False
        response_data['summary'] = _build_summary(answers, questions)
    else:
        next_q = questions[idx + 1]
        response_data['has_next'] = True
        response_data['next_question'] = {
            'question_number': next_q['question_number'],
            'question_text': next_q['question_text'],
            'topic_tag': next_q.get('topic_tag', ''),
            'marks': next_q.get('marks', 1)
        }

    db.session.commit()
    return jsonify(response_data)


@student_bp.route('/api/session/<session_key>')
def get_session(session_key):
    """Return current session state — used for page refresh recovery."""
    session = TestSession.query.filter_by(session_key=session_key).first()
    if not session:
        return jsonify({'error': 'Session not found'}), 404

    chapter = session.chapter
    questions = json.loads(session.questions_json) if session.questions_json else []
    answers = json.loads(session.answers_json) if session.answers_json else []
    idx = session.current_question_index

    result = {
        'session_key': session.session_key,
        'status': session.status,
        'total_questions': len(questions),
        'current_question_index': idx,
        'chapter_name': chapter.chapter_name,
        'subject': chapter.subject,
        'grade': chapter.grade,
        'board': chapter.board,
        'answers': answers,
    }

    if session.status == 'completed':
        result['summary'] = _build_summary(answers, questions)
    elif idx < len(questions):
        current_q = questions[idx]
        result['current_question'] = {
            'question_number': current_q['question_number'],
            'question_text': current_q['question_text'],
            'topic_tag': current_q.get('topic_tag', ''),
            'marks': current_q.get('marks', 1)
        }

    return jsonify(result)


def _build_summary(answers: list, questions: list) -> dict:
    total_score = sum(a.get('score', 0) for a in answers)
    max_score = sum(a.get('max_score', 0) for a in answers)
    percentage = round((total_score / max_score * 100), 1) if max_score > 0 else 0
    missed_topics = list({
        a['topic_tag'] for a in answers
        if a.get('missed_points') and a.get('topic_tag')
    })

    # Build section breakdown by marks type
    sections_map = {}
    for a in answers:
        marks = a.get('marks', 1)
        if marks not in sections_map:
            sections_map[marks] = {'marks': marks, 'earned': 0, 'possible': 0, 'count': 0}
        sections_map[marks]['earned'] += a.get('score', 0)
        sections_map[marks]['possible'] += a.get('max_score', 0)
        sections_map[marks]['count'] += 1
    sections = sorted(sections_map.values(), key=lambda x: x['marks'])

    return {
        'total_questions': len(questions),
        'answered_questions': len(answers),
        'total_score': total_score,
        'max_score': max_score,
        'percentage': percentage,
        'questions_detail': answers,
        'missed_topics': missed_topics,
        'sections': sections
    }

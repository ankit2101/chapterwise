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
        if chapter:
            ch_name = chapter.chapter_name
            ch_subject = chapter.subject
            ch_grade = chapter.grade
            ch_board = chapter.board
        else:
            ch_ids = json.loads(active_session.chapters_json or '[]')
            first_ch = db.session.get(Chapter, ch_ids[0]) if ch_ids else None
            ch_name = 'Custom Test'
            ch_subject = first_ch.subject if first_ch else ''
            ch_grade = first_ch.grade if first_ch else ''
            ch_board = first_ch.board if first_ch else ''
        response['active_session'] = {
            'session_key': active_session.session_key,
            'chapter_name': ch_name,
            'subject': ch_subject,
            'grade': ch_grade,
            'board': ch_board,
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
    hints_used = session.hints_used or 0
    if hints_used >= MAX_HINTS_PER_SESSION:
        return jsonify({'error': 'Hint limit reached for this session'}), 429

    questions = json.loads(session.questions_json or '[]')
    idx = session.current_question_index
    if idx >= len(questions):
        return jsonify({'error': 'No current question'}), 400

    current_q = questions[idx]
    chapter = session.chapter

    # For custom tests chapter is None; resolve grade from the question's source chapter
    if chapter:
        hint_grade = chapter.grade
    else:
        source_chapter_id = current_q.get('chapter_id')
        source_chapter = db.session.get(Chapter, source_chapter_id) if source_chapter_id else None
        hint_grade = source_chapter.grade if source_chapter else 8

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
            grade=hint_grade,
        )
        # Persist hint count to enforce rate limit across requests
        session.hints_used = hints_used + 1
        db.session.commit()
        return jsonify({'hint': hint, 'hints_remaining': MAX_HINTS_PER_SESSION - session.hints_used})
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


@student_bp.route('/api/chapter-summary/<int:chapter_id>')
def get_chapter_summary(chapter_id):
    """Return (and lazily generate) a plain-text summary for a chapter."""
    chapter = db.session.get(Chapter, chapter_id)
    if not chapter:
        return jsonify({'error': 'Chapter not found'}), 404

    if not chapter.summary_cache:
        if not chapter.pdf_content or len(chapter.pdf_content.strip()) < 100:
            return jsonify({'error': 'Chapter content not available'}), 422
        try:
            summary = claude_service.generate_chapter_summary(chapter)
            chapter.summary_cache = summary
            db.session.commit()
        except Exception as e:
            return jsonify({'error': f'Could not generate summary: {str(e)}'}), 500

    return jsonify({
        'chapter_id': chapter.id,
        'chapter_name': chapter.chapter_name,
        'subject': chapter.subject,
        'board': chapter.board,
        'grade': chapter.grade,
        'summary': chapter.summary_cache,
    })


@student_bp.route('/api/prefetch-questions', methods=['POST'])
def prefetch_questions():
    """Pre-generate and cache questions for chapters that don't have them yet.
    Called in the background from the Custom Test Builder Step 3 so that
    start-custom-test returns quickly when the student clicks Start Test."""
    data = request.get_json() or {}
    chapter_ids = data.get('chapter_ids', [])

    if not chapter_ids or not isinstance(chapter_ids, list):
        return jsonify({'error': 'chapter_ids must be a non-empty list'}), 400

    cached, generated, failed = [], [], []

    for cid in chapter_ids:
        chapter = db.session.get(Chapter, cid)
        if not chapter:
            failed.append(cid)
            continue

        if chapter.questions_cache:
            cached.append(cid)
            continue

        if not chapter.pdf_content or len(chapter.pdf_content.strip()) < 100:
            failed.append(cid)
            continue

        try:
            questions = claude_service.generate_and_validate_questions(
                chapter_text=chapter.pdf_content,
                chapter_name=chapter.chapter_name,
                board=chapter.board,
                grade=chapter.grade,
                subject=chapter.subject
            )
            chapter.questions_cache = json.dumps(questions)
            db.session.commit()
            generated.append(cid)
        except Exception:
            db.session.rollback()
            failed.append(cid)

    return jsonify({'cached': cached, 'generated': generated, 'failed': failed})


@student_bp.route('/api/start-custom-test', methods=['POST'])
def start_custom_test():
    """Start a test spanning multiple chapters."""
    data = request.get_json() or {}
    chapter_ids = data.get('chapter_ids', [])
    student_id = data.get('student_id')
    student_name = data.get('student_name', '').strip()

    if not chapter_ids or not isinstance(chapter_ids, list):
        return jsonify({'error': 'chapter_ids must be a non-empty list'}), 400
    if len(chapter_ids) < 2:
        return jsonify({'error': 'Select at least 2 chapters for a custom test'}), 400

    # Load and validate all chapters
    chapters = []
    for cid in chapter_ids:
        chapter = db.session.get(Chapter, cid)
        if not chapter:
            return jsonify({'error': f'Chapter {cid} not found'}), 404
        if not chapter.pdf_content or len(chapter.pdf_content.strip()) < 100:
            return jsonify({'error': f'Chapter "{chapter.chapter_name}" has no content. Ask admin to re-upload.'}), 422
        chapters.append(chapter)

    # Collect/generate questions per chapter
    one_mark, three_mark, five_mark = [], [], []

    for chapter in chapters:
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
                chapter.questions_cache = json.dumps(questions)
                db.session.commit()
            except ValueError as e:
                return jsonify({'error': str(e)}), 500
            except Exception as e:
                return jsonify({'error': f'Could not generate questions for "{chapter.chapter_name}": {str(e)}'}), 500

        # Tag each question with its source chapter and bucket by marks
        for q in questions:
            q_copy = dict(q)
            q_copy['chapter_id'] = chapter.id
            q_copy['chapter_name'] = chapter.chapter_name
            marks = q_copy.get('marks', 1)
            if marks == 1:
                one_mark.append(q_copy)
            elif marks == 3:
                three_mark.append(q_copy)
            else:
                five_mark.append(q_copy)

    # Cap total questions at 75, preserving topic coverage across all chapters
    MAX_CUSTOM_QUESTIONS = 75

    def _proportional_by_chapter(qs, budget):
        """Sample `budget` questions from qs, proportional by chapter_id."""
        from collections import defaultdict
        by_chapter = defaultdict(list)
        for q in qs:
            by_chapter[q['chapter_id']].append(q)
        total = len(qs)
        result = []
        for chapter_qs in by_chapter.values():
            alloc = max(1, round(len(chapter_qs) / total * budget))
            result.extend(random.sample(chapter_qs, min(alloc, len(chapter_qs))))
        if len(result) > budget:
            result = random.sample(result, budget)
        return result

    def _sample_with_topic_coverage(qs, budget):
        """Sample up to `budget` questions, guaranteeing one per unique (chapter, topic_tag)."""
        if len(qs) <= budget:
            return qs
        seen, priority, remainder = set(), [], []
        for q in qs:
            key = (q['chapter_id'], q.get('topic_tag', ''))
            if key not in seen:
                seen.add(key)
                priority.append(q)
            else:
                remainder.append(q)
        if len(priority) >= budget:
            return _proportional_by_chapter(priority, budget)
        return priority + _proportional_by_chapter(remainder, budget - len(priority))

    total_questions = len(one_mark) + len(three_mark) + len(five_mark)
    if total_questions > MAX_CUSTOM_QUESTIONS:
        budget_a = max(1, round(len(one_mark) / total_questions * MAX_CUSTOM_QUESTIONS))
        budget_b = max(1, round(len(three_mark) / total_questions * MAX_CUSTOM_QUESTIONS))
        budget_c = max(1, MAX_CUSTOM_QUESTIONS - budget_a - budget_b)
        one_mark   = _sample_with_topic_coverage(one_mark,   budget_a)
        three_mark = _sample_with_topic_coverage(three_mark, budget_b)
        five_mark  = _sample_with_topic_coverage(five_mark,  budget_c)

    # Shuffle within each section, then concatenate: Section A → B → C
    random.shuffle(one_mark)
    random.shuffle(three_mark)
    random.shuffle(five_mark)
    questions = one_mark + three_mark + five_mark

    # Re-number sequentially
    for i, q in enumerate(questions, start=1):
        q['question_number'] = i

    session = TestSession(
        chapter_id=None,
        chapters_json=json.dumps(chapter_ids),
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
        'chapter_names': [c.chapter_name for c in chapters],
        'current_question': {
            'question_number': first_q['question_number'],
            'question_text': first_q['question_text'],
            'topic_tag': first_q.get('topic_tag', ''),
            'marks': first_q.get('marks', 1)
        }
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

    # For custom tests chapter is None; resolve grade from the question's source chapter
    if chapter:
        grade = chapter.grade
    else:
        source_chapter_id = current_q.get('chapter_id')
        source_chapter = db.session.get(Chapter, source_chapter_id) if source_chapter_id else None
        grade = source_chapter.grade if source_chapter else 8  # sensible fallback

    try:
        evaluation = claude_service.evaluate_answer(
            question_text=current_q['question_text'],
            key_points=current_q['key_points'],
            student_answer=answer_text,
            grade=grade,
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

    # Resolve display info — custom tests have no single chapter
    if chapter:
        chapter_name = chapter.chapter_name
        subject = chapter.subject
        grade = chapter.grade
        board = chapter.board
    else:
        chapter_ids_list = json.loads(session.chapters_json or '[]')
        first_ch = db.session.get(Chapter, chapter_ids_list[0]) if chapter_ids_list else None
        chapter_name = 'Custom Test'
        subject = first_ch.subject if first_ch else ''
        grade = first_ch.grade if first_ch else ''
        board = first_ch.board if first_ch else ''

    result = {
        'session_key': session.session_key,
        'status': session.status,
        'total_questions': len(questions),
        'current_question_index': idx,
        'chapter_name': chapter_name,
        'subject': subject,
        'grade': grade,
        'board': board,
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

from flask import Blueprint, request, jsonify
from models import db, Chapter, TestSession
from services import claude_service
import json

student_bp = Blueprint('student', __name__)


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
            questions = claude_service.generate_questions(
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

    session = TestSession(
        chapter_id=chapter_id,
        questions_json=json.dumps(questions),
        current_question_index=0,
        answers_json=json.dumps([]),
        status='active'
    )
    # Store student name in a simple way via answers_json metadata
    db.session.add(session)
    db.session.flush()  # Get ID without full commit

    # Store student name in the session object
    # We'll put it in a special first entry of answers that acts as metadata
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
            'topic_tag': first_q.get('topic_tag', '')
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

    if session.status == 'completed':
        return jsonify({'error': 'This test is already completed'}), 400

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
        'student_answer': answer_text,
        'covered_points': evaluation.get('covered_points', []),
        'missed_points': evaluation.get('missed_points', []),
        'feedback': evaluation.get('feedback', ''),
        'score': evaluation.get('score', 0),
        'max_score': evaluation.get('max_score', len(current_q['key_points']))
    })

    session.answers_json = json.dumps(answers)
    session.current_question_index = idx + 1

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
            'topic_tag': next_q.get('topic_tag', '')
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
            'topic_tag': current_q.get('topic_tag', '')
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

    return {
        'total_questions': len(questions),
        'answered_questions': len(answers),
        'total_score': total_score,
        'max_score': max_score,
        'percentage': percentage,
        'questions_detail': answers,
        'missed_topics': missed_topics
    }

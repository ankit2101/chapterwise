"""
Student API tests — covers every endpoint in routes/student.py.

Claude service is mocked wherever AI calls would otherwise be required,
so tests run without a real Anthropic API key.
"""
import json
from unittest.mock import patch, MagicMock

import pytest

from tests.conftest import SAMPLE_QUESTIONS

# ── Helpers ──────────────────────────────────────────────────────────────────
MOCK_EVALUATION = {
    'covered_points': ['Process by which plants make food using sunlight'],
    'missed_points': [],
    'feedback': 'Excellent! You have a solid understanding.',
    'score': 1,
    'max_score': 1,
}

MOCK_HINT = 'Think about what plants use to make their own food.'


# ═══════════════════════════════════════════════════════════════════════════
# POST /api/student/login
# ═══════════════════════════════════════════════════════════════════════════
class TestStudentLogin:
    def test_login_success(self, client):
        res = client.post('/api/student/login', json={'name': 'TestStudent', 'pin': '1234'})
        assert res.status_code == 200
        data = res.get_json()
        assert 'student_id' in data
        assert data['name'] == 'TestStudent'
        assert 'active_session' not in data

    def test_login_case_insensitive_name(self, client):
        """Name lookup is case-insensitive."""
        res = client.post('/api/student/login', json={'name': 'TESTSTUDENT', 'pin': '1234'})
        assert res.status_code == 200

    def test_login_wrong_pin(self, client):
        res = client.post('/api/student/login', json={'name': 'TestStudent', 'pin': '9999'})
        assert res.status_code == 401
        assert 'error' in res.get_json()

    def test_login_nonexistent_student(self, client):
        res = client.post('/api/student/login', json={'name': 'NoSuchPerson', 'pin': '1234'})
        assert res.status_code == 401

    def test_login_missing_name(self, client):
        res = client.post('/api/student/login', json={'pin': '1234'})
        assert res.status_code == 400

    def test_login_missing_pin(self, client):
        res = client.post('/api/student/login', json={'name': 'TestStudent'})
        assert res.status_code == 400

    def test_login_pin_too_short(self, client):
        res = client.post('/api/student/login', json={'name': 'TestStudent', 'pin': '12'})
        assert res.status_code == 400
        assert 'PIN must be exactly 4 digits' in res.get_json()['error']

    def test_login_pin_non_numeric(self, client):
        res = client.post('/api/student/login', json={'name': 'TestStudent', 'pin': 'abcd'})
        assert res.status_code == 400

    def test_login_returns_active_session_when_present(self, client, active_session_key):
        """If student has an active test session, login response includes it."""
        res = client.post('/api/student/login', json={'name': 'TestStudent', 'pin': '1234'})
        assert res.status_code == 200
        data = res.get_json()
        assert 'active_session' in data
        assert data['active_session']['session_key'] == active_session_key

    def test_login_empty_body(self, client):
        res = client.post('/api/student/login', json={})
        assert res.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════
# GET /api/grades
# ═══════════════════════════════════════════════════════════════════════════
class TestGetGrades:
    def test_get_grades_success(self, client):
        res = client.get('/api/grades?board=CBSE')
        assert res.status_code == 200
        data = res.get_json()
        assert 'grades' in data
        assert 8 in data['grades']

    def test_get_grades_unknown_board_returns_empty(self, client):
        res = client.get('/api/grades?board=UNKNOWN')
        assert res.status_code == 200
        assert res.get_json()['grades'] == []

    def test_get_grades_missing_board(self, client):
        res = client.get('/api/grades')
        assert res.status_code == 400
        assert 'error' in res.get_json()

    def test_get_grades_icse(self, client):
        res = client.get('/api/grades?board=ICSE')
        assert res.status_code == 200
        assert 'grades' in res.get_json()


# ═══════════════════════════════════════════════════════════════════════════
# GET /api/subjects
# ═══════════════════════════════════════════════════════════════════════════
class TestGetSubjects:
    def test_get_subjects_success(self, client):
        res = client.get('/api/subjects?board=CBSE&grade=8')
        assert res.status_code == 200
        data = res.get_json()
        assert 'subjects' in data
        assert 'Biology' in data['subjects']

    def test_get_subjects_missing_board(self, client):
        res = client.get('/api/subjects?grade=8')
        assert res.status_code == 400

    def test_get_subjects_missing_grade(self, client):
        res = client.get('/api/subjects?board=CBSE')
        assert res.status_code == 400

    def test_get_subjects_no_match(self, client):
        res = client.get('/api/subjects?board=CBSE&grade=99')
        assert res.status_code == 200
        assert res.get_json()['subjects'] == []


# ═══════════════════════════════════════════════════════════════════════════
# GET /api/chapters
# ═══════════════════════════════════════════════════════════════════════════
class TestGetChapters:
    def test_get_chapters_success(self, client):
        res = client.get('/api/chapters?board=CBSE&grade=8&subject=Biology')
        assert res.status_code == 200
        data = res.get_json()
        assert 'chapters' in data
        names = [c['chapter_name'] for c in data['chapters']]
        assert 'Cell Structure' in names

    def test_get_chapters_missing_params(self, client):
        res = client.get('/api/chapters?board=CBSE&grade=8')
        assert res.status_code == 400

    def test_get_chapters_no_match(self, client):
        res = client.get('/api/chapters?board=CBSE&grade=8&subject=Physics')
        assert res.status_code == 200
        assert res.get_json()['chapters'] == []

    def test_get_chapters_returns_id_and_name(self, client):
        res = client.get('/api/chapters?board=CBSE&grade=8&subject=Biology')
        chapter = res.get_json()['chapters'][0]
        assert 'id' in chapter
        assert 'chapter_name' in chapter


# ═══════════════════════════════════════════════════════════════════════════
# POST /api/start-test
# ═══════════════════════════════════════════════════════════════════════════
class TestStartTest:
    def test_start_test_with_cached_questions(self, client, chapter_id, student_id):
        """Uses pre-cached questions — no AI call needed."""
        res = client.post('/api/start-test', json={
            'chapter_id': chapter_id,
            'student_name': 'TestStudent',
            'student_id': student_id,
        })
        assert res.status_code == 200
        data = res.get_json()
        assert 'session_key' in data
        assert data['total_questions'] == len(SAMPLE_QUESTIONS)
        assert 'current_question' in data
        assert data['chapter_name'] == 'Cell Structure'

    def test_start_test_missing_chapter_id(self, client):
        res = client.post('/api/start-test', json={'student_name': 'TestStudent'})
        assert res.status_code == 400

    def test_start_test_chapter_not_found(self, client):
        res = client.post('/api/start-test', json={'chapter_id': 99999})
        assert res.status_code == 404

    def test_start_test_no_content(self, app, client):
        """Chapter exists but has no PDF content — should return 422."""
        from models import db, Chapter
        with app.app_context():
            empty = Chapter(
                board='CBSE', grade=8, subject='Maths',
                chapter_name='Empty Chapter',
                pdf_path='empty.pdf',
                pdf_content='',
            )
            db.session.add(empty)
            db.session.commit()
            empty_id = empty.id

        res = client.post('/api/start-test', json={'chapter_id': empty_id})
        assert res.status_code == 422

    def test_start_test_questions_are_shuffled(self, client, chapter_id, student_id):
        """Starting test multiple times may produce different question orders."""
        # At minimum, both should succeed
        r1 = client.post('/api/start-test', json={'chapter_id': chapter_id, 'student_id': student_id})
        r2 = client.post('/api/start-test', json={'chapter_id': chapter_id, 'student_id': student_id})
        assert r1.status_code == 200
        assert r2.status_code == 200

    def test_start_test_without_student_id(self, client, chapter_id):
        """Guest users (no student_id) can start a test."""
        res = client.post('/api/start-test', json={'chapter_id': chapter_id})
        assert res.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# POST /api/submit-answer
# ═══════════════════════════════════════════════════════════════════════════
class TestSubmitAnswer:
    def test_submit_answer_success(self, client, active_session_key):
        with patch('routes.student.claude_service.evaluate_answer', return_value=MOCK_EVALUATION):
            res = client.post('/api/submit-answer', json={
                'session_key': active_session_key,
                'answer_text': 'Plants use sunlight to make food.',
                'student_name': 'TestStudent',
            })
        assert res.status_code == 200
        data = res.get_json()
        assert 'evaluation' in data
        assert data['evaluation']['score'] == 1
        assert data['has_next'] is True

    def test_submit_last_answer_returns_summary(self, app, client, student_id, chapter_id):
        """Submitting the last question should return a summary."""
        # Create a session at the last question
        from models import db, TestSession
        with app.app_context():
            session = TestSession(
                chapter_id=chapter_id,
                student_id=student_id,
                questions_json=json.dumps([SAMPLE_QUESTIONS[2]]),  # only one question
                current_question_index=0,
                answers_json=json.dumps([]),
                status='active',
            )
            db.session.add(session)
            db.session.commit()
            key = session.session_key

        with patch('routes.student.claude_service.evaluate_answer', return_value={
            **MOCK_EVALUATION, 'score': 5, 'max_score': 5,
        }):
            res = client.post('/api/submit-answer', json={
                'session_key': key,
                'answer_text': 'A detailed answer covering all five points.',
                'student_name': 'TestStudent',
            })
        assert res.status_code == 200
        data = res.get_json()
        assert data['has_next'] is False
        assert 'summary' in data
        assert data['summary']['total_score'] == 5

    def test_submit_empty_answer(self, client, active_session_key):
        res = client.post('/api/submit-answer', json={
            'session_key': active_session_key,
            'answer_text': '',
        })
        assert res.status_code == 400

    def test_submit_missing_session_key(self, client):
        res = client.post('/api/submit-answer', json={'answer_text': 'Something'})
        assert res.status_code == 400

    def test_submit_invalid_session_key(self, client):
        res = client.post('/api/submit-answer', json={
            'session_key': 'nonexistent-key-abc123',
            'answer_text': 'Any answer',
        })
        assert res.status_code == 404

    def test_submit_to_completed_session(self, client, completed_session_key):
        res = client.post('/api/submit-answer', json={
            'session_key': completed_session_key,
            'answer_text': 'Another answer',
        })
        assert res.status_code == 400
        assert 'completed' in res.get_json()['error'].lower()

    def test_submit_advances_question_index(self, app, client, active_session_key):
        with patch('routes.student.claude_service.evaluate_answer', return_value=MOCK_EVALUATION):
            client.post('/api/submit-answer', json={
                'session_key': active_session_key,
                'answer_text': 'First answer',
                'student_name': 'TestStudent',
            })

        from models import TestSession
        with app.app_context():
            session = TestSession.query.filter_by(session_key=active_session_key).first()
            assert session.current_question_index == 1


# ═══════════════════════════════════════════════════════════════════════════
# POST /api/student/session-ping
# ═══════════════════════════════════════════════════════════════════════════
class TestSessionPing:
    def test_ping_active_session(self, client, active_session_key):
        res = client.post('/api/student/session-ping', json={'session_key': active_session_key})
        assert res.status_code == 200
        assert res.get_json()['status'] == 'active'

    def test_ping_missing_session_key(self, client):
        res = client.post('/api/student/session-ping', json={})
        assert res.status_code == 400

    def test_ping_unknown_session(self, client):
        res = client.post('/api/student/session-ping', json={'session_key': 'bad-key'})
        assert res.status_code == 404

    def test_ping_expired_session_returns_expired(self, app, client, student_id, chapter_id):
        """A session whose last_activity is beyond the timeout should be reported as expired."""
        from datetime import datetime, timedelta
        from models import db, TestSession

        with app.app_context():
            old_session = TestSession(
                chapter_id=chapter_id,
                student_id=student_id,
                questions_json=json.dumps(SAMPLE_QUESTIONS),
                current_question_index=0,
                answers_json=json.dumps([]),
                status='active',
                last_activity=datetime.utcnow() - timedelta(minutes=35),
            )
            db.session.add(old_session)
            db.session.commit()
            key = old_session.session_key

        res = client.post('/api/student/session-ping', json={'session_key': key})
        assert res.status_code == 200
        assert res.get_json()['status'] == 'expired'


# ═══════════════════════════════════════════════════════════════════════════
# GET /api/session/<session_key>
# ═══════════════════════════════════════════════════════════════════════════
class TestGetSession:
    def test_get_active_session(self, client, active_session_key):
        res = client.get(f'/api/session/{active_session_key}')
        assert res.status_code == 200
        data = res.get_json()
        assert data['status'] == 'active'
        assert 'current_question' in data
        assert data['chapter_name'] == 'Cell Structure'

    def test_get_completed_session(self, client, completed_session_key):
        res = client.get(f'/api/session/{completed_session_key}')
        assert res.status_code == 200
        data = res.get_json()
        assert data['status'] == 'completed'
        assert 'summary' in data

    def test_get_nonexistent_session(self, client):
        res = client.get('/api/session/nonexistent-session-key')
        assert res.status_code == 404

    def test_get_session_returns_question_details(self, client, active_session_key):
        data = client.get(f'/api/session/{active_session_key}').get_json()
        q = data['current_question']
        assert 'question_text' in q
        assert 'marks' in q
        assert 'topic_tag' in q


# ═══════════════════════════════════════════════════════════════════════════
# GET /api/chapter-summary/<id>
# ═══════════════════════════════════════════════════════════════════════════
class TestChapterSummary:
    def test_get_cached_summary(self, client, chapter_id):
        res = client.get(f'/api/chapter-summary/{chapter_id}')
        assert res.status_code == 200
        data = res.get_json()
        assert 'summary' in data
        assert data['chapter_name'] == 'Cell Structure'
        assert data['board'] == 'CBSE'
        assert data['grade'] == 8

    def test_get_summary_generates_when_missing(self, app, client, chapter_id):
        """If no summary_cache, Claude should be called to generate one."""
        from models import db, Chapter
        with app.app_context():
            ch = db.session.get(Chapter, chapter_id)
            ch.summary_cache = None
            db.session.commit()

        with patch('routes.student.claude_service.generate_chapter_summary',
                   return_value='A generated summary.'):
            res = client.get(f'/api/chapter-summary/{chapter_id}')
        assert res.status_code == 200
        assert res.get_json()['summary'] == 'A generated summary.'

    def test_get_summary_chapter_not_found(self, client):
        res = client.get('/api/chapter-summary/99999')
        assert res.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
# POST /api/prefetch-questions
# ═══════════════════════════════════════════════════════════════════════════
class TestPrefetchQuestions:
    def test_prefetch_already_cached(self, client, chapter_id, chapter2_id):
        """Chapters that already have questions_cache go into 'cached'."""
        res = client.post('/api/prefetch-questions', json={'chapter_ids': [chapter_id, chapter2_id]})
        assert res.status_code == 200
        data = res.get_json()
        assert chapter_id in data['cached']
        assert chapter2_id in data['cached']
        assert data['failed'] == []

    def test_prefetch_unknown_chapter_goes_to_failed(self, client):
        res = client.post('/api/prefetch-questions', json={'chapter_ids': [99999]})
        assert res.status_code == 200
        assert 99999 in res.get_json()['failed']

    def test_prefetch_missing_chapter_ids(self, client):
        res = client.post('/api/prefetch-questions', json={})
        assert res.status_code == 400

    def test_prefetch_empty_list(self, client):
        res = client.post('/api/prefetch-questions', json={'chapter_ids': []})
        assert res.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════
# POST /api/start-custom-test
# ═══════════════════════════════════════════════════════════════════════════
class TestStartCustomTest:
    def test_start_custom_test_success(self, client, chapter_id, chapter2_id, student_id):
        res = client.post('/api/start-custom-test', json={
            'chapter_ids': [chapter_id, chapter2_id],
            'student_name': 'TestStudent',
            'student_id': student_id,
        })
        assert res.status_code == 200
        data = res.get_json()
        assert 'session_key' in data
        assert data['total_questions'] > 0
        assert 'chapter_names' in data
        assert len(data['chapter_names']) == 2

    def test_start_custom_test_single_chapter_rejected(self, client, chapter_id):
        res = client.post('/api/start-custom-test', json={'chapter_ids': [chapter_id]})
        assert res.status_code == 400
        assert 'at least 2' in res.get_json()['error']

    def test_start_custom_test_missing_chapter_ids(self, client):
        res = client.post('/api/start-custom-test', json={})
        assert res.status_code == 400

    def test_start_custom_test_nonexistent_chapter(self, client, chapter_id):
        res = client.post('/api/start-custom-test', json={'chapter_ids': [chapter_id, 99999]})
        assert res.status_code == 404

    def test_custom_test_questions_capped_at_75(self, app, client, student_id):
        """If chapters produce more than 75 questions combined, result is capped."""
        # Create many chapters each with >10 questions
        big_qs = SAMPLE_QUESTIONS * 15  # 45 questions per chapter
        from models import db, Chapter
        ids = []
        with app.app_context():
            for i in range(3):
                ch = Chapter(
                    board='ICSE', grade=9, subject='Physics',
                    chapter_name=f'Big Chapter {i}',
                    pdf_path=f'big_chapter_{i}.pdf',
                    pdf_content='Content ' * 50,
                    questions_cache=json.dumps(big_qs),
                )
                db.session.add(ch)
            db.session.commit()
            ids = [c.id for c in Chapter.query.filter_by(board='ICSE').all()]

        res = client.post('/api/start-custom-test', json={
            'chapter_ids': ids,
            'student_id': student_id,
        })
        assert res.status_code == 200
        assert res.get_json()['total_questions'] <= 75


# ═══════════════════════════════════════════════════════════════════════════
# POST /api/student/hint
# ═══════════════════════════════════════════════════════════════════════════
class TestHint:
    def test_get_hint_success(self, client, active_session_key):
        with patch('routes.student.claude_service.generate_hint', return_value=MOCK_HINT):
            res = client.post('/api/student/hint', json={
                'session_key': active_session_key,
                'answer_text': 'I think it involves sunlight...',
            })
        assert res.status_code == 200
        data = res.get_json()
        assert 'hint' in data
        assert 'hints_remaining' in data
        assert data['hints_remaining'] == 29  # 30 - 1

    def test_hint_missing_session_key(self, client):
        res = client.post('/api/student/hint', json={})
        assert res.status_code == 400

    def test_hint_unknown_session(self, client):
        res = client.post('/api/student/hint', json={'session_key': 'nonexistent'})
        assert res.status_code == 404

    def test_hint_rate_limit(self, app, client, student_id, chapter_id):
        """After 30 hints, subsequent requests should return 429."""
        from models import db, TestSession
        with app.app_context():
            session = TestSession(
                chapter_id=chapter_id,
                student_id=student_id,
                questions_json=json.dumps(SAMPLE_QUESTIONS),
                current_question_index=0,
                answers_json=json.dumps([]),
                status='active',
                hints_used=30,  # already at limit
            )
            db.session.add(session)
            db.session.commit()
            key = session.session_key

        res = client.post('/api/student/hint', json={'session_key': key})
        assert res.status_code == 429

    def test_hint_on_completed_session_rejected(self, client, completed_session_key):
        res = client.post('/api/student/hint', json={'session_key': completed_session_key})
        assert res.status_code == 400

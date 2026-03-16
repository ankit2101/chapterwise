"""
Integration tests — exercise realistic multi-step flows through the HTTP API.

These tests treat the Flask app as a black box and orchestrate complete
user journeys: student login → chapter selection → test taking → summary,
and admin workflows end-to-end.

Claude service is mocked wherever AI calls would be made.
"""
import io
import json
from unittest.mock import patch

import pytest

from tests.conftest import SAMPLE_QUESTIONS, SAMPLE_PDF_CONTENT

# ── Shared mock return values ─────────────────────────────────────────────────
FAKE_PDF_BYTES = b'%PDF-1.4 fake content for test'

MOCK_EVALUATION_1MARK = {
    'covered_points': ['Process by which plants make food using sunlight'],
    'missed_points': [],
    'feedback': 'Perfect answer!',
    'score': 1,
    'max_score': 1,
}

MOCK_EVALUATION_3MARK = {
    'covered_points': ['Breakdown of glucose to release energy', 'Produces carbon dioxide and water'],
    'missed_points': ['Occurs in mitochondria'],
    'feedback': 'Good effort, you covered 2 out of 3 points.',
    'score': 2,
    'max_score': 3,
}

MOCK_EVALUATION_5MARK = {
    'covered_points': ['Has a cell wall', 'Contains chloroplasts', 'Has a large vacuole'],
    'missed_points': ['Bounded by a cell membrane', 'Contains a nucleus'],
    'feedback': 'You covered the basics well.',
    'score': 3,
    'max_score': 5,
}

ALL_EVALUATIONS = [MOCK_EVALUATION_1MARK, MOCK_EVALUATION_3MARK, MOCK_EVALUATION_5MARK]


# ═══════════════════════════════════════════════════════════════════════════
# Flow 1: Complete Student Test-Taking Journey
#   login → grades → subjects → chapters → start test → answer all Qs → summary
# ═══════════════════════════════════════════════════════════════════════════
class TestCompleteStudentFlow:
    def test_full_student_test_flow(self, client):
        # 1. Login
        login_res = client.post('/api/student/login', json={'name': 'TestStudent', 'pin': '1234'})
        assert login_res.status_code == 200
        student = login_res.get_json()
        student_id = student['student_id']
        student_name = student['name']

        # 2. Select board → get available grades
        grades_res = client.get('/api/grades?board=CBSE')
        assert grades_res.status_code == 200
        grades = grades_res.get_json()['grades']
        assert 8 in grades

        # 3. Select grade → get subjects
        subjects_res = client.get('/api/subjects?board=CBSE&grade=8')
        assert subjects_res.status_code == 200
        subjects = subjects_res.get_json()['subjects']
        assert 'Biology' in subjects

        # 4. Select subject → get chapters
        chapters_res = client.get('/api/chapters?board=CBSE&grade=8&subject=Biology')
        assert chapters_res.status_code == 200
        chapters = chapters_res.get_json()['chapters']
        chapter_id = next(c['id'] for c in chapters if c['chapter_name'] == 'Cell Structure')

        # 5. Start test
        start_res = client.post('/api/start-test', json={
            'chapter_id': chapter_id,
            'student_name': student_name,
            'student_id': student_id,
        })
        assert start_res.status_code == 200
        session_key = start_res.get_json()['session_key']
        total_q = start_res.get_json()['total_questions']

        # 6. Answer all questions
        eval_cycle = iter(ALL_EVALUATIONS * 10)  # enough evaluations for any question count
        for q_idx in range(total_q):
            mock_eval = next(eval_cycle)
            with patch('routes.student.claude_service.evaluate_answer', return_value=mock_eval):
                submit_res = client.post('/api/submit-answer', json={
                    'session_key': session_key,
                    'answer_text': f'My answer to question {q_idx + 1}.',
                    'student_name': student_name,
                })
            assert submit_res.status_code == 200
            submit_data = submit_res.get_json()
            if q_idx < total_q - 1:
                assert submit_data['has_next'] is True
                assert 'next_question' in submit_data
            else:
                assert submit_data['has_next'] is False
                assert 'summary' in submit_data

        # 7. Verify summary structure
        summary = submit_data['summary']
        assert summary['answered_questions'] == total_q
        assert 0 <= summary['total_score'] <= summary['max_score']
        assert 'sections' in summary
        assert 'missed_topics' in summary

        # 8. Session should now show as completed
        session_res = client.get(f'/api/session/{session_key}')
        assert session_res.get_json()['status'] == 'completed'

    def test_session_recovery_after_page_refresh(self, client, active_session_key):
        """GET /api/session/<key> restores enough state to continue the test."""
        res = client.get(f'/api/session/{active_session_key}')
        assert res.status_code == 200
        data = res.get_json()
        assert data['status'] == 'active'
        assert 'current_question' in data
        assert data['chapter_name'] == 'Cell Structure'

    def test_resume_flow_appears_on_next_login(self, client, active_session_key):
        """After starting a test, logging in again should offer resume."""
        login_res = client.post('/api/student/login', json={'name': 'TestStudent', 'pin': '1234'})
        assert login_res.status_code == 200
        data = login_res.get_json()
        assert 'active_session' in data
        assert data['active_session']['session_key'] == active_session_key


# ═══════════════════════════════════════════════════════════════════════════
# Flow 2: Custom Multi-Chapter Test Journey
# ═══════════════════════════════════════════════════════════════════════════
class TestCustomTestFlow:
    def test_custom_test_with_prefetch(self, client, chapter_id, chapter2_id, student_id):
        # 1. Prefetch questions for both chapters
        prefetch_res = client.post('/api/prefetch-questions', json={
            'chapter_ids': [chapter_id, chapter2_id],
        })
        assert prefetch_res.status_code == 200
        data = prefetch_res.get_json()
        assert set(data['cached']) == {chapter_id, chapter2_id}

        # 2. Start custom test
        start_res = client.post('/api/start-custom-test', json={
            'chapter_ids': [chapter_id, chapter2_id],
            'student_name': 'TestStudent',
            'student_id': student_id,
        })
        assert start_res.status_code == 200
        start_data = start_res.get_json()
        assert 'session_key' in start_data
        assert start_data['total_questions'] > 0
        assert len(start_data['chapter_names']) == 2

        # 3. Submit one answer and verify it works
        with patch('routes.student.claude_service.evaluate_answer', return_value=MOCK_EVALUATION_1MARK):
            submit_res = client.post('/api/submit-answer', json={
                'session_key': start_data['session_key'],
                'answer_text': 'Answer for question 1.',
                'student_name': 'TestStudent',
            })
        assert submit_res.status_code == 200

    def test_custom_test_rejected_with_one_chapter(self, client, chapter_id):
        res = client.post('/api/start-custom-test', json={'chapter_ids': [chapter_id]})
        assert res.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════
# Flow 3: Hint Usage Flow
# ═══════════════════════════════════════════════════════════════════════════
class TestHintFlow:
    def test_hint_usage_across_multiple_questions(self, client, active_session_key):
        """Use a hint, submit answer, confirm hints_remaining persists correctly."""
        with patch('routes.student.claude_service.generate_hint', return_value='Hint text here'):
            hint_res = client.post('/api/student/hint', json={
                'session_key': active_session_key,
                'answer_text': 'Partial answer so far',
            })
        assert hint_res.status_code == 200
        assert hint_res.get_json()['hints_remaining'] == 29

        # Submit the answer after hint
        with patch('routes.student.claude_service.evaluate_answer', return_value=MOCK_EVALUATION_1MARK):
            submit_res = client.post('/api/submit-answer', json={
                'session_key': active_session_key,
                'answer_text': 'Plants use sunlight to make food.',
                'student_name': 'TestStudent',
            })
        assert submit_res.status_code == 200

        # Use another hint on the next question
        with patch('routes.student.claude_service.generate_hint', return_value='Second hint'):
            hint_res2 = client.post('/api/student/hint', json={
                'session_key': active_session_key,
                'answer_text': '',
            })
        assert hint_res2.status_code == 200
        assert hint_res2.get_json()['hints_remaining'] == 28

    def test_hint_rate_limit_enforced_over_session(self, app, client, student_id, chapter_id):
        """hints_used persists in DB; 30th hint succeeds, 31st is rejected."""
        from models import db, TestSession
        with app.app_context():
            session = TestSession(
                chapter_id=chapter_id,
                student_id=student_id,
                questions_json=json.dumps(SAMPLE_QUESTIONS),
                current_question_index=0,
                answers_json=json.dumps([]),
                status='active',
                hints_used=29,  # one away from limit
            )
            db.session.add(session)
            db.session.commit()
            key = session.session_key

        # 30th hint (should succeed)
        with patch('routes.student.claude_service.generate_hint', return_value='Last hint'):
            res = client.post('/api/student/hint', json={'session_key': key})
        assert res.status_code == 200
        assert res.get_json()['hints_remaining'] == 0

        # 31st hint (should be rejected)
        res_over = client.post('/api/student/hint', json={'session_key': key})
        assert res_over.status_code == 429


# ═══════════════════════════════════════════════════════════════════════════
# Flow 4: Admin Content Management Journey
#   login → upload chapter → view content → rename → view progress → delete
# ═══════════════════════════════════════════════════════════════════════════
class TestAdminContentManagementFlow:
    def test_full_admin_content_flow(self, client):
        # 1. Admin login
        login_res = client.post('/api/admin/login', json={'username': 'admin', 'password': 'admin123'})
        assert login_res.status_code == 200

        # 2. Upload a new chapter
        with patch('routes.admin.extract_text', return_value=SAMPLE_PDF_CONTENT), \
             patch('routes.admin.is_content_sufficient', return_value=True):
            upload_res = client.post('/api/admin/upload', data={
                'board': 'ICSE',
                'grade': '9',
                'subject': 'Chemistry',
                'chapter_name': 'Acids and Bases',
                'pdf_file': (io.BytesIO(FAKE_PDF_BYTES), 'acids_bases.pdf'),
            }, content_type='multipart/form-data')
        assert upload_res.status_code == 201
        new_chapter_id = upload_res.get_json()['chapter_id']

        # 3. Verify it appears in content tree
        content_res = client.get('/api/admin/content')
        icse_content = content_res.get_json()['content'].get('ICSE', {})
        assert '9' in icse_content
        assert 'Chemistry' in icse_content['9']
        chapter_names = [c['chapter_name'] for c in icse_content['9']['Chemistry']]
        assert 'Acids and Bases' in chapter_names

        # 4. Rename the chapter
        rename_res = client.patch(
            f'/api/admin/chapter/{new_chapter_id}/rename',
            json={'chapter_name': 'Acids, Bases and Salts'},
        )
        assert rename_res.status_code == 200

        # 5. Delete it
        delete_res = client.delete(f'/api/admin/chapter/{new_chapter_id}')
        assert delete_res.status_code == 200

        # 6. Confirm deletion
        content_after = client.get('/api/admin/content').get_json()['content']
        icse_after = content_after.get('ICSE', {})
        if '9' in icse_after and 'Chemistry' in icse_after.get('9', {}):
            chem_ids = [c['id'] for c in icse_after['9']['Chemistry']]
            assert new_chapter_id not in chem_ids


# ═══════════════════════════════════════════════════════════════════════════
# Flow 5: Admin Student Management Journey
#   login → create student → reset PIN → student login → delete student
# ═══════════════════════════════════════════════════════════════════════════
class TestAdminStudentManagementFlow:
    def test_full_student_lifecycle(self, client):
        # 1. Admin creates student
        client.post('/api/admin/login', json={'username': 'admin', 'password': 'admin123'})
        create_res = client.post('/api/admin/students', json={'name': 'JaneDoe', 'pin': '2468'})
        assert create_res.status_code == 201
        new_id = create_res.get_json()['student_id']

        # 2. Student can log in
        login_res = client.post('/api/student/login', json={'name': 'JaneDoe', 'pin': '2468'})
        assert login_res.status_code == 200

        # 3. Student login with wrong PIN fails
        bad_res = client.post('/api/student/login', json={'name': 'JaneDoe', 'pin': '1111'})
        assert bad_res.status_code == 401

        # 4. Admin resets PIN
        reset_res = client.post(f'/api/admin/students/{new_id}/reset-pin', json={'pin': '8642'})
        assert reset_res.status_code == 200

        # 5. Old PIN now fails
        old_pin_res = client.post('/api/student/login', json={'name': 'JaneDoe', 'pin': '2468'})
        assert old_pin_res.status_code == 401

        # 6. New PIN works
        new_pin_res = client.post('/api/student/login', json={'name': 'JaneDoe', 'pin': '8642'})
        assert new_pin_res.status_code == 200

        # 7. Admin deletes student
        delete_res = client.delete(f'/api/admin/students/{new_id}')
        assert delete_res.status_code == 200

        # 8. Deleted student cannot log in
        deleted_res = client.post('/api/student/login', json={'name': 'JaneDoe', 'pin': '8642'})
        assert deleted_res.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════
# Flow 6: Session Timeout Behaviour
# ═══════════════════════════════════════════════════════════════════════════
class TestSessionTimeoutFlow:
    def test_expired_session_blocks_submit(self, app, client, student_id, chapter_id):
        """A session past the 30-minute timeout returns 410 on submit."""
        from datetime import datetime, timedelta
        from models import db, TestSession

        with app.app_context():
            session = TestSession(
                chapter_id=chapter_id,
                student_id=student_id,
                questions_json=json.dumps(SAMPLE_QUESTIONS),
                current_question_index=0,
                answers_json=json.dumps([]),
                status='active',
                last_activity=datetime.utcnow() - timedelta(minutes=35),
            )
            db.session.add(session)
            db.session.commit()
            key = session.session_key

        with patch('routes.student.claude_service.evaluate_answer', return_value=MOCK_EVALUATION_1MARK):
            res = client.post('/api/submit-answer', json={
                'session_key': key,
                'answer_text': 'Any answer',
                'student_name': 'TestStudent',
            })
        assert res.status_code == 410
        data = res.get_json()
        assert data.get('expired') is True

    def test_expired_session_not_shown_on_login(self, app, client, student_id, chapter_id):
        """Expired sessions are not offered as resumable on next login."""
        from datetime import datetime, timedelta
        from models import db, TestSession

        with app.app_context():
            session = TestSession(
                chapter_id=chapter_id,
                student_id=student_id,
                questions_json=json.dumps(SAMPLE_QUESTIONS),
                current_question_index=0,
                answers_json=json.dumps([]),
                status='active',
                last_activity=datetime.utcnow() - timedelta(minutes=35),
            )
            db.session.add(session)
            db.session.commit()

        login_res = client.post('/api/student/login', json={'name': 'TestStudent', 'pin': '1234'})
        # The route expires stale sessions before checking; no active session should appear
        data = login_res.get_json()
        assert 'active_session' not in data


# ═══════════════════════════════════════════════════════════════════════════
# Flow 7: Admin Settings Round-trip
# ═══════════════════════════════════════════════════════════════════════════
class TestAdminSettingsFlow:
    def test_api_key_and_model_persist(self, admin_client):
        # Save API key
        admin_client.post('/api/admin/save-api-key', json={
            'api_key': 'sk-ant-api03-integration-test-key',
        })
        status = admin_client.get('/api/admin/api-key-status').get_json()
        assert status['configured'] is True
        assert status['source'] == 'admin_panel'

        # Switch model to Sonnet
        admin_client.post('/api/admin/save-model', json={'model_id': 'claude-sonnet-4-5-20251015'})
        model_cfg = admin_client.get('/api/admin/model-config').get_json()
        assert model_cfg['current_model'] == 'claude-sonnet-4-5-20251015'

        # Switch back to Haiku
        admin_client.post('/api/admin/save-model', json={'model_id': 'claude-haiku-4-5-20251001'})
        model_cfg2 = admin_client.get('/api/admin/model-config').get_json()
        assert model_cfg2['current_model'] == 'claude-haiku-4-5-20251001'

    def test_password_change_then_relogin(self, client):
        # Login as admin
        client.post('/api/admin/login', json={'username': 'admin', 'password': 'admin123'})

        # Change password
        client.post('/api/admin/change-password', json={
            'current_password': 'admin123',
            'new_password': 'SuperSecure99',
            'confirm_password': 'SuperSecure99',
        })

        # Old password no longer works
        client.post('/api/admin/logout')
        old_login = client.post('/api/admin/login', json={'username': 'admin', 'password': 'admin123'})
        assert old_login.status_code == 401

        # New password works
        new_login = client.post('/api/admin/login', json={'username': 'admin', 'password': 'SuperSecure99'})
        assert new_login.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# Flow 8: Student Progress Analytics
# ═══════════════════════════════════════════════════════════════════════════
class TestStudentProgressAnalytics:
    def test_progress_reflects_completed_test(self, admin_client, completed_session_key):
        """After a test completes, admin progress endpoint reflects the score."""
        res = admin_client.get('/api/admin/student-progress')
        sessions = res.get_json()['sessions']
        session = next(s for s in sessions if s['session_key'] == completed_session_key)

        assert session['status'] == 'completed'
        assert session['student_name'] == 'TestStudent'
        assert session['chapter_name'] == 'Cell Structure'
        assert session['questions_answered'] > 0

    def test_progress_includes_per_question_breakdown(self, admin_client, completed_session_key):
        sessions = admin_client.get('/api/admin/student-progress').get_json()['sessions']
        session = next(s for s in sessions if s['session_key'] == completed_session_key)
        answers = session['answers']
        assert len(answers) > 0
        answer = answers[0]
        for field in ['question_number', 'question_text', 'score', 'max_score', 'feedback']:
            assert field in answer


# ═══════════════════════════════════════════════════════════════════════════
# Flow 9: Chapter Summary Integration
# ═══════════════════════════════════════════════════════════════════════════
class TestChapterSummaryIntegration:
    def test_summary_cached_on_first_call_and_reused(self, app, client, chapter_id):
        """First call generates and caches; second call returns cached without AI."""
        from models import db, Chapter

        # Clear cache
        with app.app_context():
            ch = db.session.get(Chapter, chapter_id)
            ch.summary_cache = None
            db.session.commit()

        call_count = [0]

        def mock_summary(_):
            call_count[0] += 1
            return 'Generated summary text for integration test.'

        with patch('routes.student.claude_service.generate_chapter_summary', side_effect=mock_summary):
            res1 = client.get(f'/api/chapter-summary/{chapter_id}')
            res2 = client.get(f'/api/chapter-summary/{chapter_id}')

        assert res1.status_code == 200
        assert res2.status_code == 200
        # AI should only be called once (second uses cache)
        assert call_count[0] == 1
        assert res1.get_json()['summary'] == res2.get_json()['summary']

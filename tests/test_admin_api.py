"""
Admin API tests — covers every endpoint in routes/admin.py.

PDF extraction is mocked so upload tests work without real PDF files.
"""
import io
import json
from unittest.mock import patch

import pytest

from tests.conftest import SAMPLE_QUESTIONS

# ── Mock return values ────────────────────────────────────────────────────────
MOCK_PDF_CONTENT = 'Biology chapter content. ' * 30  # >300 chars
MOCK_CHAPTER_NAME = 'Cell Division'

# Minimal valid "PDF" bytes for multipart uploads
FAKE_PDF_BYTES = b'%PDF-1.4 fake content for test'


def _fake_pdf(filename='chapter.pdf'):
    return (io.BytesIO(FAKE_PDF_BYTES), filename)


# ═══════════════════════════════════════════════════════════════════════════
# Authentication  POST /api/admin/login  |  POST /api/admin/logout
#                 GET  /api/admin/check-auth
# ═══════════════════════════════════════════════════════════════════════════
class TestAdminAuth:
    def test_login_success(self, client):
        res = client.post('/api/admin/login', json={'username': 'admin', 'password': 'admin123'})
        assert res.status_code == 200
        data = res.get_json()
        assert data['success'] is True
        assert data['username'] == 'admin'

    def test_login_wrong_password(self, client):
        res = client.post('/api/admin/login', json={'username': 'admin', 'password': 'wrongpass'})
        assert res.status_code == 401
        assert 'error' in res.get_json()

    def test_login_wrong_username(self, client):
        res = client.post('/api/admin/login', json={'username': 'nobody', 'password': 'admin123'})
        assert res.status_code == 401

    def test_login_empty_credentials(self, client):
        res = client.post('/api/admin/login', json={})
        assert res.status_code == 401

    def test_logout_clears_session(self, admin_client):
        res = admin_client.post('/api/admin/logout')
        assert res.status_code == 200
        assert res.get_json()['success'] is True
        # Now check-auth should report unauthenticated
        res2 = admin_client.get('/api/admin/check-auth')
        assert res2.get_json()['authenticated'] is False

    def test_check_auth_when_logged_in(self, admin_client):
        res = admin_client.get('/api/admin/check-auth')
        assert res.status_code == 200
        data = res.get_json()
        assert data['authenticated'] is True
        assert data['username'] == 'admin'

    def test_check_auth_when_not_logged_in(self, client):
        res = client.get('/api/admin/check-auth')
        assert res.status_code == 200
        assert res.get_json()['authenticated'] is False

    def test_protected_endpoint_rejects_unauthenticated(self, client):
        res = client.get('/api/admin/content')
        assert res.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════
# Content management  GET /api/admin/content
# ═══════════════════════════════════════════════════════════════════════════
class TestAdminContent:
    def test_get_content_returns_tree(self, admin_client):
        res = admin_client.get('/api/admin/content')
        assert res.status_code == 200
        data = res.get_json()
        assert 'content' in data
        # Seeded data: CBSE → 8 → Biology → [Cell Structure, Plant Kingdom]
        assert 'CBSE' in data['content']
        assert '8' in data['content']['CBSE']
        assert 'Biology' in data['content']['CBSE']['8']

    def test_get_content_chapter_fields(self, admin_client):
        res = admin_client.get('/api/admin/content')
        chapters = res.get_json()['content']['CBSE']['8']['Biology']
        ch = chapters[0]
        assert 'id' in ch
        assert 'chapter_name' in ch
        assert 'has_questions_cache' in ch
        assert ch['has_questions_cache'] is True  # seeded with questions_cache


# ═══════════════════════════════════════════════════════════════════════════
# Upload  POST /api/admin/upload
# ═══════════════════════════════════════════════════════════════════════════
class TestAdminUpload:
    def _upload(self, admin_client, **kwargs):
        data = {
            'board': 'CBSE',
            'grade': '8',
            'subject': 'Maths',
            'chapter_name': 'Algebra Basics',
            'pdf_file': _fake_pdf(),
        }
        data.update(kwargs)
        return admin_client.post(
            '/api/admin/upload',
            data=data,
            content_type='multipart/form-data',
        )

    def test_upload_success(self, admin_client):
        with patch('routes.admin.extract_text', return_value=MOCK_PDF_CONTENT), \
             patch('routes.admin.is_content_sufficient', return_value=True):
            res = self._upload(admin_client)
        assert res.status_code == 201
        data = res.get_json()
        assert data['success'] is True
        assert 'chapter_id' in data
        assert data['chapter_name'] == 'Algebra Basics'

    def test_upload_warns_on_thin_content(self, admin_client):
        with patch('routes.admin.extract_text', return_value='short'), \
             patch('routes.admin.is_content_sufficient', return_value=False):
            res = self._upload(admin_client)
        assert res.status_code == 201
        assert 'warning' in res.get_json()

    def test_upload_invalid_board(self, admin_client):
        with patch('routes.admin.extract_text', return_value=MOCK_PDF_CONTENT), \
             patch('routes.admin.is_content_sufficient', return_value=True):
            res = self._upload(admin_client, board='INVALID')
        assert res.status_code == 400

    def test_upload_invalid_grade(self, admin_client):
        with patch('routes.admin.extract_text', return_value=MOCK_PDF_CONTENT), \
             patch('routes.admin.is_content_sufficient', return_value=True):
            res = self._upload(admin_client, grade='99')
        assert res.status_code == 400

    def test_upload_invalid_subject(self, admin_client):
        with patch('routes.admin.extract_text', return_value=MOCK_PDF_CONTENT), \
             patch('routes.admin.is_content_sufficient', return_value=True):
            res = self._upload(admin_client, subject='Dancing')
        assert res.status_code == 400

    def test_upload_missing_chapter_name(self, admin_client):
        with patch('routes.admin.extract_text', return_value=MOCK_PDF_CONTENT), \
             patch('routes.admin.is_content_sufficient', return_value=True):
            res = self._upload(admin_client, chapter_name='')
        assert res.status_code == 400

    def test_upload_no_file(self, admin_client):
        res = admin_client.post('/api/admin/upload', data={
            'board': 'CBSE', 'grade': '8', 'subject': 'Maths',
            'chapter_name': 'No File Chapter',
        }, content_type='multipart/form-data')
        assert res.status_code == 400

    def test_upload_non_pdf_file(self, admin_client):
        res = admin_client.post('/api/admin/upload', data={
            'board': 'CBSE', 'grade': '8', 'subject': 'Maths',
            'chapter_name': 'Doc Chapter',
            'pdf_file': (io.BytesIO(b'word content'), 'chapter.docx'),
        }, content_type='multipart/form-data')
        assert res.status_code == 400

    def test_upload_duplicate_returns_409(self, admin_client):
        """Uploading a chapter that already exists should return 409 Conflict."""
        with patch('routes.admin.extract_text', return_value=MOCK_PDF_CONTENT), \
             patch('routes.admin.is_content_sufficient', return_value=True):
            # 'Cell Structure' in Biology grade 8 already seeded
            res = admin_client.post('/api/admin/upload', data={
                'board': 'CBSE', 'grade': '8', 'subject': 'Biology',
                'chapter_name': 'Cell Structure',
                'pdf_file': _fake_pdf(),
            }, content_type='multipart/form-data')
        assert res.status_code == 409

    def test_upload_unauthenticated(self, client):
        res = client.post('/api/admin/upload', data={
            'board': 'CBSE', 'grade': '8', 'subject': 'Maths',
            'chapter_name': 'X', 'pdf_file': _fake_pdf(),
        }, content_type='multipart/form-data')
        assert res.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════
# Bulk Upload  POST /api/admin/bulk-upload
# ═══════════════════════════════════════════════════════════════════════════
class TestBulkUpload:
    def test_bulk_upload_success(self, admin_client):
        with patch('routes.admin.extract_text', return_value=MOCK_PDF_CONTENT), \
             patch('routes.admin.is_content_sufficient', return_value=True), \
             patch('routes.admin.extract_chapter_name', return_value=MOCK_CHAPTER_NAME):
            res = admin_client.post('/api/admin/bulk-upload', data={
                'board': 'CBSE', 'grade': '9', 'subject': 'Physics',
                'pdf_files': [_fake_pdf('ch1.pdf'), _fake_pdf('ch2.pdf')],
            }, content_type='multipart/form-data')
        assert res.status_code == 200
        data = res.get_json()
        assert data['success_count'] > 0

    def test_bulk_upload_auto_deduplicates(self, admin_client):
        """Two files that resolve to the same chapter name get renamed (2), (3)…"""
        call_count = [0]

        def name_side_effect(_):
            call_count[0] += 1
            return 'Chapter Alpha'  # always returns same name

        with patch('routes.admin.extract_text', return_value=MOCK_PDF_CONTENT), \
             patch('routes.admin.is_content_sufficient', return_value=True), \
             patch('routes.admin.extract_chapter_name', side_effect=name_side_effect):
            res = admin_client.post('/api/admin/bulk-upload', data={
                'board': 'ICSE', 'grade': '9', 'subject': 'Chemistry',
                'pdf_files': [_fake_pdf('a.pdf'), _fake_pdf('b.pdf')],
            }, content_type='multipart/form-data')
        assert res.status_code == 200
        results = res.get_json()['results']
        names = [r['chapter_name'] for r in results if r['success']]
        assert len(set(names)) == len(names), 'All chapter names should be unique'

    def test_bulk_upload_missing_params(self, admin_client):
        res = admin_client.post('/api/admin/bulk-upload', data={
            'board': 'CBSE', 'grade': '8',
            # missing subject
            'pdf_files': [_fake_pdf()],
        }, content_type='multipart/form-data')
        assert res.status_code == 400

    def test_bulk_upload_no_files(self, admin_client):
        res = admin_client.post('/api/admin/bulk-upload', data={
            'board': 'CBSE', 'grade': '8', 'subject': 'Maths',
        }, content_type='multipart/form-data')
        assert res.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════
# Rename  PATCH /api/admin/chapter/<id>/rename
# ═══════════════════════════════════════════════════════════════════════════
class TestRenameChapter:
    def test_rename_success(self, admin_client, chapter_id):
        res = admin_client.patch(
            f'/api/admin/chapter/{chapter_id}/rename',
            json={'chapter_name': 'Cell Biology Revised'},
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data['success'] is True
        assert data['chapter_name'] == 'Cell Biology Revised'

    def test_rename_to_same_name_ok(self, admin_client, chapter_id):
        """Renaming to the exact same name (self) should succeed."""
        res = admin_client.patch(
            f'/api/admin/chapter/{chapter_id}/rename',
            json={'chapter_name': 'Cell Structure'},
        )
        assert res.status_code == 200

    def test_rename_duplicate_returns_409(self, admin_client, chapter_id):
        """Cannot rename to a name already used by a different chapter."""
        res = admin_client.patch(
            f'/api/admin/chapter/{chapter_id}/rename',
            json={'chapter_name': 'Plant Kingdom'},
        )
        assert res.status_code == 409

    def test_rename_empty_name(self, admin_client, chapter_id):
        res = admin_client.patch(
            f'/api/admin/chapter/{chapter_id}/rename',
            json={'chapter_name': ''},
        )
        assert res.status_code == 400

    def test_rename_chapter_not_found(self, admin_client):
        res = admin_client.patch('/api/admin/chapter/99999/rename', json={'chapter_name': 'X'})
        assert res.status_code == 404

    def test_rename_unauthenticated(self, client, chapter_id):
        res = client.patch(f'/api/admin/chapter/{chapter_id}/rename', json={'chapter_name': 'X'})
        assert res.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════
# Delete  DELETE /api/admin/chapter/<id>
# ═══════════════════════════════════════════════════════════════════════════
class TestDeleteChapter:
    def test_delete_success(self, admin_client, chapter2_id):
        res = admin_client.delete(f'/api/admin/chapter/{chapter2_id}')
        assert res.status_code == 200
        assert res.get_json()['success'] is True

    def test_delete_chapter_not_found(self, admin_client):
        res = admin_client.delete('/api/admin/chapter/99999')
        assert res.status_code == 404

    def test_delete_chapter_disappears_from_content(self, admin_client, chapter2_id):
        admin_client.delete(f'/api/admin/chapter/{chapter2_id}')
        content = admin_client.get('/api/admin/content').get_json()['content']
        biology_chapters = content.get('CBSE', {}).get('8', {}).get('Biology', [])
        ids = [c['id'] for c in biology_chapters]
        assert chapter2_id not in ids

    def test_delete_unauthenticated(self, client, chapter_id):
        res = client.delete(f'/api/admin/chapter/{chapter_id}')
        assert res.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════
# Regenerate questions  POST /api/admin/regenerate-questions/<id>
# ═══════════════════════════════════════════════════════════════════════════
class TestRegenerateQuestions:
    def test_regenerate_success(self, admin_client, chapter_id):
        with patch('routes.admin.claude_service') as mock_svc:
            mock_svc.generate_and_validate_questions.return_value = SAMPLE_QUESTIONS
            res = admin_client.post(f'/api/admin/regenerate-questions/{chapter_id}')
        assert res.status_code == 200
        data = res.get_json()
        assert data['success'] is True
        assert data['question_count'] == len(SAMPLE_QUESTIONS)

    def test_regenerate_chapter_not_found(self, admin_client):
        res = admin_client.post('/api/admin/regenerate-questions/99999')
        assert res.status_code == 404

    def test_regenerate_no_content(self, app, admin_client):
        from models import db, Chapter
        with app.app_context():
            ch = Chapter(
                board='CBSE', grade=10, subject='English',
                chapter_name='Empty', pdf_path='empty.pdf', pdf_content='',
            )
            db.session.add(ch)
            db.session.commit()
            empty_id = ch.id

        res = admin_client.post(f'/api/admin/regenerate-questions/{empty_id}')
        assert res.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
# Student management
#   GET/POST /api/admin/students
#   DELETE   /api/admin/students/<id>
#   POST     /api/admin/students/<id>/reset-pin
# ═══════════════════════════════════════════════════════════════════════════
class TestStudentManagement:
    def test_list_students(self, admin_client):
        res = admin_client.get('/api/admin/students')
        assert res.status_code == 200
        students = res.get_json()['students']
        names = [s['name'] for s in students]
        assert 'TestStudent' in names
        assert 'OtherStudent' in names

    def test_list_students_has_session_counts(self, admin_client):
        students = admin_client.get('/api/admin/students').get_json()['students']
        s = next(s for s in students if s['name'] == 'TestStudent')
        assert 'active_sessions' in s
        assert 'completed_sessions' in s

    def test_create_student_success(self, admin_client):
        res = admin_client.post('/api/admin/students', json={'name': 'NewStudent', 'pin': '4321'})
        assert res.status_code == 201
        data = res.get_json()
        assert data['success'] is True
        assert 'student_id' in data
        assert data['name'] == 'NewStudent'

    def test_create_student_duplicate_name(self, admin_client):
        res = admin_client.post('/api/admin/students', json={'name': 'TestStudent', 'pin': '9999'})
        assert res.status_code == 409

    def test_create_student_invalid_pin_length(self, admin_client):
        res = admin_client.post('/api/admin/students', json={'name': 'ShortPin', 'pin': '12'})
        assert res.status_code == 400

    def test_create_student_non_numeric_pin(self, admin_client):
        res = admin_client.post('/api/admin/students', json={'name': 'AlphaPin', 'pin': 'abcd'})
        assert res.status_code == 400

    def test_create_student_missing_name(self, admin_client):
        res = admin_client.post('/api/admin/students', json={'pin': '1234'})
        assert res.status_code == 400

    def test_delete_student_success(self, admin_client, student_id):
        # Use OtherStudent so we don't break other fixtures that depend on TestStudent
        from models import Student
        other_id = None
        # Get id via API
        students = admin_client.get('/api/admin/students').get_json()['students']
        other = next(s for s in students if s['name'] == 'OtherStudent')
        other_id = other['id']

        res = admin_client.delete(f'/api/admin/students/{other_id}')
        assert res.status_code == 200
        assert res.get_json()['success'] is True

    def test_delete_student_not_found(self, admin_client):
        res = admin_client.delete('/api/admin/students/99999')
        assert res.status_code == 404

    def test_reset_pin_success(self, admin_client, student_id):
        res = admin_client.post(
            f'/api/admin/students/{student_id}/reset-pin',
            json={'pin': '9876'},
        )
        assert res.status_code == 200
        assert res.get_json()['success'] is True

    def test_reset_pin_invalid(self, admin_client, student_id):
        res = admin_client.post(
            f'/api/admin/students/{student_id}/reset-pin',
            json={'pin': 'abc'},
        )
        assert res.status_code == 400

    def test_reset_pin_student_not_found(self, admin_client):
        res = admin_client.post('/api/admin/students/99999/reset-pin', json={'pin': '1234'})
        assert res.status_code == 404

    def test_student_management_unauthenticated(self, client):
        assert client.get('/api/admin/students').status_code == 401
        assert client.post('/api/admin/students', json={}).status_code == 401


# ═══════════════════════════════════════════════════════════════════════════
# Student Progress  GET /api/admin/student-progress
# ═══════════════════════════════════════════════════════════════════════════
class TestStudentProgress:
    def test_progress_returns_sessions(self, admin_client, completed_session_key):
        res = admin_client.get('/api/admin/student-progress')
        assert res.status_code == 200
        sessions = res.get_json()['sessions']
        assert isinstance(sessions, list)
        keys = [s['session_key'] for s in sessions]
        assert completed_session_key in keys

    def test_progress_session_fields(self, admin_client, completed_session_key):
        sessions = admin_client.get('/api/admin/student-progress').get_json()['sessions']
        s = next(s for s in sessions if s['session_key'] == completed_session_key)
        for field in ['student_name', 'chapter_name', 'status', 'total_score',
                      'max_score', 'percentage', 'started_at', 'answers']:
            assert field in s, f'Missing field: {field}'

    def test_progress_unauthenticated(self, client):
        assert client.get('/api/admin/student-progress').status_code == 401


# ═══════════════════════════════════════════════════════════════════════════
# Settings  POST /api/admin/change-password
#           POST /api/admin/save-api-key
#           GET  /api/admin/api-key-status
#           GET  /api/admin/model-config
#           POST /api/admin/save-model
# ═══════════════════════════════════════════════════════════════════════════
class TestAdminSettings:
    # ── Change password ──────────────────────────────────────────────────
    def test_change_password_success(self, admin_client):
        res = admin_client.post('/api/admin/change-password', json={
            'current_password': 'admin123',
            'new_password': 'NewSecure99',
            'confirm_password': 'NewSecure99',
        })
        assert res.status_code == 200
        assert res.get_json()['success'] is True

    def test_change_password_wrong_current(self, admin_client):
        res = admin_client.post('/api/admin/change-password', json={
            'current_password': 'wrongpassword',
            'new_password': 'NewSecure99',
            'confirm_password': 'NewSecure99',
        })
        assert res.status_code == 400

    def test_change_password_mismatch(self, admin_client):
        res = admin_client.post('/api/admin/change-password', json={
            'current_password': 'admin123',
            'new_password': 'NewSecure99',
            'confirm_password': 'DifferentPass',
        })
        assert res.status_code == 400

    def test_change_password_too_short(self, admin_client):
        res = admin_client.post('/api/admin/change-password', json={
            'current_password': 'admin123',
            'new_password': 'abc',
            'confirm_password': 'abc',
        })
        assert res.status_code == 400

    # ── API key ──────────────────────────────────────────────────────────
    def test_save_api_key_success(self, admin_client):
        res = admin_client.post('/api/admin/save-api-key', json={
            'api_key': 'sk-ant-api03-valid-looking-key-1234567890',
        })
        assert res.status_code == 200
        assert res.get_json()['success'] is True

    def test_save_api_key_invalid_prefix(self, admin_client):
        res = admin_client.post('/api/admin/save-api-key', json={'api_key': 'invalid-key-format'})
        assert res.status_code == 400

    def test_save_api_key_empty(self, admin_client):
        res = admin_client.post('/api/admin/save-api-key', json={'api_key': ''})
        assert res.status_code == 400

    def test_api_key_status(self, admin_client):
        res = admin_client.get('/api/admin/api-key-status')
        assert res.status_code == 200
        data = res.get_json()
        assert 'configured' in data
        assert 'source' in data

    def test_api_key_configured_after_save(self, admin_client):
        admin_client.post('/api/admin/save-api-key', json={
            'api_key': 'sk-ant-api03-saved-key-xyz',
        })
        res = admin_client.get('/api/admin/api-key-status')
        data = res.get_json()
        assert data['configured'] is True
        assert data['source'] == 'admin_panel'

    # ── Model config ─────────────────────────────────────────────────────
    def test_get_model_config(self, admin_client):
        res = admin_client.get('/api/admin/model-config')
        assert res.status_code == 200
        data = res.get_json()
        assert 'current_model' in data
        assert 'available_models' in data
        assert len(data['available_models']) == 2

    def test_save_model_valid(self, admin_client):
        res = admin_client.post('/api/admin/save-model', json={
            'model_id': 'claude-sonnet-4-5-20251015',
        })
        assert res.status_code == 200
        assert res.get_json()['success'] is True

    def test_save_model_invalid_id(self, admin_client):
        res = admin_client.post('/api/admin/save-model', json={'model_id': 'gpt-4o'})
        assert res.status_code == 400

    def test_save_model_persists(self, admin_client):
        admin_client.post('/api/admin/save-model', json={'model_id': 'claude-sonnet-4-5-20251015'})
        cfg = admin_client.get('/api/admin/model-config').get_json()
        assert cfg['current_model'] == 'claude-sonnet-4-5-20251015'

    def test_settings_unauthenticated(self, client):
        assert client.post('/api/admin/change-password', json={}).status_code == 401
        assert client.post('/api/admin/save-api-key', json={}).status_code == 401
        assert client.get('/api/admin/model-config').status_code == 401
        assert client.post('/api/admin/save-model', json={}).status_code == 401

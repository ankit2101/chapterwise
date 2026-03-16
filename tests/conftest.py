"""
Shared pytest fixtures for ChapterWise backend tests.

Sets SECRET_KEY in the environment BEFORE importing app modules,
because config.py checks os.environ at class-definition time.
"""
import os
import json
import tempfile

import bcrypt
import pytest

# ── Must be set before any app import ──────────────────────────────────────
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-pytest-32bytes!!')
os.environ.setdefault('ANTHROPIC_API_KEY', 'sk-ant-test-key-placeholder')

from app import create_app          # noqa: E402  (intentional late import)
from models import db as _db, Student, Chapter, TestSession  # noqa: E402


# ── Sample data ─────────────────────────────────────────────────────────────
SAMPLE_QUESTIONS = [
    {
        "question_number": 1,
        "question_text": "What is photosynthesis?",
        "key_points": ["Process by which plants make food using sunlight"],
        "marks": 1,
        "topic_tag": "photosynthesis",
    },
    {
        "question_number": 2,
        "question_text": "Explain the process of respiration.",
        "key_points": [
            "Breakdown of glucose to release energy",
            "Produces carbon dioxide and water",
            "Occurs in mitochondria",
        ],
        "marks": 3,
        "topic_tag": "respiration",
    },
    {
        "question_number": 3,
        "question_text": "Describe the structure of a plant cell.",
        "key_points": [
            "Has a cell wall for rigidity",
            "Contains chloroplasts for photosynthesis",
            "Has a large central vacuole",
            "Bounded by a cell membrane",
            "Contains a nucleus with genetic material",
        ],
        "marks": 5,
        "topic_tag": "cell_structure",
    },
]

SAMPLE_PDF_CONTENT = "Plant biology content. " * 30  # >300 chars — sufficient


# ── Test configuration ───────────────────────────────────────────────────────
class TestConfig:
    """Minimal Flask config for unit/integration tests."""

    SECRET_KEY = 'test-secret-key-for-pytest-32bytes!!'
    TESTING = True
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 32 * 1024 * 1024
    ALLOWED_EXTENSIONS = {'pdf'}
    ANTHROPIC_API_KEY = 'sk-ant-test-key-placeholder'
    CLAUDE_MODEL = 'claude-haiku-4-5-20251001'
    AVAILABLE_MODELS = [
        {'id': 'claude-haiku-4-5-20251001', 'label': 'Claude Haiku', 'description': 'Fast'},
        {'id': 'claude-sonnet-4-5-20251015', 'label': 'Claude Sonnet', 'description': 'Capable'},
    ]
    DEFAULT_ADMIN_USERNAME = 'admin'
    DEFAULT_ADMIN_PASSWORD = 'admin123'
    DEBUG = False

    # Set dynamically by the fixture
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    UPLOAD_FOLDER = None
    STATIC_FOLDER = None


# ── Core fixtures ────────────────────────────────────────────────────────────
@pytest.fixture(scope='function')
def app():
    """Create a fresh Flask app with an in-memory DB for each test."""
    with tempfile.TemporaryDirectory() as upload_dir, \
         tempfile.TemporaryDirectory() as static_dir:

        cfg = TestConfig()
        cfg.UPLOAD_FOLDER = upload_dir
        cfg.STATIC_FOLDER = static_dir

        flask_app = create_app(cfg)

        with flask_app.app_context():
            _db.create_all()
            _seed_test_data()
            yield flask_app
            _db.session.remove()
            _db.drop_all()


def _seed_test_data():
    """Populate the in-memory DB with a student and a chapter."""
    # Student: TestStudent / PIN 1234
    pin_hash = bcrypt.hashpw(b'1234', bcrypt.gensalt()).decode('utf-8')
    student = Student(
        name='TestStudent',
        name_lower='teststudent',
        pin_hash=pin_hash,
    )
    _db.session.add(student)

    # A second student for edge-case tests
    pin_hash2 = bcrypt.hashpw(b'5678', bcrypt.gensalt()).decode('utf-8')
    student2 = Student(
        name='OtherStudent',
        name_lower='otherstudent',
        pin_hash=pin_hash2,
    )
    _db.session.add(student2)

    # Chapter with pre-cached questions (avoids Claude API calls)
    chapter = Chapter(
        board='CBSE',
        grade=8,
        subject='Biology',
        chapter_name='Cell Structure',
        pdf_path='test_cbse_grade8_biology_cell_structure.pdf',
        pdf_content=SAMPLE_PDF_CONTENT,
        questions_cache=json.dumps(SAMPLE_QUESTIONS),
        summary_cache='Plants make food via photosynthesis.',
    )
    _db.session.add(chapter)

    # Second chapter (no questions cached — forces generation for custom-test tests)
    chapter2 = Chapter(
        board='CBSE',
        grade=8,
        subject='Biology',
        chapter_name='Plant Kingdom',
        pdf_path='test_cbse_grade8_biology_plant_kingdom.pdf',
        pdf_content=SAMPLE_PDF_CONTENT,
        questions_cache=json.dumps(SAMPLE_QUESTIONS),  # also cached for speed
    )
    _db.session.add(chapter2)

    _db.session.commit()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin_client(client):
    """HTTP client pre-authenticated as admin."""
    client.post('/api/admin/login', json={'username': 'admin', 'password': 'admin123'})
    return client


# ── Convenience ID fixtures ──────────────────────────────────────────────────
@pytest.fixture
def student_id(app):
    with app.app_context():
        s = Student.query.filter_by(name_lower='teststudent').first()
        return s.id


@pytest.fixture
def chapter_id(app):
    with app.app_context():
        c = Chapter.query.filter_by(chapter_name='Cell Structure').first()
        return c.id


@pytest.fixture
def chapter2_id(app):
    with app.app_context():
        c = Chapter.query.filter_by(chapter_name='Plant Kingdom').first()
        return c.id


@pytest.fixture
def active_session_key(app, student_id, chapter_id):
    """Insert an active TestSession and return its session_key."""
    with app.app_context():
        session = TestSession(
            chapter_id=chapter_id,
            student_id=student_id,
            questions_json=json.dumps(SAMPLE_QUESTIONS),
            current_question_index=0,
            answers_json=json.dumps([]),
            status='active',
        )
        _db.session.add(session)
        _db.session.commit()
        return session.session_key


@pytest.fixture
def completed_session_key(app, student_id, chapter_id):
    """Insert a completed TestSession and return its session_key."""
    answers = [
        {
            'question_number': 1,
            'question_text': SAMPLE_QUESTIONS[0]['question_text'],
            'topic_tag': 'photosynthesis',
            'marks': 1,
            'student_answer': 'Plants make food from sunlight.',
            'covered_points': ['Process by which plants make food using sunlight'],
            'missed_points': [],
            'feedback': 'Great answer!',
            'score': 1,
            'max_score': 1,
        }
    ]
    with app.app_context():
        session = TestSession(
            chapter_id=chapter_id,
            student_id=student_id,
            questions_json=json.dumps(SAMPLE_QUESTIONS),
            current_question_index=3,
            answers_json=json.dumps(answers),
            status='completed',
        )
        _db.session.add(session)
        _db.session.commit()
        return session.session_key

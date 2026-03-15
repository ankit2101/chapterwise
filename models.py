from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import uuid

db = SQLAlchemy()


class Student(db.Model):
    __tablename__ = 'students'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    name_lower = db.Column(db.String(100), unique=True, nullable=False)  # lowercase for lookup
    pin_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    test_sessions = db.relationship('TestSession', backref='student', lazy=True)

    def __repr__(self):
        return f'<Student {self.name}>'


class Admin(db.Model):
    __tablename__ = 'admins'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Admin {self.username}>'


class AppSettings(db.Model):
    __tablename__ = 'app_settings'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<AppSettings {self.key}>'


class Chapter(db.Model):
    __tablename__ = 'chapters'

    id = db.Column(db.Integer, primary_key=True)
    board = db.Column(db.String(10), nullable=False)
    grade = db.Column(db.Integer, nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    chapter_name = db.Column(db.String(200), nullable=False)
    pdf_path = db.Column(db.String(300), nullable=False)
    pdf_content = db.Column(db.Text, nullable=True)
    questions_cache = db.Column(db.Text, nullable=True)
    summary_cache = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('board', 'grade', 'subject', 'chapter_name',
                            name='uq_chapter_identity'),
    )

    test_sessions = db.relationship('TestSession', backref='chapter',
                                    lazy=True, cascade='all, delete-orphan',
                                    foreign_keys='TestSession.chapter_id')

    def __repr__(self):
        return f'<Chapter {self.board} Grade{self.grade} {self.subject}: {self.chapter_name}>'


class TestSession(db.Model):
    __tablename__ = 'test_sessions'

    id = db.Column(db.Integer, primary_key=True)
    session_key = db.Column(db.String(36), unique=True, nullable=False,
                            default=lambda: str(uuid.uuid4()))
    chapter_id = db.Column(db.Integer, db.ForeignKey('chapters.id'), nullable=True)
    chapters_json = db.Column(db.Text, nullable=True)  # JSON array of chapter IDs for custom tests
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=True)
    questions_json = db.Column(db.Text, nullable=True)
    current_question_index = db.Column(db.Integer, default=0)
    answers_json = db.Column(db.Text, default='[]')
    hints_used = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='active')  # active | completed | expired
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<TestSession {self.session_key} status={self.status}>'

import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    _secret = os.environ.get('SECRET_KEY', '').strip()
    if not _secret:
        raise RuntimeError(
            "SECRET_KEY is not set. Add it to your .env file.\n"
            "Generate one with: python3 -c \"import secrets; print(secrets.token_hex(32))\""
        )
    SECRET_KEY = _secret
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'chapterwise.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads', 'pdfs')
    STATIC_FOLDER = os.path.join(BASE_DIR, 'static')
    MAX_CONTENT_LENGTH = 32 * 1024 * 1024  # 32 MB max PDF upload
    ALLOWED_EXTENSIONS = {'pdf'}
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
    CLAUDE_MODEL = 'claude-haiku-4-5-20251001'  # default fallback
    AVAILABLE_MODELS = [
        {
            'id': 'claude-haiku-4-5-20251001',
            'label': 'Claude Haiku',
            'description': 'Fast & economical — ideal for most classrooms',
        },
        {
            'id': 'claude-sonnet-4-5-20251015',
            'label': 'Claude Sonnet',
            'description': 'More capable — richer questions and deeper feedback',
        },
    ]
    DEFAULT_ADMIN_USERNAME = 'admin'
    DEFAULT_ADMIN_PASSWORD = 'admin123'


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False

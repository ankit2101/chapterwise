import os
import re
from flask import Blueprint, request, jsonify, session, current_app
from models import db, Admin, Chapter, AppSettings, Student, TestSession
from services.pdf_service import extract_text, is_content_sufficient
import bcrypt

admin_bp = Blueprint('admin', __name__)


def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return jsonify({'error': 'Authentication required', 'authenticated': False}), 401
        return f(*args, **kwargs)
    return decorated


def _safe_filename(board, grade, subject, chapter_name):
    """Generate a filesystem-safe filename."""
    safe_chapter = re.sub(r'[^\w\s-]', '', chapter_name).strip()
    safe_chapter = re.sub(r'[\s]+', '_', safe_chapter)
    safe_subject = re.sub(r'[^\w]', '_', subject).strip('_')
    return f"{board}_grade{grade}_{safe_subject}_{safe_chapter}.pdf"


# ─── Auth ───

@admin_bp.route('/api/admin/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').encode('utf-8')

    admin = Admin.query.filter_by(username=username).first()
    if admin and bcrypt.checkpw(password, admin.password_hash.encode('utf-8')):
        session['admin_logged_in'] = True
        session['admin_username'] = admin.username
        session.permanent = True
        return jsonify({'success': True, 'username': admin.username})

    return jsonify({'error': 'Invalid username or password'}), 401


@admin_bp.route('/api/admin/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})


@admin_bp.route('/api/admin/check-auth')
def check_auth():
    return jsonify({
        'authenticated': bool(session.get('admin_logged_in')),
        'username': session.get('admin_username', '')
    })


# ─── Content Management ───

@admin_bp.route('/api/admin/content')
@login_required
def get_content():
    chapters = Chapter.query.order_by(
        Chapter.board, Chapter.grade, Chapter.subject, Chapter.chapter_name
    ).all()

    grouped = {}
    for c in chapters:
        board_key = c.board
        grade_key = str(c.grade)
        subject_key = c.subject

        grouped.setdefault(board_key, {})
        grouped[board_key].setdefault(grade_key, {})
        grouped[board_key][grade_key].setdefault(subject_key, [])
        grouped[board_key][grade_key][subject_key].append({
            'id': c.id,
            'chapter_name': c.chapter_name,
            'text_length': len(c.pdf_content) if c.pdf_content else 0,
            'has_questions_cache': bool(c.questions_cache),
            'created_at': c.created_at.strftime('%d %b %Y')
        })

    return jsonify({'content': grouped})


@admin_bp.route('/api/admin/upload', methods=['POST'])
@login_required
def upload():
    board = request.form.get('board', '').strip()
    grade_str = request.form.get('grade', '').strip()
    subject = request.form.get('subject', '').strip()
    chapter_name = request.form.get('chapter_name', '').strip()
    pdf_file = request.files.get('pdf_file')

    # Validate
    errors = []
    if not board or board not in ('CBSE', 'ICSE'):
        errors.append('Board must be CBSE or ICSE.')
    try:
        grade = int(grade_str)
        if grade not in range(6, 11):
            errors.append('Grade must be between 6 and 10.')
    except (ValueError, TypeError):
        grade = None
        errors.append('Grade must be a number between 6 and 10.')
    if not subject:
        errors.append('Subject name is required.')
    if not chapter_name:
        errors.append('Chapter name is required.')
    if len(chapter_name) > 200:
        errors.append('Chapter name must be 200 characters or less.')
    if not pdf_file or pdf_file.filename == '':
        errors.append('Please select a PDF file.')
    elif not pdf_file.filename.lower().endswith('.pdf'):
        errors.append('Only PDF files (.pdf) are accepted.')

    if errors:
        return jsonify({'error': '; '.join(errors)}), 400

    # Duplicate check
    existing = Chapter.query.filter_by(
        board=board, grade=grade, subject=subject, chapter_name=chapter_name
    ).first()
    if existing:
        return jsonify({'error': 'A chapter with this name already exists for this board/grade/subject.'}), 409

    # Save PDF
    filename = _safe_filename(board, grade, subject, chapter_name)
    upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)

    # Handle filename collision
    if os.path.exists(upload_path):
        base, ext = os.path.splitext(filename)
        import time
        filename = f"{base}_{int(time.time())}{ext}"
        upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)

    pdf_file.save(upload_path)

    # Extract text
    try:
        pdf_content = extract_text(upload_path)
    except ValueError as e:
        os.remove(upload_path)
        return jsonify({'error': str(e)}), 422

    warning = None
    if not is_content_sufficient(pdf_content):
        warning = (
            'Very little text was extracted from this PDF. '
            'It may be an image-based or scanned PDF. '
            'Students may not be able to start a test for this chapter.'
        )

    chapter = Chapter(
        board=board,
        grade=grade,
        subject=subject,
        chapter_name=chapter_name,
        pdf_path=filename,
        pdf_content=pdf_content,
        questions_cache=None
    )
    db.session.add(chapter)
    db.session.commit()

    result = {
        'success': True,
        'chapter_id': chapter.id,
        'chapter_name': chapter_name,
        'text_length': len(pdf_content)
    }
    if warning:
        result['warning'] = warning
    return jsonify(result), 201


@admin_bp.route('/api/admin/chapter/<int:chapter_id>', methods=['DELETE'])
@login_required
def delete_chapter(chapter_id):
    chapter = db.session.get(Chapter, chapter_id)
    if not chapter:
        return jsonify({'error': 'Chapter not found'}), 404

    # Delete physical PDF
    pdf_path = os.path.join(current_app.config['UPLOAD_FOLDER'], chapter.pdf_path)
    if os.path.exists(pdf_path):
        try:
            os.remove(pdf_path)
        except OSError:
            pass  # File already gone, continue

    db.session.delete(chapter)
    db.session.commit()
    return jsonify({'success': True, 'deleted_id': chapter_id})


@admin_bp.route('/api/admin/regenerate-questions/<int:chapter_id>', methods=['POST'])
@login_required
def regenerate_questions(chapter_id):
    """Clear cached questions so they get regenerated on next test start."""
    chapter = db.session.get(Chapter, chapter_id)
    if not chapter:
        return jsonify({'error': 'Chapter not found'}), 404
    chapter.questions_cache = None
    db.session.commit()
    return jsonify({'success': True, 'message': 'Questions cache cleared. New questions will be generated on next test.'})


# ─── Settings ───

@admin_bp.route('/api/admin/change-password', methods=['POST'])
@login_required
def change_password():
    data = request.get_json() or {}
    current_pw = data.get('current_password', '').encode('utf-8')
    new_pw = data.get('new_password', '').strip()
    confirm_pw = data.get('confirm_password', '').strip()

    admin = Admin.query.filter_by(username=session['admin_username']).first()
    if not admin:
        return jsonify({'error': 'Admin account not found'}), 404

    if not bcrypt.checkpw(current_pw, admin.password_hash.encode('utf-8')):
        return jsonify({'error': 'Current password is incorrect'}), 400

    if new_pw != confirm_pw:
        return jsonify({'error': 'New passwords do not match'}), 400

    if len(new_pw) < 8:
        return jsonify({'error': 'New password must be at least 8 characters long'}), 400

    admin.password_hash = bcrypt.hashpw(
        new_pw.encode('utf-8'), bcrypt.gensalt()
    ).decode('utf-8')
    db.session.commit()
    return jsonify({'success': True, 'message': 'Password changed successfully'})


@admin_bp.route('/api/admin/save-api-key', methods=['POST'])
@login_required
def save_api_key():
    data = request.get_json() or {}
    api_key = data.get('api_key', '').strip()

    if not api_key:
        return jsonify({'error': 'API key cannot be empty'}), 400

    if not api_key.startswith('sk-ant-'):
        return jsonify({'error': 'Invalid API key format. Anthropic keys start with "sk-ant-"'}), 400

    setting = AppSettings.query.filter_by(key='anthropic_api_key').first()
    if setting:
        setting.value = api_key
    else:
        setting = AppSettings(key='anthropic_api_key', value=api_key)
        db.session.add(setting)
    db.session.commit()
    return jsonify({'success': True, 'message': 'API key saved successfully'})


@admin_bp.route('/api/admin/api-key-status')
@login_required
def api_key_status():
    setting = AppSettings.query.filter_by(key='anthropic_api_key').first()
    configured = bool(setting and setting.value and setting.value.strip())

    # Also check env var as fallback
    from flask import current_app
    env_key = current_app.config.get('ANTHROPIC_API_KEY', '')
    fallback = bool(env_key and env_key.strip())

    return jsonify({
        'configured': configured or fallback,
        'source': 'admin_panel' if configured else ('env_variable' if fallback else 'none')
    })


# ─── Student Management ───

@admin_bp.route('/api/admin/students')
@login_required
def list_students():
    students = Student.query.order_by(Student.name).all()
    result = []
    for s in students:
        active = TestSession.query.filter_by(student_id=s.id, status='active').count()
        completed = TestSession.query.filter_by(student_id=s.id, status='completed').count()
        result.append({
            'id': s.id,
            'name': s.name,
            'created_at': s.created_at.strftime('%d %b %Y'),
            'active_sessions': active,
            'completed_sessions': completed,
        })
    return jsonify({'students': result})


@admin_bp.route('/api/admin/students', methods=['POST'])
@login_required
def create_student():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    pin = str(data.get('pin', '')).strip()

    if not name:
        return jsonify({'error': 'Name is required'}), 400
    if not pin or len(pin) != 4 or not pin.isdigit():
        return jsonify({'error': 'PIN must be exactly 4 digits'}), 400

    name_lower = name.lower()
    if Student.query.filter_by(name_lower=name_lower).first():
        return jsonify({'error': f'A student named "{name}" already exists'}), 409

    try:
        pin_hash = bcrypt.hashpw(pin.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        student = Student(name=name, name_lower=name_lower, pin_hash=pin_hash)
        db.session.add(student)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Could not create student: {str(e)}'}), 500

    return jsonify({'success': True, 'student_id': student.id, 'name': student.name}), 201


@admin_bp.route('/api/admin/students/<int:student_id>', methods=['DELETE'])
@login_required
def delete_student(student_id):
    student = db.session.get(Student, student_id)
    if not student:
        return jsonify({'error': 'Student not found'}), 404
    db.session.delete(student)
    db.session.commit()
    return jsonify({'success': True})


@admin_bp.route('/api/admin/students/<int:student_id>/reset-pin', methods=['POST'])
@login_required
def reset_student_pin(student_id):
    data = request.get_json() or {}
    new_pin = str(data.get('pin', '')).strip()

    if not new_pin or len(new_pin) != 4 or not new_pin.isdigit():
        return jsonify({'error': 'New PIN must be exactly 4 digits'}), 400

    student = db.session.get(Student, student_id)
    if not student:
        return jsonify({'error': 'Student not found'}), 404

    student.pin_hash = bcrypt.hashpw(new_pin.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    db.session.commit()
    return jsonify({'success': True, 'message': f'PIN reset for {student.name}'})

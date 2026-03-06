import os
import re
import json
from flask import Blueprint, request, jsonify, session, current_app
from models import db, Admin, Chapter, AppSettings, Student, TestSession
from services.pdf_service import extract_text, is_content_sufficient, extract_chapter_name
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


def _unique_chapter_name(board, grade, subject, base_name):
    """
    Return base_name if no duplicate exists for this board/grade/subject,
    otherwise append (2), (3) … until a unique name is found.
    """
    name = base_name
    counter = 2
    while Chapter.query.filter_by(
        board=board, grade=grade, subject=subject, chapter_name=name
    ).first():
        suffix = f' ({counter})'
        name = base_name[: 200 - len(suffix)] + suffix
        counter += 1
    return name


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


@admin_bp.route('/api/admin/bulk-upload', methods=['POST'])
@login_required
def bulk_upload():
    """Upload multiple chapter PDFs at once. Chapter names are auto-extracted from the first page."""
    import tempfile
    import shutil
    import time as time_module

    board = request.form.get('board', '').strip()
    grade_str = request.form.get('grade', '').strip()
    subject = request.form.get('subject', '').strip()
    pdf_files = request.files.getlist('pdf_files')

    # Validate common fields
    errors = []
    if not board or board not in ('CBSE', 'ICSE'):
        errors.append('Board must be CBSE or ICSE.')
    grade = None
    try:
        grade = int(grade_str)
        if grade not in range(6, 11):
            errors.append('Grade must be between 6 and 10.')
    except (ValueError, TypeError):
        errors.append('Grade must be a number between 6 and 10.')
    if not subject:
        errors.append('Subject name is required.')
    if not pdf_files or all(f.filename == '' for f in pdf_files):
        errors.append('Please select at least one PDF file.')
    if errors:
        return jsonify({'error': '; '.join(errors)}), 400

    upload_folder = current_app.config['UPLOAD_FOLDER']
    results = []

    for pdf_file in pdf_files:
        if not pdf_file.filename or pdf_file.filename == '':
            continue

        file_result = {
            'filename': pdf_file.filename,
            'success': False,
            'chapter_name': None,
            'error': None,
            'warning': None,
        }

        if not pdf_file.filename.lower().endswith('.pdf'):
            file_result['error'] = 'Not a PDF file.'
            results.append(file_result)
            continue

        temp_path = None
        final_path = None

        try:
            # Save to a temp file so we can extract text before committing
            with tempfile.NamedTemporaryFile(
                dir=upload_folder, suffix='.pdf', delete=False
            ) as tmp:
                pdf_file.save(tmp)
                temp_path = tmp.name

            # Extract chapter name from first page
            chapter_name = extract_chapter_name(temp_path)
            if not chapter_name:
                file_result['error'] = (
                    'Could not extract a chapter name from the first page. '
                    'Use single upload to enter the name manually.'
                )
                results.append(file_result)
                continue

            chapter_name = chapter_name[:200]

            # Auto-deduplicate: append (2), (3) … if a chapter with the same name exists
            original_name = chapter_name
            chapter_name = _unique_chapter_name(board, grade, subject, chapter_name)
            file_result['chapter_name'] = chapter_name
            if chapter_name != original_name:
                file_result['renamed'] = True

            # Determine final path
            filename = _safe_filename(board, grade, subject, chapter_name)
            final_path = os.path.join(upload_folder, filename)
            if os.path.exists(final_path):
                base, ext = os.path.splitext(filename)
                filename = f"{base}_{int(time_module.time())}{ext}"
                final_path = os.path.join(upload_folder, filename)

            shutil.move(temp_path, final_path)
            temp_path = None  # Already moved — don't delete in finally

            # Extract full text content
            pdf_content = extract_text(final_path)

            warning = None
            if not is_content_sufficient(pdf_content):
                warning = (
                    'Very little text was extracted. '
                    'This may be an image-based or scanned PDF.'
                )
                file_result['warning'] = warning

            chapter = Chapter(
                board=board,
                grade=grade,
                subject=subject,
                chapter_name=chapter_name,
                pdf_path=filename,
                pdf_content=pdf_content,
                questions_cache=None,
            )
            db.session.add(chapter)
            db.session.commit()

            file_result['success'] = True
            file_result['chapter_id'] = chapter.id
            file_result['text_length'] = len(pdf_content)

        except ValueError as e:
            db.session.rollback()
            if final_path and os.path.exists(final_path):
                try:
                    os.remove(final_path)
                except OSError:
                    pass
            file_result['error'] = str(e)

        except Exception as e:
            db.session.rollback()
            if final_path and os.path.exists(final_path):
                try:
                    os.remove(final_path)
                except OSError:
                    pass
            file_result['error'] = f'Unexpected error: {str(e)}'

        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

        results.append(file_result)

    success_count = sum(1 for r in results if r['success'])
    return jsonify({
        'results': results,
        'total': len(results),
        'success_count': success_count,
        'failure_count': len(results) - success_count,
    }), 200 if success_count > 0 else 422


@admin_bp.route('/api/admin/chapter/<int:chapter_id>/pdf')
@login_required
def serve_chapter_pdf(chapter_id):
    from flask import send_from_directory
    chapter = db.session.get(Chapter, chapter_id)
    if not chapter:
        return jsonify({'error': 'Chapter not found'}), 404
    upload_folder = current_app.config['UPLOAD_FOLDER']
    return send_from_directory(
        upload_folder,
        chapter.pdf_path,
        mimetype='application/pdf',
        as_attachment=False,
    )


@admin_bp.route('/api/admin/chapter/<int:chapter_id>/rename', methods=['PATCH'])
@login_required
def rename_chapter(chapter_id):
    chapter = db.session.get(Chapter, chapter_id)
    if not chapter:
        return jsonify({'error': 'Chapter not found'}), 404

    data = request.get_json() or {}
    new_name = data.get('chapter_name', '').strip()

    if not new_name:
        return jsonify({'error': 'Chapter name cannot be empty'}), 400
    if len(new_name) > 200:
        return jsonify({'error': 'Chapter name must be 200 characters or less'}), 400

    # Duplicate check (exclude self)
    existing = Chapter.query.filter_by(
        board=chapter.board, grade=chapter.grade,
        subject=chapter.subject, chapter_name=new_name
    ).first()
    if existing and existing.id != chapter_id:
        return jsonify({'error': f'"{new_name}" already exists for this board / grade / subject'}), 409

    chapter.chapter_name = new_name
    db.session.commit()
    return jsonify({'success': True, 'chapter_name': new_name})


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


@admin_bp.route('/api/admin/model-config')
@login_required
def get_model_config():
    """Return available models and the currently selected model."""
    setting = AppSettings.query.filter_by(key='claude_model').first()
    current_model = (
        setting.value.strip()
        if setting and setting.value and setting.value.strip()
        else current_app.config.get('CLAUDE_MODEL', 'claude-haiku-4-5-20251001')
    )
    return jsonify({
        'current_model': current_model,
        'available_models': current_app.config.get('AVAILABLE_MODELS', []),
    })


@admin_bp.route('/api/admin/save-model', methods=['POST'])
@login_required
def save_model():
    """Persist the admin's chosen Claude model to AppSettings."""
    data = request.get_json() or {}
    model_id = data.get('model_id', '').strip()

    available_ids = [m['id'] for m in current_app.config.get('AVAILABLE_MODELS', [])]
    if not model_id or model_id not in available_ids:
        return jsonify({'error': f'Invalid model. Choose from: {", ".join(available_ids)}'}), 400

    setting = AppSettings.query.filter_by(key='claude_model').first()
    if setting:
        setting.value = model_id
    else:
        setting = AppSettings(key='claude_model', value=model_id)
        db.session.add(setting)
    db.session.commit()

    label = next((m['label'] for m in current_app.config['AVAILABLE_MODELS'] if m['id'] == model_id), model_id)
    return jsonify({'success': True, 'message': f'Model switched to {label}', 'model_id': model_id})


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


@admin_bp.route('/api/admin/student-progress')
@login_required
def student_progress():
    """Return all test sessions with student/chapter info, scores, and time taken."""
    sessions = (
        TestSession.query
        .order_by(TestSession.created_at.desc())
        .all()
    )
    result = []
    for s in sessions:
        answers = json.loads(s.answers_json) if s.answers_json else []
        questions = json.loads(s.questions_json) if s.questions_json else []
        total_score = sum(a.get('score', 0) for a in answers)
        max_score = sum(a.get('max_score', 0) for a in answers)
        percentage = round((total_score / max_score * 100), 1) if max_score > 0 else None

        duration_seconds = None
        if s.last_activity and s.created_at:
            duration_seconds = max(0, int((s.last_activity - s.created_at).total_seconds()))

        chapter = s.chapter
        result.append({
            'session_key': s.session_key,
            'student_name': s.student.name if s.student else 'Guest',
            'student_id': s.student_id,
            'chapter_name': chapter.chapter_name,
            'subject': chapter.subject,
            'grade': chapter.grade,
            'board': chapter.board,
            'status': s.status,
            'total_score': total_score,
            'max_score': max_score,
            'percentage': percentage,
            'questions_answered': len(answers),
            'total_questions': len(questions),
            'duration_seconds': duration_seconds,
            'started_at': s.created_at.strftime('%d %b %Y, %I:%M %p'),
            'answers': [
                {
                    'question_number': a.get('question_number'),
                    'question_text': a.get('question_text', ''),
                    'topic_tag': a.get('topic_tag', ''),
                    'marks': a.get('marks', 1),
                    'score': a.get('score', 0),
                    'max_score': a.get('max_score', 0),
                    'feedback': a.get('feedback', ''),
                    'student_answer': a.get('student_answer', ''),
                    'covered_points': a.get('covered_points', []),
                    'missed_points': a.get('missed_points', []),
                }
                for a in answers
            ],
        })
    return jsonify({'sessions': result})


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

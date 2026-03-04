import os
from flask import Flask, send_from_directory, send_file
from flask_cors import CORS
from models import db, Admin
from config import DevelopmentConfig
import bcrypt


def create_app(config=DevelopmentConfig):
    app = Flask(__name__, static_folder=None)
    app.config.from_object(config)

    # Ensure directories exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['STATIC_FOLDER'], exist_ok=True)

    # Enable CORS for development (Vite dev server on :5173)
    CORS(app, supports_credentials=True, origins=[
        'http://localhost:5173',
        'http://127.0.0.1:5173',
        'http://localhost:5000',
    ])

    # Initialize extensions
    db.init_app(app)

    # Register blueprints
    from routes.student import student_bp
    from routes.admin import admin_bp
    app.register_blueprint(student_bp)
    app.register_blueprint(admin_bp)

    # Create tables and seed admin
    with app.app_context():
        db.create_all()
        _seed_admin(app)

    # JSON error handlers for all /api/* routes
    from flask import request as _req, jsonify as _jsonify

    @app.errorhandler(404)
    def not_found(e):
        if _req.path.startswith('/api/'):
            return _jsonify({'error': 'Endpoint not found'}), 404
        static_dir = app.config['STATIC_FOLDER']
        index_path = os.path.join(static_dir, 'index.html')
        if os.path.exists(index_path):
            return send_file(index_path)
        return str(e), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        if _req.path.startswith('/api/'):
            return _jsonify({'error': 'Method not allowed'}), 405
        return str(e), 405

    @app.errorhandler(500)
    def internal_error(e):
        if _req.path.startswith('/api/'):
            return _jsonify({'error': f'Server error: {e}'}), 500
        return str(e), 500

    # Serve React SPA for any non-API route (production mode)
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_react(path):
        from flask import request as _req, jsonify as _jsonify
        # Return JSON 404 for unknown /api/* paths (not caught by blueprints)
        if path.startswith('api/'):
            return _jsonify({'error': 'Endpoint not found'}), 404
        static_dir = app.config['STATIC_FOLDER']
        # If it's a real static file, serve it
        if path and os.path.exists(os.path.join(static_dir, path)):
            return send_from_directory(static_dir, path)
        # Otherwise serve index.html (React Router handles routing)
        index_path = os.path.join(static_dir, 'index.html')
        if os.path.exists(index_path):
            return send_file(index_path)
        return (
            '<h2>ChapterWise API is running.</h2>'
            '<p>Run <code>cd frontend && npm run dev</code> to start the React app.</p>',
            200
        )

    return app


def _seed_admin(app):
    if not Admin.query.filter_by(username=app.config['DEFAULT_ADMIN_USERNAME']).first():
        hashed = bcrypt.hashpw(
            app.config['DEFAULT_ADMIN_PASSWORD'].encode('utf-8'),
            bcrypt.gensalt()
        ).decode('utf-8')
        admin = Admin(
            username=app.config['DEFAULT_ADMIN_USERNAME'],
            password_hash=hashed
        )
        db.session.add(admin)
        db.session.commit()
        print(f"[ChapterWise] Default admin created: {app.config['DEFAULT_ADMIN_USERNAME']}")


if __name__ == '__main__':
    app = create_app()
    print("\n" + "=" * 50)
    print("  ChapterWise is running!")
    print("  Flask API: http://localhost:5000")
    print("  Open a second terminal and run:")
    print("    cd frontend && npm run dev")
    print("  Then open: http://localhost:5173")
    print("=" * 50 + "\n")
    app.run(debug=True, port=5000)

#!/bin/bash
# ChapterWise Startup Script
# Run this file to start the application

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo ""
echo "======================================="
echo "   Starting ChapterWise"
echo "======================================="
echo ""

# Start Flask in background
echo "Starting backend server..."
python3 app.py &
FLASK_PID=$!

# Give Flask a moment to start
sleep 2

echo ""
echo "======================================="
echo "  ChapterWise is ready!"
echo ""
echo "  Open your browser and go to:"
echo "  http://localhost:5000"
echo ""
echo "  Admin Panel: http://localhost:5000/admin/login"
echo "  Username: admin  |  Password: admin123"
echo ""
echo "  Press Ctrl+C to stop the server."
echo "======================================="
echo ""

# Open browser automatically (macOS)
if command -v open &> /dev/null; then
  sleep 1
  open "http://localhost:5000"
fi

# Wait for Flask process
wait $FLASK_PID

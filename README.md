# ChapterWise

An AI-powered chapter-wise test platform for Indian school students (Grade 6–10). Students practise by answering questions verbally — the app listens, evaluates their answer against key concepts, and gives instant encouraging feedback.

---

## Features

### Student Portal
- **Student login** — Students log in with a name and 4-digit PIN assigned by their teacher (no self-registration)
- **Session management** — 30-minute inactivity timeout with automatic session expiry; active sessions resume on re-login
- **Cascading selection** — Board (CBSE / ICSE) → Grade → Subject → Chapter, all populated from uploaded PDFs
- **CBSE-pattern question paper** — Three sections per chapter, scaled to chapter size:
  - **Section A** — 10–15 one-mark questions (definitions, single facts, one-liners)
  - **Section B** — 5–10 three-mark questions (brief explanations, 3 key points)
  - **Section C** — 5–10 five-mark questions (detailed answers, 5 key points)
- **Marks-aware hints** — Each question shows its mark value and a plain-English guide on how much to write
- **Full-topic coverage** — Questions are scaled to chapter size (simple / medium / large) and distributed across every section of the chapter
- **Voice answers** — Speak your answer; the browser transcribes it in real time using the Web Speech API
- **Text-to-Speech** — Each question is read aloud automatically; a replay button is always available
- **Shuffled questions** — Question order is randomised on every new test attempt so no two attempts are identical
- **AI evaluation** — Claude checks whether the student covered the key points (lenient on grammar, sequence, and phrasing)
- **Encouraging feedback** — Points covered shown in green; missed points shown in amber with a gentle reminder
- **Test summary** — Total score, percentage, section-wise breakdown (Section A / B / C), missed topics, and a per-question breakdown at the end

### Admin Panel
- **Student management** — Create student accounts with name + 4-digit PIN, reset PINs, and delete students from the dashboard
- **PDF upload** — Attach a board, grade, subject, and chapter name to any PDF
- **Content management** — View, organise, and delete uploaded chapters
- **Student progress** — View every student's test attempts, scores, time taken, and per-question breakdown in a searchable, paginated table
- **Question cache** — Questions are generated once and cached; a "Refresh Questions" button forces regeneration
- **AI model selection** — Switch between Claude Haiku (fast & economical) and Claude Sonnet (more capable) from the Settings page — no server restart needed
- **API key management** — Enter the Anthropic API key directly in the UI (no server restarts needed)
- **Password change** — Update the admin password from the settings page
- **Secure by default** — bcrypt-hashed passwords, session-based authentication

### UI & Branding
- **ChapterWise logo** — Displayed in the header of every page; clicking it returns to the home page
- **Brand colour scheme** — Blue-to-green gradient matching the ChapterWise logo throughout the portal
- **Mobile-friendly** — Fully responsive layout for phones and tablets

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.9+, Flask 3.0, SQLAlchemy, SQLite |
| AI | Anthropic Claude API (Haiku & Sonnet; selectable per deployment) |
| PDF Extraction | pdfplumber |
| Frontend | React 19, Vite, React Router v7 |
| Voice Input | Browser Web Speech API (`en-IN`) |
| Text-to-Speech | Browser `speechSynthesis` API |
| Auth | bcrypt, Flask sessions, PIN-based student login |

---

## Prerequisites

- **Python 3.9+**
- **Node.js 24.14.0+** and **npm 10+**
- An **Anthropic API key** — get one at [console.anthropic.com](https://console.anthropic.com)

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/ankit2101/chapterwise.git
cd chapterwise
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

### 4. Configure environment

Create a `.env` file in the project root:

```bash
# Required — change this to a long random string before deploying
SECRET_KEY=chapterwise-secret-change-in-prod-2024

# Optional — fallback Anthropic API key.
# You can also set this through Admin Panel → Settings after startup.
# ANTHROPIC_API_KEY=sk-ant-...
```

> The `SECRET_KEY` secures Flask session cookies. Any long random string works for local use. For production, generate one with `python3 -c "import secrets; print(secrets.token_hex(32))"`.

> The `ANTHROPIC_API_KEY` set through the Admin Panel takes precedence over the `.env` value.

---

## Running the App

### Development mode (recommended for local use)

Open **two terminals**:

**Terminal 1 — Flask API server:**
```bash
python app.py
```

**Terminal 2 — Vite dev server (hot reload):**
```bash
cd frontend
npm run dev
```

Open **http://localhost:5173** in your browser.

> Voice input works best in **Google Chrome**. Other browsers may not support the Web Speech API.

---

### Production mode (single server)

Build the React app once, then serve everything from Flask:

```bash
cd frontend && npm run build && cd ..
python app.py
```

Open **http://localhost:5000**.

---

### Quick start script (macOS)

A convenience script starts the server and opens the browser automatically:

```bash
./start.sh
```

---

## First-time Setup (Admin)

1. Open `http://localhost:5000/admin/login`
2. Log in with the default credentials:
   - **Username:** `admin`
   - **Password:** `admin123`
3. Go to **Settings** → paste your Anthropic API key → click **Save API Key**
4. (Optional) In **Settings → AI Model**, choose between **Claude Haiku** (faster, cheaper) and **Claude Sonnet** (richer questions, deeper feedback) → click **Save Model**
5. Go to **Dashboard** → **Student Management** section → create student accounts:
   - Enter a student name and a 4-digit PIN
   - Share the name and PIN with the student (students cannot self-register)
6. Upload your first PDF:
   - Select Board, Grade, Subject, and enter a Chapter Name
   - Upload the PDF (up to 32 MB)
7. The app extracts text automatically. Chapters with very little text (scanned/image PDFs) will show a warning.

> **Change the default password** immediately after first login via Settings → Change Password.

---

## How It Works

```
Admin creates student accounts (name + 4-digit PIN)
Admin uploads PDF
        ↓
Text extracted by pdfplumber
        ↓
Student logs in with name + PIN
        ↓
Student selects Board → Grade → Subject → Chapter → Start Test
        ↓
Claude counts chapter subtopics and generates:
  • 10–15 one-mark questions  (Section A)
  • 5–10  three-mark questions (Section B)
  • 5–10  five-mark questions  (Section C)
(Questions cached after first run; cover every section of the chapter)
        ↓
Question displayed with mark value + answer-length hint
Question read aloud via Text-to-Speech
        ↓
Student speaks answer → Web Speech API → transcript appears in text area
        ↓
Student submits → Claude evaluates key-point coverage
        ↓
Feedback shown: covered points ✓ | missed points → (with gentle guidance)
        ↓
Next question … until all questions answered
        ↓
Summary: total score, section-wise breakdown, missed topics, per-question detail
```

---

## Question Generation

Questions are generated by Claude and scaled to chapter complexity:

| Chapter size | Section A (1 mark) | Section B (3 marks) | Section C (5 marks) | Total |
|---|---|---|---|---|
| Simple (1–4 subtopics) | 10 | 5 | 5 | 20 |
| Medium (5–7 subtopics) | 12 | 7 | 7 | 26 |
| Large (8+ subtopics) | 15 | 10 | 10 | 35 |

Every subtopic of the chapter appears in at least one question across all three sections. The number of key points per question exactly matches its mark value (1 key point for 1-mark, 3 for 3-mark, 5 for 5-mark), so scoring is transparent and proportional.

---

## Project Structure

```
chapterwise/
├── app.py                  # Flask app factory, SPA catch-all route
├── config.py               # Configuration (model, DB path, upload folder)
├── models.py               # SQLAlchemy models: Student, Admin, Chapter, TestSession, AppSettings
├── requirements.txt
│
├── routes/
│   ├── student.py          # /api/student/login, /api/grades, /api/subjects, /api/chapters,
│   │                       # /api/start-test, /api/submit-answer, /api/session/<key>
│   └── admin.py            # /api/admin/* (login, upload, delete, password, API key, model config, students, student-progress)
│
├── services/
│   ├── pdf_service.py      # pdfplumber text extraction + cleaning
│   └── claude_service.py   # Question generation (3 sections) + answer evaluation prompts
│
├── frontend/
│   ├── vite.config.js      # Dev proxy (/api → :5000), build output → ../static/
│   └── src/
│       ├── App.jsx          # React Router route definitions
│       ├── context/         # AdminAuthContext, StudentAuthContext (login state)
│       ├── api/             # studentApi.js, adminApi.js (fetch wrappers)
│       ├── hooks/           # useSpeechRecognition.js, useTextToSpeech.js
│       ├── components/
│       │   ├── student/     # StudentLogin, SelectionPage, TestPage,
│       │   │                # QuestionCard, VoiceInput, FeedbackCard, SummaryPage
│       │   ├── admin/       # AdminLogin, AdminDashboard, UploadForm,
│       │   │                # ChapterTable, AdminSettings, StudentManagement, StudentProgress
│       │   └── shared/      # LoadingOverlay, Toast, ProtectedRoute,
│       │                    # StudentProtectedRoute, Logo
│       └── styles/          # student.css, admin.css
│
├── static/                 # Built React output (gitignored; regenerated by npm run build)
├── uploads/pdfs/           # Uploaded chapter PDFs (gitignored)
└── chapterwise.db          # SQLite database (gitignored, auto-created on first run)
```

---

## Configuration

### Environment Variables (`.env`)

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | **Required** | *(none — app will not start without it)* | Flask session secret. Generate with `python3 -c "import secrets; print(secrets.token_hex(32))"`. |
| `ANTHROPIC_API_KEY` | Optional | *(none)* | Fallback Anthropic API key. Can be set via Admin Panel → Settings instead. |

Generate a secure secret key:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### App Configuration (`config.py`)

| Setting | Value | Description |
|---|---|---|
| `CLAUDE_MODEL` | `claude-haiku-4-5-20251001` | Default Claude model (fallback if not set via Admin Panel) |
| `AVAILABLE_MODELS` | Haiku, Sonnet | Models selectable from Admin Panel → Settings → AI Model |
| `MAX_CONTENT_LENGTH` | `32 MB` | Maximum PDF upload size |
| `SQLALCHEMY_DATABASE_URI` | `sqlite:///chapterwise.db` | SQLite database in the project root |
| `UPLOAD_FOLDER` | `uploads/pdfs/` | Directory where uploaded PDFs are stored |
| `DEFAULT_ADMIN_USERNAME` | `admin` | Initial admin username (change via Admin Panel) |
| `DEFAULT_ADMIN_PASSWORD` | `admin123` | Initial admin password (change immediately after first login) |

These settings live in `config.py` and can be overridden via environment variables where applicable.

---

## API Reference

### Student Endpoints

| Method | URL | Description |
|---|---|---|
| `POST` | `/api/student/login` | Authenticate student with name + PIN |
| `POST` | `/api/student/session-ping` | Keep session alive (resets 30-min timer) |
| `GET` | `/api/grades?board=CBSE` | Available grades for a board |
| `GET` | `/api/subjects?board=CBSE&grade=8` | Subjects for board + grade |
| `GET` | `/api/chapters?board=CBSE&grade=8&subject=Science` | Chapters for board + grade + subject |
| `POST` | `/api/start-test` | Create session, generate questions, return first question |
| `POST` | `/api/submit-answer` | Evaluate answer, return feedback + next question or summary |
| `GET` | `/api/session/<key>` | Restore session state (used on page refresh) |

### Admin Endpoints (require session cookie)

| Method | URL | Description |
|---|---|---|
| `POST` | `/api/admin/login` | Authenticate admin |
| `POST` | `/api/admin/logout` | Clear session |
| `GET` | `/api/admin/content` | All chapters grouped by board/grade/subject |
| `POST` | `/api/admin/upload` | Upload PDF + metadata |
| `DELETE` | `/api/admin/chapter/<id>` | Delete chapter and PDF file |
| `POST` | `/api/admin/change-password` | Update admin password |
| `POST` | `/api/admin/save-api-key` | Store Anthropic API key |
| `GET` | `/api/admin/api-key-status` | Check if API key is configured |
| `GET` | `/api/admin/model-config` | Get available models and currently active model |
| `POST` | `/api/admin/save-model` | Switch the active Claude model |
| `GET` | `/api/admin/students` | List all students with session counts |
| `POST` | `/api/admin/students` | Create a new student (name + PIN) |
| `DELETE` | `/api/admin/students/<id>` | Delete a student account |
| `POST` | `/api/admin/students/<id>/reset-pin` | Reset a student's PIN |
| `GET` | `/api/admin/student-progress` | All test sessions with scores, time, and per-question breakdown |

---

## Notes

- **Voice input** requires **Google Chrome** (or another Chromium-based browser). Firefox and Safari do not support the Web Speech API. Students on unsupported browsers can type their answers instead.
- **Image-based PDFs** (scanned documents) will extract very little text. The admin dashboard shows a warning for these files, and tests cannot be started until sufficient text is available.
- **Question caching** — questions for a chapter are generated once and stored in the database. Use the **Refresh Q** button in the admin dashboard to regenerate them (e.g., after re-uploading a better PDF). Caching must be cleared manually if the question format changes.
- **Model selection** — switching the Claude model (Haiku ↔ Sonnet) takes effect immediately for all new question generation and answer evaluation; no server restart is required. Previously cached questions are unaffected until regenerated.
- The app is designed for **local / classroom use**. For internet-facing deployment, set a strong `SECRET_KEY`, use HTTPS, and consider adding rate limiting.

---

## License

MIT

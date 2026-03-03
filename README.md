# ChapterWise

An AI-powered chapter-wise test platform for Indian school students (Grade 6–10). Students practise by answering questions verbally — the app listens, evaluates their answer against key concepts, and gives instant encouraging feedback.

---

## Features

### Student Portal
- **Cascading selection** — Board (CBSE / ICSE) → Grade → Subject → Chapter, all populated from uploaded PDFs
- **Voice answers** — Speak your answer; the browser transcribes it in real time using the Web Speech API
- **Text-to-Speech** — Each question is read aloud automatically; a replay button is always available
- **AI evaluation** — Claude checks whether the student covered the key points (lenient on grammar, sequence, and phrasing)
- **Encouraging feedback** — Points covered shown in green; missed points shown in amber with a gentle reminder
- **Full-topic coverage** — Claude generates enough questions to cover every topic in the chapter
- **Test summary** — Score, percentage, missed topics, and a per-question breakdown at the end

### Admin Panel
- **PDF upload** — Attach a board, grade, subject, and chapter name to any PDF
- **Content management** — View, organise, and delete uploaded chapters
- **Question cache** — Questions are generated once and cached; a "Refresh Questions" button forces regeneration
- **API key management** — Enter the Anthropic API key directly in the UI (no server restarts needed)
- **Password change** — Update the admin password from the settings page
- **Secure by default** — bcrypt-hashed passwords, session-based authentication

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.9+, Flask 3.0, SQLAlchemy, SQLite |
| AI | Anthropic Claude API (`claude-haiku-4-5-20251001`) |
| PDF Extraction | pdfplumber |
| Frontend | React 18, Vite, React Router v6 |
| Voice Input | Browser Web Speech API (`en-IN`) |
| Text-to-Speech | Browser `speechSynthesis` API |
| Auth | bcrypt, Flask sessions |

---

## Prerequisites

- **Python 3.9+**
- **Node.js 18+** and **npm**
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

```bash
cp .env.example .env
```

`.env` is only needed for an optional fallback API key and the secret key. The Anthropic API key can also be entered through the Admin Panel UI after startup.

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
4. Go to **Dashboard** → upload your first PDF:
   - Select Board, Grade, Subject, and enter a Chapter Name
   - Upload the PDF (up to 32 MB)
5. The app extracts text automatically. Chapters with very little text (scanned/image PDFs) will show a warning.

> **Change the default password** immediately after first login via Settings → Change Password.

---

## How It Works

```
Admin uploads PDF
        ↓
Text extracted by pdfplumber
        ↓
Student selects Board → Grade → Subject → Chapter → Start Test
        ↓
Claude generates 6–12 questions covering all chapter topics (cached after first run)
        ↓
Question displayed + read aloud via Text-to-Speech
        ↓
Student speaks answer → Web Speech API → transcript appears in text area
        ↓
Student submits → Claude evaluates key point coverage
        ↓
Feedback shown: covered points ✓ | missed points → (with gentle guidance)
        ↓
Next question … until all topics covered
        ↓
Summary: total score, percentage, missed topics, per-question breakdown
```

---

## Project Structure

```
chapterwise/
├── app.py                  # Flask app factory, SPA catch-all route
├── config.py               # Configuration (model, DB path, upload folder)
├── models.py               # SQLAlchemy models: Admin, Chapter, TestSession, AppSettings
├── requirements.txt
│
├── routes/
│   ├── student.py          # /api/grades, /api/subjects, /api/chapters,
│   │                       # /api/start-test, /api/submit-answer, /api/session/<key>
│   └── admin.py            # /api/admin/* (login, upload, delete, password, API key)
│
├── services/
│   ├── pdf_service.py      # pdfplumber text extraction + cleaning
│   └── claude_service.py   # Question generation + answer evaluation prompts
│
├── frontend/
│   ├── vite.config.js      # Dev proxy (/api → :5000), build output → ../static/
│   └── src/
│       ├── App.jsx          # React Router route definitions
│       ├── context/         # AdminAuthContext (login state)
│       ├── api/             # studentApi.js, adminApi.js (fetch wrappers)
│       ├── hooks/           # useSpeechRecognition.js, useTextToSpeech.js
│       ├── components/
│       │   ├── student/     # SelectionPage, TestPage, QuestionCard,
│       │   │                # VoiceInput, FeedbackCard, SummaryPage
│       │   ├── admin/       # AdminLogin, AdminDashboard, UploadForm,
│       │   │                # ChapterTable, AdminSettings
│       │   └── shared/      # LoadingOverlay, Toast, ProtectedRoute
│       └── styles/          # student.css, admin.css
│
├── uploads/pdfs/           # Uploaded chapter PDFs (gitignored)
├── static/                 # Built React output (gitignored, regenerated by npm run build)
└── chapterwise.db          # SQLite database (gitignored, auto-created on first run)
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Recommended | Flask session secret. Change before deploying. |
| `ANTHROPIC_API_KEY` | Optional | Fallback API key. Can be set via Admin Panel instead. |

The Anthropic API key set through the Admin Panel takes precedence over the environment variable.

---

## API Reference

### Student Endpoints

| Method | URL | Description |
|---|---|---|
| `GET` | `/api/grades?board=CBSE` | Available grades for a board |
| `GET` | `/api/subjects?board=CBSE&grade=8` | Subjects for board + grade |
| `GET` | `/api/chapters?board=CBSE&grade=8&subject=Science` | Chapters for board + grade + subject |
| `POST` | `/api/start-test` | Create session, generate questions, return first question |
| `POST` | `/api/submit-answer` | Evaluate answer, return feedback + next question or summary |
| `GET` | `/api/session/<key>` | Restore session state (used on page refresh) |

### Admin Endpoints (require session cookie)

| Method | URL | Description |
|---|---|---|
| `POST` | `/api/admin/login` | Authenticate |
| `POST` | `/api/admin/logout` | Clear session |
| `GET` | `/api/admin/content` | All chapters grouped by board/grade/subject |
| `POST` | `/api/admin/upload` | Upload PDF + metadata |
| `DELETE` | `/api/admin/chapter/<id>` | Delete chapter and PDF file |
| `POST` | `/api/admin/change-password` | Update admin password |
| `POST` | `/api/admin/save-api-key` | Store Anthropic API key |
| `GET` | `/api/admin/api-key-status` | Check if API key is configured |

---

## Notes

- **Voice input** requires **Google Chrome** (or another Chromium-based browser). Firefox and Safari do not support the Web Speech API. Students on unsupported browsers can type their answers instead.
- **Image-based PDFs** (scanned documents) will extract very little text. The admin dashboard shows a warning for these files, and tests cannot be started until sufficient text is available.
- **Question caching** — questions for a chapter are generated once and stored in the database. Use the **Refresh Q** button in the admin dashboard to regenerate them (e.g., after re-uploading a better PDF).
- The app is designed for **local / classroom use**. For internet-facing deployment, set a strong `SECRET_KEY`, use HTTPS, and consider adding rate limiting.

---

## License

MIT

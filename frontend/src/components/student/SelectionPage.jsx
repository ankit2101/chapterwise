import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getGrades, getSubjects, getChapters, startTest } from '../../api/studentApi';
import LoadingOverlay from '../shared/LoadingOverlay';
import Logo from '../shared/Logo';

const BOARDS = ['CBSE', 'ICSE'];

export default function SelectionPage() {
  const [board, setBoard] = useState('');
  const [grade, setGrade] = useState('');
  const [subject, setSubject] = useState('');
  const [chapterId, setChapterId] = useState('');
  const [studentName, setStudentName] = useState('');

  const [grades, setGrades] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [chapters, setChapters] = useState([]);

  const [loading, setLoading] = useState(false);
  const [startingTest, setStartingTest] = useState(false);
  const [error, setError] = useState('');

  const navigate = useNavigate();

  // Load grades when board changes
  useEffect(() => {
    if (!board) { setGrades([]); setGrade(''); return; }
    setGrade('');
    setSubject('');
    setChapterId('');
    setLoading(true);
    getGrades(board)
      .then(data => setGrades(data.grades || []))
      .catch(() => setGrades([]))
      .finally(() => setLoading(false));
  }, [board]);

  // Load subjects when grade changes
  useEffect(() => {
    if (!board || !grade) { setSubjects([]); setSubject(''); return; }
    setSubject('');
    setChapterId('');
    setLoading(true);
    getSubjects(board, grade)
      .then(data => setSubjects(data.subjects || []))
      .catch(() => setSubjects([]))
      .finally(() => setLoading(false));
  }, [board, grade]);

  // Load chapters when subject changes
  useEffect(() => {
    if (!board || !grade || !subject) { setChapters([]); setChapterId(''); return; }
    setChapterId('');
    setLoading(true);
    getChapters(board, grade, subject)
      .then(data => setChapters(data.chapters || []))
      .catch(() => setChapters([]))
      .finally(() => setLoading(false));
  }, [board, grade, subject]);

  const handleStartTest = async () => {
    if (!chapterId) {
      setError('Please select a chapter to start the test.');
      return;
    }
    setError('');
    setStartingTest(true);
    try {
      const data = await startTest(parseInt(chapterId), studentName);
      navigate(`/test/${data.session_key}`, {
        state: {
          sessionData: data,
          studentName,
        }
      });
    } catch (err) {
      setError(err.message);
      setStartingTest(false);
    }
  };

  const canStart = board && grade && subject && chapterId;

  return (
    <div className="selection-page">
      {startingTest && <LoadingOverlay message="Generating questions for this chapter... This takes about 15 seconds." />}

      <header className="site-header">
        <div className="header-inner">
          <Logo size="md" />
          <p className="tagline">Master Your Chapters. Revise Smarter.</p>
        </div>
      </header>

      <main className="selection-main">
        <div className="welcome-section">
          <h1>Hello! Let&apos;s start practising</h1>
          <p>Select your board, grade, subject, and chapter to begin a test.</p>
        </div>

        <div className="selection-card">
          <div className="form-group">
            <label htmlFor="student-name">Your Name (optional)</label>
            <input
              id="student-name"
              type="text"
              value={studentName}
              onChange={e => setStudentName(e.target.value)}
              placeholder="Enter your name for personalised feedback"
              maxLength={50}
            />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="board-select">Board</label>
              <select id="board-select" value={board} onChange={e => setBoard(e.target.value)}>
                <option value="">Select Board</option>
                {BOARDS.map(b => <option key={b} value={b}>{b}</option>)}
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="grade-select">Grade</label>
              <select
                id="grade-select"
                value={grade}
                onChange={e => setGrade(e.target.value)}
                disabled={grades.length === 0}
              >
                <option value="">
                  {!board ? 'Select Board first' : grades.length === 0 ? 'No grades available' : 'Select Grade'}
                </option>
                {grades.map(g => <option key={g} value={g}>Grade {g}</option>)}
              </select>
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="subject-select">Subject</label>
            <select
              id="subject-select"
              value={subject}
              onChange={e => setSubject(e.target.value)}
              disabled={subjects.length === 0}
            >
              <option value="">
                {!grade ? 'Select Grade first' : subjects.length === 0 ? 'No subjects available' : 'Select Subject'}
              </option>
              {subjects.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="chapter-select">Chapter</label>
            <select
              id="chapter-select"
              value={chapterId}
              onChange={e => setChapterId(e.target.value)}
              disabled={chapters.length === 0}
            >
              <option value="">
                {!subject ? 'Select Subject first' : chapters.length === 0 ? 'No chapters available' : 'Select Chapter'}
              </option>
              {chapters.map(c => (
                <option key={c.id} value={c.id}>{c.chapter_name}</option>
              ))}
            </select>
          </div>

          {error && <div className="alert alert-error">{error}</div>}

          <button
            className="btn btn-start"
            onClick={handleStartTest}
            disabled={!canStart || loading || startingTest}
          >
            {startingTest ? 'Preparing Test...' : 'Start Test'}
          </button>
        </div>

        <div className="how-it-works">
          <h2>How it works</h2>
          <div className="steps">
            <div className="step">
              <div className="step-number">1</div>
              <p>Select your chapter above</p>
            </div>
            <div className="step">
              <div className="step-number">2</div>
              <p>Answer questions by speaking or typing</p>
            </div>
            <div className="step">
              <div className="step-number">3</div>
              <p>Get instant feedback on your answers</p>
            </div>
          </div>
        </div>
      </main>

      <footer className="site-footer">
        <a href="/admin/login" className="admin-link">Admin Panel</a>
      </footer>
    </div>
  );
}

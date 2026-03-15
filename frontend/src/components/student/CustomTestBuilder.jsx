import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  getGrades, getSubjects, getChapters,
  getChapterSummary, startCustomTest,
} from '../../api/studentApi';
import { useStudentAuth } from '../../context/StudentAuthContext';
import LoadingOverlay from '../shared/LoadingOverlay';
import Logo from '../shared/Logo';
import { SUBJECTS } from '../../constants/subjects';

const BOARDS = ['CBSE', 'ICSE'];

// ─── Step indicator ──────────────────────────────────────────
function StepIndicator({ current }) {
  const steps = ['Select Board & Grade', 'Choose Chapters', 'Review & Start'];
  return (
    <div className="custom-test-steps">
      {steps.map((label, i) => (
        <div
          key={i}
          className={`custom-test-step ${i + 1 === current ? 'active' : ''} ${i + 1 < current ? 'done' : ''}`}
        >
          <div className="custom-test-step-num">{i + 1 < current ? '✓' : i + 1}</div>
          <span>{label}</span>
        </div>
      ))}
    </div>
  );
}

// ─── Main component ──────────────────────────────────────────
export default function CustomTestBuilder() {
  const { student, logout } = useStudentAuth();
  const navigate = useNavigate();

  const [step, setStep] = useState(1);

  // Step 1 state
  const [board, setBoard] = useState('');
  const [grade, setGrade] = useState('');
  const [grades, setGrades] = useState([]);
  const [loadingGrades, setLoadingGrades] = useState(false);

  // Step 2 state
  const [subject, setSubject] = useState('');
  const [subjects, setSubjects] = useState([]);
  const [chapters, setChapters] = useState([]);
  const [loadingSubjects, setLoadingSubjects] = useState(false);
  const [loadingChapters, setLoadingChapters] = useState(false);
  const [basket, setBasket] = useState([]); // [{id, chapter_name, subject}]

  // Step 3 state
  const [summaries, setSummaries] = useState({}); // { chapterId: { summary, loading, error } }
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState('');

  // Load grades on board change
  useEffect(() => {
    if (!board) { setGrades([]); setGrade(''); return; }
    setGrade('');
    setLoadingGrades(true);
    getGrades(board)
      .then(d => setGrades(d.grades || []))
      .catch(() => setGrades([]))
      .finally(() => setLoadingGrades(false));
  }, [board]);

  // Load subjects when board+grade are set
  useEffect(() => {
    if (!board || !grade) { setSubjects([]); setSubject(''); return; }
    setSubject('');
    setChapters([]);
    setLoadingSubjects(true);
    getSubjects(board, grade)
      .then(d => {
        const list = d.subjects || [];
        const sorted = [...list].sort((a, b) => {
          const ia = SUBJECTS.indexOf(a), ib = SUBJECTS.indexOf(b);
          if (ia === -1 && ib === -1) return a.localeCompare(b);
          if (ia === -1) return 1;
          if (ib === -1) return -1;
          return ia - ib;
        });
        setSubjects(sorted);
      })
      .catch(() => setSubjects([]))
      .finally(() => setLoadingSubjects(false));
  }, [board, grade]);

  // Load chapters when subject changes
  useEffect(() => {
    if (!board || !grade || !subject) { setChapters([]); return; }
    setLoadingChapters(true);
    getChapters(board, grade, subject)
      .then(d => setChapters(d.chapters || []))
      .catch(() => setChapters([]))
      .finally(() => setLoadingChapters(false));
  }, [board, grade, subject]);

  // Fetch summaries when entering step 3
  useEffect(() => {
    if (step !== 3) return;
    basket.forEach(ch => {
      if (summaries[ch.id]) return; // already fetched or fetching
      setSummaries(prev => ({ ...prev, [ch.id]: { loading: true } }));
      getChapterSummary(ch.id)
        .then(d => setSummaries(prev => ({ ...prev, [ch.id]: { summary: d.summary, loading: false } })))
        .catch(() => setSummaries(prev => ({
          ...prev, [ch.id]: { summary: null, loading: false, error: 'Could not load summary.' }
        })));
    });
  }, [step]); // eslint-disable-line react-hooks/exhaustive-deps

  function toggleChapter(chapter) {
    setBasket(prev => {
      const exists = prev.find(c => c.id === chapter.id);
      if (exists) return prev.filter(c => c.id !== chapter.id);
      return [...prev, { id: chapter.id, chapter_name: chapter.chapter_name, subject }];
    });
  }

  function isInBasket(id) {
    return basket.some(c => c.id === id);
  }

  async function handleStartTest() {
    setStartError('');
    setStarting(true);
    try {
      const data = await startCustomTest(
        basket.map(c => c.id),
        student?.name || '',
        student?.id || null
      );
      navigate(`/test/${data.session_key}`, {
        state: { sessionData: data, studentName: student?.name || '' }
      });
    } catch (err) {
      setStartError(err.message);
      setStarting(false);
    }
  }

  return (
    <div className="selection-page">
      {starting && <LoadingOverlay message="Building your custom test... This may take a moment." />}

      <header className="site-header">
        <div className="header-inner">
          <Logo size="md" />
          <div className="header-right">
            {student && (
              <div className="student-info">
                <span className="student-greeting">Hi, <strong>{student.name}</strong></span>
                <button className="btn btn-sm btn-ghost" onClick={logout}>Logout</button>
              </div>
            )}
            <p className="tagline">Master Your Chapters. Revise Smarter.</p>
          </div>
        </div>
      </header>

      <main className="selection-main">
        <div className="welcome-section">
          <h1>Custom Test Builder</h1>
          <p>Pick chapters from one or more subjects to create your personalised test.</p>
        </div>

        <StepIndicator current={step} />

        {/* ── Step 1: Board & Grade ── */}
        {step === 1 && (
          <div className="selection-card">
            <h2 className="card-section-title">Select Board &amp; Grade</h2>
            <div className="form-row">
              <div className="form-group">
                <label htmlFor="ctb-board">Board</label>
                <select id="ctb-board" value={board} onChange={e => setBoard(e.target.value)}>
                  <option value="">Select Board</option>
                  {BOARDS.map(b => <option key={b} value={b}>{b}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label htmlFor="ctb-grade">Grade</label>
                <select
                  id="ctb-grade"
                  value={grade}
                  onChange={e => setGrade(e.target.value)}
                  disabled={!board || loadingGrades}
                >
                  <option value="">
                    {!board ? 'Select Board first' : loadingGrades ? 'Loading...' : grades.length === 0 ? 'No grades available' : 'Select Grade'}
                  </option>
                  {grades.map(g => <option key={g} value={g}>Grade {g}</option>)}
                </select>
              </div>
            </div>

            <div className="custom-test-actions">
              <button className="btn btn-ghost" onClick={() => navigate('/')}>Back</button>
              <button
                className="btn btn-primary"
                disabled={!board || !grade}
                onClick={() => setStep(2)}
              >
                Next: Choose Chapters
              </button>
            </div>
          </div>
        )}

        {/* ── Step 2: Choose Chapters ── */}
        {step === 2 && (
          <div className="selection-card">
            <h2 className="card-section-title">Choose Chapters</h2>
            <p className="card-subtitle">
              Select a subject, then click chapters to add them to your test.
            </p>

            <div className="form-group">
              <label htmlFor="ctb-subject">Subject</label>
              <select
                id="ctb-subject"
                value={subject}
                onChange={e => setSubject(e.target.value)}
                disabled={loadingSubjects}
              >
                <option value="">
                  {loadingSubjects ? 'Loading...' : subjects.length === 0 ? 'No subjects available' : 'Select Subject'}
                </option>
                {subjects.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>

            {/* Chapter list */}
            {subject && (
              <div className="chapter-list">
                {loadingChapters ? (
                  <p className="chapter-list-hint">Loading chapters...</p>
                ) : chapters.length === 0 ? (
                  <p className="chapter-list-hint">No chapters available for this subject.</p>
                ) : (
                  chapters.map(c => (
                    <button
                      key={c.id}
                      className={`chapter-list-item ${isInBasket(c.id) ? 'selected' : ''}`}
                      onClick={() => toggleChapter(c)}
                    >
                      <span className="chapter-list-check">{isInBasket(c.id) ? '✓' : '+'}</span>
                      {c.chapter_name}
                    </button>
                  ))
                )}
              </div>
            )}

            {/* Basket */}
            <div className="basket-section">
              <h3 className="basket-title">
                Your Test ({basket.length} chapter{basket.length !== 1 ? 's' : ''} selected)
              </h3>
              {basket.length === 0 ? (
                <p className="basket-empty">No chapters added yet. Select at least 2 to continue.</p>
              ) : (
                <div className="basket-chips">
                  {basket.map(c => (
                    <span key={c.id} className="basket-chip">
                      <span className="basket-chip-subject">{c.subject}</span>
                      {c.chapter_name}
                      <button
                        className="basket-chip-remove"
                        onClick={() => setBasket(prev => prev.filter(x => x.id !== c.id))}
                        aria-label={`Remove ${c.chapter_name}`}
                      >×</button>
                    </span>
                  ))}
                </div>
              )}
            </div>

            <div className="custom-test-actions">
              <button className="btn btn-ghost" onClick={() => setStep(1)}>Back</button>
              <button
                className="btn btn-primary"
                disabled={basket.length < 2}
                onClick={() => setStep(3)}
              >
                Next: Review Chapters
              </button>
            </div>
          </div>
        )}

        {/* ── Step 3: Review summaries & Start ── */}
        {step === 3 && (
          <div className="selection-card">
            <h2 className="card-section-title">Review Your Chapters</h2>
            <p className="card-subtitle">
              Read the chapter summaries below, then start your custom test when ready.
            </p>

            <div className="summary-cards">
              {basket.map(ch => {
                const state = summaries[ch.id] || {};
                return (
                  <div key={ch.id} className="summary-card">
                    <div className="summary-card-header">
                      <span className="summary-card-subject">{ch.subject}</span>
                      <h3 className="summary-card-title">{ch.chapter_name}</h3>
                    </div>
                    <div className="summary-card-body">
                      {state.loading ? (
                        <div className="summary-skeleton">
                          <div className="skeleton-line" />
                          <div className="skeleton-line short" />
                          <div className="skeleton-line" />
                        </div>
                      ) : state.error ? (
                        <p className="summary-card-error">{state.error}</p>
                      ) : (
                        <p className="summary-card-text">{state.summary}</p>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            {startError && <div className="alert alert-error">{startError}</div>}

            <div className="custom-test-actions">
              <button className="btn btn-ghost" onClick={() => setStep(2)}>Back</button>
              <button
                className="btn btn-start"
                onClick={handleStartTest}
                disabled={starting}
              >
                {starting ? 'Preparing Test...' : `Start Custom Test (${basket.length} chapters)`}
              </button>
            </div>
          </div>
        )}
      </main>

      <footer className="site-footer">
        <a href="/admin/login" className="admin-link">Admin Panel</a>
      </footer>
    </div>
  );
}

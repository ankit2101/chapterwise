import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useLocation, useNavigate } from 'react-router-dom';
import { submitAnswer, getSession, sessionPing, requestHint } from '../../api/studentApi';
import QuestionCard from './QuestionCard';
import VoiceInput from './VoiceInput';
import FeedbackCard from './FeedbackCard';
import SummaryPage from './SummaryPage';
import LoadingOverlay from '../shared/LoadingOverlay';
import Logo from '../shared/Logo';

const VIEW = {
  LOADING: 'loading',
  QUESTION: 'question',
  FEEDBACK: 'feedback',
  SUMMARY: 'summary',
  ERROR: 'error',
  EXPIRED: 'expired',
};

const INACTIVITY_WARN_MS = 25 * 60 * 1000;  // 25 minutes
const INACTIVITY_EXPIRE_MS = 30 * 60 * 1000; // 30 minutes
const PING_INTERVAL_MS = 5 * 60 * 1000;      // ping every 5 minutes

export default function TestPage() {
  const { sessionKey } = useParams();
  const location = useLocation();
  const navigate = useNavigate();

  const [view, setView] = useState(VIEW.LOADING);
  const [sessionInfo, setSessionInfo] = useState(null);
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [totalQuestions, setTotalQuestions] = useState(0);
  const [answer, setAnswer] = useState('');
  const [evaluation, setEvaluation] = useState(null);
  const [answeredQuestion, setAnsweredQuestion] = useState(null);
  const [summary, setSummary] = useState(null);
  const [isLastQuestion, setIsLastQuestion] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [studentName, setStudentName] = useState('');
  const [showInactivityWarning, setShowInactivityWarning] = useState(false);
  const [hint, setHint] = useState('');
  const [hintLoading, setHintLoading] = useState(false);
  const [hintUsed, setHintUsed] = useState(false);

  const inactivityWarnTimer = useRef(null);
  const inactivityExpireTimer = useRef(null);
  const pingTimer = useRef(null);

  const handleSessionExpired = useCallback(() => {
    setView(VIEW.EXPIRED);
  }, []);

  const resetInactivityTimers = useCallback(() => {
    clearTimeout(inactivityWarnTimer.current);
    clearTimeout(inactivityExpireTimer.current);
    setShowInactivityWarning(false);
    inactivityWarnTimer.current = setTimeout(() => {
      setShowInactivityWarning(true);
    }, INACTIVITY_WARN_MS);
    inactivityExpireTimer.current = setTimeout(() => {
      handleSessionExpired();
    }, INACTIVITY_EXPIRE_MS);
  }, [handleSessionExpired]);

  // Start inactivity timers when test is active
  useEffect(() => {
    if (view === VIEW.QUESTION || view === VIEW.FEEDBACK) {
      resetInactivityTimers();
    }
    return () => {
      clearTimeout(inactivityWarnTimer.current);
      clearTimeout(inactivityExpireTimer.current);
    };
  }, [view, resetInactivityTimers]);

  // Periodic server ping
  useEffect(() => {
    if (!sessionKey) return;
    pingTimer.current = setInterval(async () => {
      try {
        const res = await sessionPing(sessionKey);
        if (res.status === 'expired') handleSessionExpired();
      } catch { /* ignore */ }
    }, PING_INTERVAL_MS);
    return () => clearInterval(pingTimer.current);
  }, [sessionKey, handleSessionExpired]);

  useEffect(() => {
    const locState = location.state;

    if (locState?.sessionData) {
      // Fresh test — data passed via navigate state
      const data = locState.sessionData;
      setSessionInfo({
        chapterName: data.chapter_name,
        subject: data.subject,
        grade: data.grade,
        board: data.board,
      });
      setCurrentQuestion(data.current_question);
      setTotalQuestions(data.total_questions);
      setStudentName(locState.studentName || '');
      setView(VIEW.QUESTION);
    } else {
      // Page refresh — reload from server
      getSession(sessionKey)
        .then(data => {
          setSessionInfo({
            chapterName: data.chapter_name,
            subject: data.subject,
            grade: data.grade,
            board: data.board,
          });
          setTotalQuestions(data.total_questions);

          if (data.status === 'completed') {
            setSummary(data.summary);
            setView(VIEW.SUMMARY);
          } else if (data.current_question) {
            setCurrentQuestion(data.current_question);
            setView(VIEW.QUESTION);
          } else {
            setError('Session data is incomplete. Please start a new test.');
            setView(VIEW.ERROR);
          }
        })
        .catch(err => {
          setError(err.message);
          setView(VIEW.ERROR);
        });
    }
  }, [sessionKey]);

  const handleSubmit = async () => {
    resetInactivityTimers();
    if (!answer.trim()) {
      setError('Please speak or type your answer before submitting.');
      return;
    }
    if (answer.trim().length < 5) {
      setError('Your answer seems too short. Please try to give a fuller response.');
      return;
    }
    setError('');
    setSubmitting(true);

    try {
      const data = await submitAnswer(sessionKey, answer.trim(), studentName);
      if (data.expired) { handleSessionExpired(); return; }
      setAnsweredQuestion(currentQuestion);
      setEvaluation(data.evaluation);
      setIsLastQuestion(!data.has_next);

      if (data.has_next) {
        // Store next question to show after feedback
        setCurrentQuestion(data.next_question);
      } else {
        setSummary(data.summary);
      }

      setView(VIEW.FEEDBACK);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleRequestHint = async () => {
    setHintLoading(true);
    try {
      const data = await requestHint(sessionKey, answer);
      setHint(data.hint);
      setHintUsed(true);
    } catch (err) {
      setHint('Sorry, could not generate a hint right now. Please try again.');
      setHintUsed(true);
    } finally {
      setHintLoading(false);
    }
  };

  const handleNext = () => {
    if (isLastQuestion) {
      setView(VIEW.SUMMARY);
    } else {
      setAnswer('');
      setHint('');
      setHintUsed(false);
      setEvaluation(null);
      setAnsweredQuestion(null);
      setView(VIEW.QUESTION);
    }
  };

  if (view === VIEW.SUMMARY && summary && sessionInfo) {
    return (
      <SummaryPage
        summary={summary}
        chapterName={sessionInfo.chapterName}
        subject={sessionInfo.subject}
        grade={sessionInfo.grade}
        board={sessionInfo.board}
      />
    );
  }

  if (view === VIEW.EXPIRED) {
    return (
      <div className="test-page error-page">
        <header className="site-header"><div className="header-inner"><Logo size="md" /></div></header>
        <main className="test-main">
          <div className="session-expired-card">
            <div className="expired-icon">⏰</div>
            <h2>Session Expired</h2>
            <p>Your test session expired after 30 minutes of inactivity. Your progress has been saved.</p>
            <p>Log in again to resume or start a new test.</p>
            <button className="btn btn-primary" onClick={() => navigate('/')}>
              Back to Home
            </button>
          </div>
        </main>
      </div>
    );
  }

  if (view === VIEW.ERROR) {
    return (
      <div className="test-page error-page">
        <header className="site-header">
          <div className="header-inner">
            <Logo size="md" />
          </div>
        </header>
        <main className="test-main">
          <div className="alert alert-error" style={{ marginTop: '2rem' }}>
            {error || 'Something went wrong. Please go back and start a new test.'}
          </div>
          <button className="btn btn-outline" onClick={() => navigate('/')} style={{ marginTop: '1rem' }}>
            Go Back Home
          </button>
        </main>
      </div>
    );
  }

  if (view === VIEW.LOADING) {
    return <LoadingOverlay message="Loading your test..." />;
  }

  return (
    <div className="test-page" onMouseMove={resetInactivityTimers} onKeyDown={resetInactivityTimers}>
      {submitting && <LoadingOverlay message="Evaluating your answer..." />}

      {showInactivityWarning && (
        <div className="inactivity-warning">
          Your session will expire in 5 minutes due to inactivity.
          <button className="btn-dismiss" onClick={resetInactivityTimers}>Keep going</button>
        </div>
      )}

      <header className="site-header">
        <div className="header-inner">
          <Logo size="md" />
          {sessionInfo && (
            <div className="test-context">
              {sessionInfo.board} · Grade {sessionInfo.grade} · {sessionInfo.subject}
            </div>
          )}
        </div>
      </header>

      <main className="test-main">
        {view === VIEW.QUESTION && currentQuestion && (
          <>
            <QuestionCard
              question={currentQuestion}
              currentNumber={currentQuestion.question_number}
              totalQuestions={totalQuestions}
              onRequestHint={handleRequestHint}
              hint={hint}
              hintLoading={hintLoading}
              hintUsed={hintUsed}
              lang={sessionInfo?.subject === 'Hindi' ? 'hi-IN' : 'en-IN'}
            />

            <div className="answer-section">
              <VoiceInput
                value={answer}
                onChange={setAnswer}
                disabled={submitting}
                lang={sessionInfo?.subject === 'Hindi' ? 'hi-IN' : 'en-IN'}
              />

              {error && <div className="alert alert-error">{error}</div>}

              <button
                className="btn btn-submit"
                onClick={handleSubmit}
                disabled={submitting || !answer.trim()}
              >
                Submit Answer
              </button>
            </div>
          </>
        )}

        {view === VIEW.FEEDBACK && evaluation && (
          <FeedbackCard
            evaluation={evaluation}
            question={answeredQuestion}
            onNext={handleNext}
            hasNext={!isLastQuestion}
            isLast={isLastQuestion}
          />
        )}
      </main>
    </div>
  );
}

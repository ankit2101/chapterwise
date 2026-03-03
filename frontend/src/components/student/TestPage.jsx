import { useState, useEffect } from 'react';
import { useParams, useLocation, useNavigate } from 'react-router-dom';
import { submitAnswer, getSession } from '../../api/studentApi';
import QuestionCard from './QuestionCard';
import VoiceInput from './VoiceInput';
import FeedbackCard from './FeedbackCard';
import SummaryPage from './SummaryPage';
import LoadingOverlay from '../shared/LoadingOverlay';

const VIEW = {
  LOADING: 'loading',
  QUESTION: 'question',
  FEEDBACK: 'feedback',
  SUMMARY: 'summary',
  ERROR: 'error',
};

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
  const [summary, setSummary] = useState(null);
  const [isLastQuestion, setIsLastQuestion] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [studentName, setStudentName] = useState('');

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

  const handleNext = () => {
    if (isLastQuestion) {
      setView(VIEW.SUMMARY);
    } else {
      setAnswer('');
      setEvaluation(null);
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

  if (view === VIEW.ERROR) {
    return (
      <div className="test-page error-page">
        <header className="site-header">
          <div className="header-inner">
            <div className="logo">
              <span className="logo-icon">CW</span>
              <span className="logo-text">ChapterWise</span>
            </div>
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
    <div className="test-page">
      {submitting && <LoadingOverlay message="Evaluating your answer..." />}

      <header className="site-header">
        <div className="header-inner">
          <div className="logo">
            <span className="logo-icon">CW</span>
            <span className="logo-text">ChapterWise</span>
          </div>
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
            />

            <div className="answer-section">
              <VoiceInput
                value={answer}
                onChange={setAnswer}
                disabled={submitting}
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
            onNext={handleNext}
            hasNext={!isLastQuestion}
            isLast={isLastQuestion}
          />
        )}
      </main>
    </div>
  );
}

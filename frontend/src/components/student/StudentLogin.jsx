import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useStudentAuth } from '../../context/StudentAuthContext';
import { studentLogin } from '../../api/studentApi';
import Logo from '../shared/Logo';

export default function StudentLogin() {
  const navigate = useNavigate();
  const { login } = useStudentAuth();

  const [name, setName] = useState('');
  const [pin, setPin] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [resumeData, setResumeData] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    const trimmedName = name.trim();
    const trimmedPin = pin.trim();
    if (!trimmedName) { setError('Please enter your name.'); return; }
    if (trimmedPin.length !== 4 || !/^\d{4}$/.test(trimmedPin)) {
      setError('PIN must be exactly 4 digits.');
      return;
    }

    setLoading(true);
    try {
      const data = await studentLogin(trimmedName, trimmedPin);
      login(data);

      if (data.active_session) {
        setResumeData(data.active_session);
      } else {
        navigate('/');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleResume = () => {
    navigate(`/test/${resumeData.session_key}`);
  };

  const handleStartNew = () => {
    navigate('/');
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-logo">
          <Logo size="lg" />
        </div>
        <h2 className="login-title">Student Login</h2>
        <p className="login-subtitle">Enter your name and PIN given by your teacher</p>

        {resumeData ? (
          <div className="resume-prompt">
            <div className="resume-icon">📚</div>
            <h3>Welcome back!</h3>
            <p>You have an unfinished test:</p>
            <div className="resume-details">
              <strong>{resumeData.chapter_name}</strong>
              <span>{resumeData.subject} · Grade {resumeData.grade}</span>
              <span className="resume-progress">
                Question {resumeData.current_question_index + 1} of {resumeData.total_questions}
              </span>
            </div>
            <div className="resume-actions">
              <button className="btn btn-primary" onClick={handleResume}>
                Resume Test
              </button>
              <button className="btn btn-outline" onClick={handleStartNew}>
                Start New Test
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="login-form">
            {error && <div className="alert alert-error">{error}</div>}

            <div className="form-group">
              <label htmlFor="student-name">Your Name</label>
              <input
                id="student-name"
                type="text"
                value={name}
                onChange={e => setName(e.target.value)}
                placeholder="e.g. Priya Sharma"
                autoComplete="name"
                autoFocus
              />
            </div>

            <div className="form-group">
              <label htmlFor="student-pin">4-Digit PIN</label>
              <input
                id="student-pin"
                type="password"
                inputMode="numeric"
                maxLength={4}
                value={pin}
                onChange={e => setPin(e.target.value.replace(/\D/g, '').slice(0, 4))}
                placeholder="••••"
                autoComplete="current-password"
              />
              <span className="form-hint">
                Your teacher sets up your account with a name and PIN.
              </span>
            </div>

            <button type="submit" className="btn btn-primary btn-full" disabled={loading}>
              {loading ? 'Signing in...' : 'Continue'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

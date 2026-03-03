import { useEffect } from 'react';
import useTextToSpeech from '../../hooks/useTextToSpeech';

export default function QuestionCard({ question, currentNumber, totalQuestions }) {
  const { speak, stop, isSpeaking, isSupported } = useTextToSpeech();

  // Auto-read question when it changes
  useEffect(() => {
    if (question?.question_text) {
      // Small delay to let the component render first
      const timer = setTimeout(() => {
        speak(`Question ${question.question_number}. ${question.question_text}`);
      }, 400);
      return () => clearTimeout(timer);
    }
  }, [question?.question_text]);

  // Stop speech on unmount
  useEffect(() => {
    return () => stop();
  }, []);

  if (!question) return null;

  const progress = ((currentNumber - 1) / totalQuestions) * 100;

  return (
    <div className="question-card">
      <div className="progress-bar-container">
        <div className="progress-bar" style={{ width: `${progress}%` }} />
      </div>

      <div className="question-meta">
        <span className="question-counter">
          Question {currentNumber} of {totalQuestions}
        </span>
        {question.topic_tag && (
          <span className="topic-badge">{question.topic_tag}</span>
        )}
      </div>

      <div className="question-text">
        {question.question_text}
      </div>

      {isSupported && (
        <button
          type="button"
          className={`btn-replay ${isSpeaking ? 'btn-replay-active' : ''}`}
          onClick={() => {
            if (isSpeaking) {
              stop();
            } else {
              speak(`Question ${question.question_number}. ${question.question_text}`);
            }
          }}
          title={isSpeaking ? 'Stop reading' : 'Read question aloud'}
        >
          {isSpeaking ? '⏸ Stop Reading' : '🔊 Read Aloud'}
        </button>
      )}
    </div>
  );
}

import { useEffect } from 'react';
import useSpeechRecognition from '../../hooks/useSpeechRecognition';

export default function VoiceInput({ value, onChange, disabled }) {
  const {
    isListening,
    error: speechError,
    isSupported,
    startListening,
    stopListening,
    transcript,
    setTranscript,
  } = useSpeechRecognition();

  // Sync transcript from speech recognition to the parent's value
  useEffect(() => {
    if (transcript !== value) {
      onChange(transcript);
    }
  }, [transcript]);

  const handleMicToggle = () => {
    if (isListening) {
      stopListening();
    } else {
      // Pass existing textarea content as base
      setTranscript(value);
      startListening(value);
    }
  };

  const handleTextChange = (e) => {
    setTranscript(e.target.value);
    onChange(e.target.value);
  };

  return (
    <div className="voice-input-container">
      <div className="voice-controls">
        {isSupported ? (
          <button
            type="button"
            className={`btn-mic ${isListening ? 'btn-mic-active' : ''}`}
            onClick={handleMicToggle}
            disabled={disabled}
            title={isListening ? 'Stop recording' : 'Start voice recording'}
          >
            <span className="mic-icon">{isListening ? '⏹' : '🎤'}</span>
            <span className="mic-label">
              {isListening ? 'Stop Recording' : 'Speak Answer'}
            </span>
            {isListening && <span className="pulse-ring" />}
          </button>
        ) : (
          <div className="mic-unsupported">
            Voice input requires Google Chrome. Please use Chrome or type your answer below.
          </div>
        )}

        {isListening && (
          <span className="listening-indicator">
            Listening... speak clearly
          </span>
        )}
      </div>

      {speechError && (
        <div className="speech-error">{speechError}</div>
      )}

      <div className="textarea-label">
        {isListening
          ? 'Your words will appear here as you speak:'
          : isSupported
          ? 'Your answer (edit if needed):'
          : 'Type your answer here:'}
      </div>

      <textarea
        className="answer-textarea"
        value={value}
        onChange={handleTextChange}
        placeholder={
          isSupported
            ? 'Wait for the question to finish reading, then click "Speak Answer" — or type your answer here...'
            : 'Type your answer here...'
        }
        rows={5}
        disabled={disabled}
      />
    </div>
  );
}

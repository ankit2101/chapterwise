import { useState, useRef, useCallback, useEffect } from 'react';

const SpeechRecognition =
  window.SpeechRecognition || window.webkitSpeechRecognition || null;

export default function useSpeechRecognition() {
  const [transcript, setTranscript] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [error, setError] = useState(null);
  const isSupported = Boolean(SpeechRecognition);

  const recognitionRef = useRef(null);
  const finalTranscriptRef = useRef('');
  const shouldRestartRef = useRef(false);

  const stopListening = useCallback(() => {
    shouldRestartRef.current = false;
    setIsListening(false);
    if (recognitionRef.current) {
      recognitionRef.current.stop();
    }
  }, []);

  const startListening = useCallback((existingText = '') => {
    if (!isSupported) {
      setError('Speech recognition is not supported in this browser. Please use Google Chrome.');
      return;
    }
    setError(null);
    finalTranscriptRef.current = existingText;

    const recognition = new SpeechRecognition();
    recognition.lang = 'en-IN';
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      setIsListening(true);
    };

    recognition.onresult = (event) => {
      let interimText = '';
      let newFinal = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const t = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          newFinal += t + ' ';
        } else {
          interimText += t;
        }
      }
      if (newFinal) {
        finalTranscriptRef.current += newFinal;
      }
      setTranscript(finalTranscriptRef.current + interimText);
    };

    recognition.onerror = (event) => {
      const messages = {
        'no-speech': 'No speech detected. Please try again.',
        'audio-capture': 'Microphone not accessible. Check browser permissions.',
        'not-allowed': 'Microphone permission was denied. Please allow microphone access in your browser settings.',
        'network': 'A network error occurred during speech recognition.',
      };
      setError(messages[event.error] || `Speech error: ${event.error}`);
      shouldRestartRef.current = false;
      setIsListening(false);
    };

    recognition.onend = () => {
      // Auto-restart if we should still be listening
      if (shouldRestartRef.current) {
        setTimeout(() => {
          if (shouldRestartRef.current && recognitionRef.current) {
            try {
              recognitionRef.current.start();
            } catch {
              setIsListening(false);
            }
          }
        }, 150);
      } else {
        setIsListening(false);
      }
    };

    recognitionRef.current = recognition;
    shouldRestartRef.current = true;
    recognition.start();
  }, [isSupported]);

  const resetTranscript = useCallback(() => {
    finalTranscriptRef.current = '';
    setTranscript('');
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      shouldRestartRef.current = false;
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
    };
  }, []);

  return {
    transcript,
    isListening,
    error,
    isSupported,
    startListening,
    stopListening,
    resetTranscript,
    setTranscript,
  };
}

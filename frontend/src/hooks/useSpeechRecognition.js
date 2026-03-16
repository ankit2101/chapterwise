import { useState, useRef, useCallback, useEffect } from 'react';

export default function useSpeechRecognition() {
  // Detect support inside the hook (not at module-load time) to avoid
  // silent null when the module is evaluated before the browser is ready.
  const SpeechRecognition =
    (typeof window !== 'undefined' &&
      (window.SpeechRecognition || window.webkitSpeechRecognition)) ||
    null;

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

  const startListening = useCallback((existingText = '', lang = 'en-IN') => {
    if (!isSupported) {
      setError('Speech recognition is not supported in this browser. Please use Google Chrome.');
      return;
    }

    // Prevent double-start if already listening or in 300 ms startup window
    if (shouldRestartRef.current) return;

    // Stop any TTS that may be playing — Chrome won't start the mic reliably
    // while speechSynthesis is active, and the mic would pick up the speaker.
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }

    setError(null);
    finalTranscriptRef.current = existingText;

    const recognition = new SpeechRecognition();
    recognition.lang = lang;
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
      // 'no-speech' fires after ~5-8 s of silence even with continuous=true.
      // Don't treat it as a fatal error — let onend fire and auto-restart.
      if (event.error === 'no-speech') {
        return;
      }

      const messages = {
        'audio-capture': 'Microphone not accessible. Check browser permissions.',
        'not-allowed':
          'Microphone permission was denied. Please allow microphone access in your browser settings.',
        'network': 'A network error occurred during speech recognition.',
      };
      setError(messages[event.error] || `Speech error: ${event.error}`);
      shouldRestartRef.current = false;
      setIsListening(false);
    };

    recognition.onend = () => {
      // Auto-restart if we should still be listening (handles both unexpected
      // stops and the silent no-speech case handled above).
      if (shouldRestartRef.current) {
        setTimeout(() => {
          if (shouldRestartRef.current && recognitionRef.current) {
            try {
              recognitionRef.current.start();
            } catch {
              setIsListening(false);
              shouldRestartRef.current = false;
            }
          }
        }, 150);
      } else {
        setIsListening(false);
      }
    };

    recognitionRef.current = recognition;
    shouldRestartRef.current = true;

    // Show listening state immediately so the button reflects "active" during
    // the 300 ms wait (also prevents accidental double-clicks).
    setIsListening(true);

    // Wait 300 ms after cancelling TTS before starting the mic so the
    // audio subsystem has time to fully release the output stream.
    setTimeout(() => {
      if (shouldRestartRef.current && recognitionRef.current) {
        try {
          recognitionRef.current.start();
        } catch {
          setIsListening(false);
          shouldRestartRef.current = false;
        }
      }
    }, 300);
  }, [isSupported, SpeechRecognition]);

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

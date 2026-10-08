import React, { useState } from 'react';
import { Mic, ArrowRight, Bot, Sparkles } from 'lucide-react';
import { I18N } from '../constants/languages';

export default function FloatingVoiceBar({ currentLang, onAskVoice, isAsking }) {
  const [query, setQuery] = useState('');

  const dict = (key) => (I18N[key] && I18N[key][currentLang]) || (I18N[key] && I18N[key].en) || '';

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!query.trim() || isAsking) return;
    onAskVoice(query);
    setQuery('');
  };

  const handleMicClick = () => {
    // If Web Speech recognition available
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      const recognition = new SpeechRecognition();
      recognition.lang = currentLang === 'en' ? 'en-IN' : `${currentLang}-IN`;
      recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        setQuery(transcript);
        onAskVoice(transcript);
      };
      recognition.start();
    } else {
      // Fallback sample prompt
      const sample = currentLang === 'hi' ? 'क्या मेरा बेटा छात्रवृत्ति के लिए आवेदन कर सकता है?' : 'can my son apply for scholarship?';
      setQuery(sample);
      onAskVoice(sample);
    }
  };

  return (
    <div style={{
      position: 'fixed',
      bottom: '24px',
      left: '50%',
      transform: 'translateX(-50%)',
      width: '90%',
      maxWidth: '680px',
      zIndex: 40,
    }}>
      <form
        onSubmit={handleSubmit}
        className="glass-panel"
        style={{
          background: 'rgba(15, 23, 42, 0.92)',
          backdropFilter: 'blur(20px)',
          border: '1px solid rgba(59, 130, 246, 0.3)',
          boxShadow: '0 12px 40px rgba(0, 0, 0, 0.5), 0 0 20px rgba(59, 130, 246, 0.2)',
          borderRadius: '9999px',
          padding: '6px 10px',
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
        }}
      >
        {/* Red Glowing Mic Button */}
        <button
          type="button"
          onClick={handleMicClick}
          style={{
            width: '44px',
            height: '44px',
            borderRadius: '50%',
            background: 'linear-gradient(135deg, #ef4444, #dc2626)',
            border: '1px solid rgba(255, 255, 255, 0.3)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            boxShadow: '0 0 16px rgba(239, 68, 68, 0.5)',
            flexShrink: 0,
            transition: 'all 0.2s',
          }}
        >
          <Mic size={20} color="#ffffff" />
        </button>

        {/* Input Text Box */}
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={dict('input_placeholder')}
          style={{
            flex: 1,
            background: 'transparent',
            border: 'none',
            outline: 'none',
            color: '#ffffff',
            fontSize: '14px',
            fontFamily: 'inherit',
            fontWeight: 500,
            padding: '4px 8px',
          }}
        />

        {/* AI Assistant Pill Tag */}
        <span style={{
          fontSize: '11px',
          fontWeight: 700,
          color: '#94a3b8',
          background: 'rgba(255, 255, 255, 0.06)',
          padding: '4px 10px',
          borderRadius: '9999px',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          whiteSpace: 'nowrap',
          display: 'flex',
          alignItems: 'center',
          gap: '4px',
        }}>
          <Sparkles size={11} color="#60a5fa" />
          {dict('ai_assistant')}
        </span>

        {/* Ask Submit Button */}
        <button
          type="submit"
          disabled={isAsking}
          style={{
            background: 'linear-gradient(135deg, #2563eb, #3b82f6)',
            border: 'none',
            borderRadius: '9999px',
            color: '#ffffff',
            fontWeight: 700,
            fontSize: '13px',
            padding: '10px 18px',
            cursor: isAsking ? 'not-allowed' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            boxShadow: '0 4px 14px rgba(37, 99, 235, 0.4)',
            whiteSpace: 'nowrap',
            transition: 'all 0.2s',
          }}
        >
          {isAsking ? 'Thinking...' : dict('btn_ask')}
        </button>
      </form>
    </div>
  );
}

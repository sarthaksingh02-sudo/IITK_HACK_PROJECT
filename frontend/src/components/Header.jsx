import React from 'react';
import { Landmark, Radio, Wifi, RefreshCw, Globe2 } from 'lucide-react';
import { SARVAM_LANGUAGES, I18N } from '../constants/languages';

export default function Header({ currentLang, onLangChange, onSync, isSyncing }) {
  const dict = (key) => (I18N[key] && I18N[key][currentLang]) || (I18N[key] && I18N[key].en) || '';

  return (
    <header style={{
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: '16px 28px',
      borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
      background: 'rgba(9, 13, 22, 0.85)',
      backdropFilter: 'blur(20px)',
      position: 'sticky',
      top: 0,
      zIndex: 50,
    }}>
      {/* Left: Brand Identity */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
        <div style={{
          width: '46px',
          height: '46px',
          borderRadius: '14px',
          background: 'linear-gradient(135deg, #1d4ed8, #3b82f6)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 0 24px rgba(59, 130, 246, 0.45)',
          border: '1px solid rgba(255, 255, 255, 0.2)',
        }}>
          <Landmark size={24} color="#ffffff" />
        </div>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <h1 style={{
              fontFamily: 'Outfit, sans-serif',
              fontSize: '22px',
              fontWeight: 800,
              color: '#ffffff',
              letterSpacing: '-0.4px',
            }}>
              AccessAI Village Hub
            </h1>
            <span style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '5px',
              padding: '2px 9px',
              borderRadius: '9999px',
              fontSize: '11px',
              fontWeight: 700,
              background: 'rgba(16, 185, 129, 0.16)',
              color: '#34d399',
              border: '1px solid rgba(16, 185, 129, 0.35)',
            }}>
              <span style={{
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                background: '#10b981',
                boxShadow: '0 0 8px #10b981',
                animation: 'pulseGlow 2s infinite',
              }}></span>
              Live
            </span>
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '1px' }}>
            {dict('sub_title')}
          </div>
        </div>
      </div>

      {/* Center: Tier 1 Broadcast Status Pill */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        padding: '6px 16px',
        borderRadius: '9999px',
        background: 'rgba(15, 23, 42, 0.8)',
        border: '1px solid rgba(59, 130, 246, 0.25)',
        boxShadow: '0 4px 16px rgba(0, 0, 0, 0.3)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Wifi size={16} color="#38bdf8" />
          <span style={{
            fontSize: '12px',
            fontWeight: 600,
            color: '#e2e8f0',
            letterSpacing: '0.2px',
          }}>
            {dict('tier_badge')}
          </span>
        </div>
        <button
          onClick={onSync}
          disabled={isSyncing}
          style={{
            background: 'rgba(56, 189, 248, 0.12)',
            border: '1px solid rgba(56, 189, 248, 0.35)',
            color: '#38bdf8',
            fontSize: '11px',
            fontWeight: 700,
            padding: '4px 12px',
            borderRadius: '9999px',
            cursor: isSyncing ? 'not-allowed' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            transition: 'all 0.2s',
          }}
        >
          <RefreshCw size={12} className={isSyncing ? 'animate-spin' : ''} />
          {dict('btn_radio_sync')}
        </button>
      </div>

      {/* Right Corner: Sarvam AI 9 Indian Languages + English Selector */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        background: 'rgba(30, 41, 59, 0.85)',
        border: '1px solid rgba(255, 255, 255, 0.18)',
        borderRadius: '14px',
        padding: '6px 12px',
        boxShadow: '0 4px 20px rgba(0, 0, 0, 0.25)',
      }}>
        <Globe2 size={16} color="#60a5fa" />
        <select
          value={currentLang}
          onChange={(e) => onLangChange(e.target.value)}
          style={{
            background: 'transparent',
            border: 'none',
            color: '#ffffff',
            fontWeight: 700,
            fontSize: '13px',
            cursor: 'pointer',
            outline: 'none',
            fontFamily: 'inherit',
          }}
        >
          {SARVAM_LANGUAGES.map((lang) => (
            <option
              key={lang.code}
              value={lang.code}
              style={{ background: '#0f172a', color: '#ffffff' }}
            >
              {lang.flag} {lang.native} ({lang.name})
            </option>
          ))}
        </select>
      </div>
    </header>
  );
}

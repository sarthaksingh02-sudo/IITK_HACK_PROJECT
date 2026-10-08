import React from 'react';
import { Users, Home, Award, BookOpen, UserCheck, ArrowRight } from 'lucide-react';

export default function FamilySection({ households, onSelectPersonForSuggestions }) {
  if (households.length === 0) {
    return (
      <div className="glass-panel" style={{ padding: '40px', textAlign: 'center', color: '#94a3b8' }}>
        No household records found.
      </div>
    );
  }

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <Users size={22} color="#f59e0b" />
        <h2 style={{ fontFamily: 'Outfit, sans-serif', fontSize: '20px', fontWeight: 800, color: '#ffffff' }}>
          Household Profiles & Eligibility Matrix
        </h2>
      </div>

      {households.map((hh) => (
        <div
          key={hh.id}
          className="glass-panel"
          style={{
            padding: '24px',
            borderLeft: '4px solid #3b82f6',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px',
          }}
        >
          {/* Household Header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Home size={18} color="#60a5fa" />
              <span style={{ fontFamily: 'Outfit', fontWeight: 800, fontSize: '17px', color: '#fff' }}>
                {hh.village}, {hh.district} ({hh.state})
              </span>
            </div>
            <div style={{ fontSize: '12px', color: '#94a3b8' }}>
              Members: <strong style={{ color: '#fff' }}>{hh.member_count}</strong> | Consent: <strong style={{ color: '#34d399' }}>✓ Granted</strong>
            </div>
          </div>

          {/* Members List */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {(hh.members || []).map((m) => (
              <div
                key={m.id}
                style={{
                  background: 'rgba(0, 0, 0, 0.3)',
                  border: '1px solid rgba(255, 255, 255, 0.06)',
                  borderRadius: '14px',
                  padding: '14px 18px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: '12px',
                }}
              >
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontWeight: 800, fontSize: '15px', color: '#ffffff' }}>
                      {m.name}
                    </span>
                    <span style={{ fontSize: '12px', color: '#94a3b8' }}>
                      ({m.relation || 'Member'})
                    </span>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontSize: '12px', color: '#94a3b8', flexWrap: 'wrap' }}>
                    <span>🎂 DOB: <strong style={{ color: '#e2e8f0' }}>{m.dob}</strong></span>
                    <span>🎓 <strong style={{ color: '#e2e8f0', textTransform: 'capitalize' }}>{m.education}</strong></span>
                    <span>🏷️ Category: <strong style={{ color: '#e2e8f0' }}>{m.category}</strong></span>
                    {m.occupation && <span>💼 {m.occupation}</span>}
                  </div>

                  {m.skills && m.skills.length > 0 && (
                    <div style={{ display: 'flex', gap: '6px', alignItems: 'center', marginTop: '4px', flexWrap: 'wrap' }}>
                      <span style={{ fontSize: '11px', color: '#60a5fa', fontWeight: 600 }}>🛠️ Skills:</span>
                      {m.skills.map((sk, i) => (
                        <span
                          key={i}
                          style={{
                            fontSize: '11px',
                            background: 'rgba(59, 130, 246, 0.15)',
                            color: '#93c5fd',
                            padding: '2px 8px',
                            borderRadius: '6px',
                            border: '1px solid rgba(59, 130, 246, 0.25)',
                          }}
                        >
                          {sk}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                <button
                  onClick={() => onSelectPersonForSuggestions(m.id)}
                  className="btn-secondary"
                  style={{
                    fontSize: '12px',
                    padding: '6px 14px',
                    borderRadius: '10px',
                    color: '#60a5fa',
                    borderColor: 'rgba(59, 130, 246, 0.3)',
                  }}
                >
                  View Suggestions <ArrowRight size={13} />
                </button>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

import React from 'react';
import { X, CheckCircle2, HelpCircle, XCircle, Users } from 'lucide-react';

export default function FamilyEligibilityModal({
  isOpen,
  onClose,
  opportunity,
  matchResults,
}) {
  if (!isOpen || !opportunity) return null;

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      background: 'rgba(0, 0, 0, 0.75)',
      backdropFilter: 'blur(8px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 100,
      padding: '20px',
    }}>
      <div className="glass-panel animate-fade-in" style={{
        width: '100%',
        maxWidth: '620px',
        maxHeight: '90vh',
        background: '#0d1322',
        border: '1px solid rgba(59, 130, 246, 0.3)',
        boxShadow: '0 20px 60px rgba(0, 0, 0, 0.6)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}>
        {/* Header */}
        <div style={{
          padding: '20px 24px',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#60a5fa', fontSize: '13px', fontWeight: 700 }}>
              <Users size={16} />
              Family Eligibility Matrix
            </div>
            <h3 style={{ fontFamily: 'Outfit', fontSize: '18px', fontWeight: 800, color: '#ffffff', marginTop: '2px' }}>
              {opportunity.title}
            </h3>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'rgba(255, 255, 255, 0.08)',
              border: 'none',
              borderRadius: '8px',
              color: '#94a3b8',
              padding: '6px',
              cursor: 'pointer',
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Member Results List */}
        <div style={{
          padding: '24px',
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: '12px',
        }}>
          {(!matchResults || matchResults.length === 0) ? (
            <div style={{ textAlign: 'center', color: '#94a3b8', padding: '20px' }}>
              Evaluating family members against eligibility criteria...
            </div>
          ) : (
            matchResults.map((m, idx) => {
              const isElig = m.status === 'ELIGIBLE';
              const isPoss = m.status === 'POSSIBLE';
              const statusColor = isElig ? '#10b981' : (isPoss ? '#f59e0b' : '#ef4444');

              return (
                <div
                  key={idx}
                  style={{
                    background: 'rgba(15, 23, 42, 0.8)',
                    border: `1px solid ${statusColor}44`,
                    borderRadius: '12px',
                    padding: '14px 18px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '6px',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontWeight: 800, fontSize: '15px', color: '#ffffff' }}>
                      👤 {m.person_name}
                    </span>
                    <span style={{
                      padding: '3px 10px',
                      borderRadius: '9999px',
                      fontSize: '11px',
                      fontWeight: 800,
                      background: `${statusColor}22`,
                      color: statusColor,
                      border: `1px solid ${statusColor}55`,
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                    }}>
                      {isElig && <CheckCircle2 size={12} />}
                      {isPoss && <HelpCircle size={12} />}
                      {!isElig && !isPoss && <XCircle size={12} />}
                      {m.status}
                    </span>
                  </div>

                  <div style={{ fontSize: '13px', color: isElig ? '#34d399' : (isPoss ? '#fcd34d' : '#fca5a5') }}>
                    {m.reasons && m.reasons.length > 0
                      ? m.reasons.join(', ')
                      : (m.question || 'Meets all deterministic criteria.')}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div style={{
          padding: '14px 24px',
          borderTop: '1px solid rgba(255, 255, 255, 0.08)',
          display: 'flex',
          justifyContent: 'flex-end',
          background: 'rgba(11, 15, 25, 0.6)',
        }}>
          <button onClick={onClose} className="btn-secondary" style={{ fontSize: '13px', padding: '6px 16px' }}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

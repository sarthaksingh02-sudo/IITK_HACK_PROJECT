import React from 'react';
import { Stethoscope, AlertTriangle, ShieldCheck, HeartPulse, Hospital } from 'lucide-react';

export default function HealthSection({
  healthData,
  households,
  selectedPersonId,
  onSelectPerson,
}) {
  const allMembers = households.flatMap((h) => h.members || []);

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Header & Person Selector */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Stethoscope size={22} color="#06b6d4" />
          <h2 style={{ fontFamily: 'Outfit, sans-serif', fontSize: '20px', fontWeight: 800, color: '#ffffff' }}>
            Family Health & Immunization Guidance
          </h2>
        </div>

        {allMembers.length > 0 && (
          <select
            value={selectedPersonId || ''}
            onChange={(e) => onSelectPerson(e.target.value)}
            style={{
              background: 'rgba(30, 41, 59, 0.85)',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              color: '#ffffff',
              padding: '8px 14px',
              borderRadius: '12px',
              fontSize: '13px',
              fontWeight: 600,
              cursor: 'pointer',
              outline: 'none',
            }}
          >
            {allMembers.map((m) => (
              <option key={m.id} value={m.id} style={{ background: '#0f172a' }}>
                👤 {m.name} ({m.relation || 'Member'})
              </option>
            ))}
          </select>
        )}
      </div>

      {/* Mandatory Non-Diagnostic Referral Disclaimer */}
      <div style={{
        background: 'rgba(239, 68, 68, 0.1)',
        border: '1px solid rgba(239, 68, 68, 0.3)',
        padding: '14px 18px',
        borderRadius: '14px',
        display: 'flex',
        alignItems: 'flex-start',
        gap: '12px',
        fontSize: '13px',
        color: '#fecaca',
        lineHeight: 1.5,
      }}>
        <AlertTriangle size={20} color="#ef4444" style={{ flexShrink: 0, marginTop: '2px' }} />
        <div>
          <strong>Important Medical Disclaimer:</strong> This module provides general scheduling reminders and community referral guidance. It does <em>not</em> provide medical diagnoses. Always consult your nearest ASHA worker, ANM, or Primary Health Centre (PHC).
        </div>
      </div>

      {/* Health Content */}
      {!healthData ? (
        <div className="glass-panel" style={{ padding: '36px', textAlign: 'center', color: '#94a3b8' }}>
          Select a family member above to view immunization schedule and health alerts.
        </div>
      ) : (
        <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <h3 style={{ fontFamily: 'Outfit', fontSize: '18px', fontWeight: 800, color: '#fff' }}>
                👶 {healthData.name}
              </h3>
              <div style={{ fontSize: '12px', color: '#94a3b8', marginTop: '2px' }}>
                Age: <strong style={{ color: '#e2e8f0' }}>{healthData.age_years} yrs {healthData.age_months % 12} mos</strong>
              </div>
            </div>
            <span style={{ fontSize: '11px', color: '#64748b' }}>
              Source: {healthData.source}
            </span>
          </div>

          {/* NIS Universal Immunization Schedule */}
          {healthData.immunizations && healthData.immunizations.length > 0 && (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '15px', fontWeight: 700, color: '#38bdf8', marginBottom: '12px' }}>
                <ShieldCheck size={18} />
                Universal Immunization Schedule (NIS):
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {healthData.immunizations.map((imm, idx) => {
                  const badgeColor = imm.status === 'due_now' ? '#f59e0b' : (imm.status === 'upcoming' ? '#10b981' : '#64748b');
                  return (
                    <div
                      key={idx}
                      style={{
                        background: 'rgba(0, 0, 0, 0.3)',
                        border: '1px solid rgba(255, 255, 255, 0.06)',
                        borderRadius: '12px',
                        padding: '12px 16px',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                      }}
                    >
                      <div>
                        <div style={{ fontWeight: 700, fontSize: '14px', color: '#ffffff' }}>
                          {imm.vaccine}
                        </div>
                        <div style={{ fontSize: '12px', color: '#94a3b8', marginTop: '2px' }}>
                          {imm.notes}
                        </div>
                      </div>
                      <span style={{
                        padding: '4px 10px',
                        borderRadius: '9999px',
                        fontSize: '11px',
                        fontWeight: 800,
                        background: `${badgeColor}22`,
                        color: badgeColor,
                        border: `1px solid ${badgeColor}55`,
                      }}>
                        {imm.status === 'due_now' ? 'DUE NOW' : (imm.status === 'upcoming' ? 'UPCOMING' : 'COMPLETED')}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* NHM Danger Signs & Community Referral */}
          {healthData.relevant_red_flags && healthData.relevant_red_flags.length > 0 && (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '15px', fontWeight: 700, color: '#f87171', marginBottom: '12px' }}>
                <HeartPulse size={18} />
                Danger Signs & Referral Protocols (NHM):
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {healthData.relevant_red_flags.map((rf, idx) => (
                  <div
                    key={idx}
                    style={{
                      background: 'rgba(239, 68, 68, 0.08)',
                      border: '1px solid rgba(239, 68, 68, 0.25)',
                      borderRadius: '12px',
                      padding: '12px 16px',
                    }}
                  >
                    <div style={{ fontWeight: 800, fontSize: '14px', color: '#fca5a5' }}>
                      ⚠️ {rf.symptom}
                    </div>
                    <div style={{ fontSize: '13px', color: '#ffffff', marginTop: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <Hospital size={14} color="#ef4444" />
                      <strong>Action:</strong> {rf.action}
                    </div>
                    <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '4px' }}>
                      Reference: {rf.source_ref}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

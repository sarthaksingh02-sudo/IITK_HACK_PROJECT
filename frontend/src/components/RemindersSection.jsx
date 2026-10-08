import React from 'react';
import { Clock, FastForward, Bell, AlertCircle, Calendar } from 'lucide-react';

export default function RemindersSection({
  reminders,
  fastForwardDays,
  onFastForwardChange,
}) {
  const options = [0, 10, 30, 60];

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <Clock size={22} color="#a855f7" />
        <h2 style={{ fontFamily: 'Outfit, sans-serif', fontSize: '20px', fontWeight: 800, color: '#ffffff' }}>
          Reminders, Stage Alerts & Time Travel Simulator
        </h2>
      </div>

      {/* Fast-Forward Simulation Panel */}
      <div
        className="glass-panel"
        style={{
          padding: '20px 24px',
          background: 'rgba(245, 158, 11, 0.06)',
          border: '1px solid rgba(245, 158, 11, 0.3)',
          display: 'flex',
          flexDirection: 'column',
          gap: '14px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 800, fontSize: '15px', color: '#fbbf24' }}>
            <FastForward size={18} />
            Fast-Forward Time Machine:
          </div>
          <span style={{
            fontSize: '14px',
            fontWeight: 800,
            color: '#fbbf24',
            background: 'rgba(245, 158, 11, 0.2)',
            padding: '4px 12px',
            borderRadius: '9999px',
          }}>
            +{fastForwardDays} Days Forward
          </span>
        </div>

        <p style={{ fontSize: '12px', color: '#94a3b8' }}>
          Simulate advancing calendar days into the future to test deadline countdown triggers, document preparation lead times, and stage alerts:
        </p>

        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          {options.map((days) => (
            <button
              key={days}
              onClick={() => onFastForwardChange(days)}
              style={{
                padding: '8px 18px',
                borderRadius: '12px',
                fontSize: '13px',
                fontWeight: 700,
                cursor: 'pointer',
                border: fastForwardDays === days
                  ? '1px solid #f59e0b'
                  : '1px solid rgba(255, 255, 255, 0.1)',
                background: fastForwardDays === days
                  ? 'rgba(245, 158, 11, 0.25)'
                  : 'rgba(15, 23, 42, 0.7)',
                color: fastForwardDays === days ? '#fbbf24' : '#e2e8f0',
                transition: 'all 0.2s',
              }}
            >
              {days === 0 ? 'Today (0 days)' : `+${days} Days Ahead`}
            </button>
          ))}
        </div>
      </div>

      {/* Reminders List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
        {(!reminders || reminders.length === 0) ? (
          <div className="glass-panel" style={{ padding: '36px', textAlign: 'center', color: '#94a3b8' }}>
            No active reminders or deadlines for this date.
          </div>
        ) : (
          reminders.map((r, idx) => (
            <div
              key={idx}
              className="glass-panel"
              style={{
                padding: '18px 22px',
                borderLeft: '4px solid #f59e0b',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontWeight: 800, fontSize: '15px', color: '#fbbf24', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Bell size={16} />
                  {r.person_name}
                </span>
                <span style={{
                  padding: '3px 10px',
                  borderRadius: '9999px',
                  fontSize: '11px',
                  fontWeight: 800,
                  background: 'rgba(245, 158, 11, 0.18)',
                  color: '#fbbf24',
                  textTransform: 'uppercase',
                }}>
                  {r.kind || 'DEADLINE'}
                </span>
              </div>

              <div style={{ fontSize: '14px', color: '#ffffff', fontWeight: 600 }}>
                {r.message}
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '12px', color: '#94a3b8', marginTop: '4px' }}>
                <span>Opportunity: <strong style={{ color: '#e2e8f0' }}>{r.opportunity_title}</strong></span>
                <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <Calendar size={13} />
                  Due: <strong style={{ color: '#fbbf24' }}>{r.due_at}</strong>
                </span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

import React from 'react';
import { Target, Lightbulb, Rocket, ExternalLink, Info } from 'lucide-react';
import { I18N } from '../constants/languages';

export default function SuggestionsSection({
  suggestions,
  households,
  selectedPersonId,
  onSelectPerson,
  currentLang,
}) {
  const dict = (key) => (I18N[key] && I18N[key][currentLang]) || (I18N[key] && I18N[key].en) || '';

  const allMembers = households.flatMap((h) => h.members || []);

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
      {/* Header & Person Selector */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: '12px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Target size={22} color="#f43f5e" />
          <h2 style={{
            fontFamily: 'Outfit, sans-serif',
            fontSize: '20px',
            fontWeight: 800,
            color: '#ffffff',
          }}>
            {dict('hdr_sugg') || 'Personalized Suggestions (Feature K)'}
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

      {/* Suggested, Not Guaranteed Disclaimer */}
      <div style={{
        background: 'rgba(59, 130, 246, 0.12)',
        border: '1px solid rgba(59, 130, 246, 0.3)',
        padding: '12px 16px',
        borderRadius: '14px',
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        fontSize: '13px',
        color: '#93c5fd',
      }}>
        <Info size={18} color="#60a5fa" style={{ flexShrink: 0 }} />
        <span>
          <strong>Suggested, not guaranteed</strong>: Recommendations are deterministically ranked based on profile skills and education rules.
        </span>
      </div>

      {/* Suggestions Cards List */}
      {suggestions.length === 0 ? (
        <div className="glass-panel" style={{ padding: '36px', textAlign: 'center', color: '#94a3b8' }}>
          No suggestions available for this person.
        </div>
      ) : (
        suggestions.map((s, idx) => {
          const statusColor = s.status === 'ELIGIBLE' ? '#10b981' : (s.status === 'POSSIBLE' ? '#f59e0b' : '#ef4444');
          const title = s.title_localized || (currentLang === 'hi' && s.title_hi ? s.title_hi : s.title);
          const whyFit = s.why_fit_localized || (currentLang === 'hi' ? s.why_fit_hi : s.why_fit);

          return (
            <div
              key={idx}
              className="glass-panel"
              style={{
                padding: '22px 24px',
                borderLeft: `4px solid ${statusColor}`,
                display: 'flex',
                flexDirection: 'column',
                gap: '14px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <h3 style={{ fontFamily: 'Outfit', fontSize: '18px', fontWeight: 800, color: '#fff' }}>
                    {title}
                  </h3>
                  <div style={{ fontSize: '12px', color: '#94a3b8', marginTop: '4px' }}>
                    {s.org ? `${s.org} • ` : ''}
                    <span style={{ textTransform: 'uppercase', color: '#60a5fa', fontWeight: 700 }}>
                      {s.type || 'SCHEME'}
                    </span>
                  </div>
                </div>

                <span style={{
                  padding: '4px 12px',
                  borderRadius: '9999px',
                  fontSize: '11px',
                  fontWeight: 800,
                  background: `${statusColor}22`,
                  color: statusColor,
                  border: `1px solid ${statusColor}55`,
                }}>
                  {s.status === 'ELIGIBLE' ? '✓ ELIGIBLE' : (s.status === 'POSSIBLE' ? '? POSSIBLE' : '✗ NOT ELIGIBLE')}
                </span>
              </div>

              {/* Why This Fits Box */}
              <div style={{
                background: 'rgba(59, 130, 246, 0.08)',
                borderLeft: '3px solid #3b82f6',
                padding: '10px 14px',
                borderRadius: '0 10px 10px 0',
                fontSize: '13px',
                color: '#e2e8f0',
                lineHeight: 1.5,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 700, color: '#60a5fa', marginBottom: '2px' }}>
                  <Lightbulb size={14} />
                  Why this fits you:
                </div>
                {whyFit}
              </div>

              {/* Pathway Step if Not Eligible */}
              {s.pathway_step && (
                <div style={{
                  background: 'rgba(245, 158, 11, 0.08)',
                  borderLeft: '3px solid #f59e0b',
                  padding: '10px 14px',
                  borderRadius: '0 10px 10px 0',
                  fontSize: '13px',
                  color: '#fef3c7',
                  lineHeight: 1.5,
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 700, color: '#fbbf24', marginBottom: '2px' }}>
                    <Rocket size={14} />
                    How to become eligible:
                  </div>
                  <div>{s.pathway_step.action_required}</div>
                  {s.pathway_step.source_url && (
                    <a
                      href={s.pathway_step.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ color: '#fbbf24', textDecoration: 'none', fontWeight: 700, fontSize: '12px', display: 'inline-block', marginTop: '4px' }}
                    >
                      🔗 {s.pathway_step.step_title} (View Details)
                    </a>
                  )}
                </div>
              )}

              {/* Bottom Citations */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '12px', color: '#64748b' }}>
                <span>🎯 Fit Score: <strong style={{ color: '#93c5fd' }}>{Math.round(s.fit_score * 100)}%</strong></span>
                {s.source_url && (
                  <a
                    href={s.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ color: '#38bdf8', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '4px' }}
                  >
                    <ExternalLink size={12} />
                    Official Notice
                  </a>
                )}
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}

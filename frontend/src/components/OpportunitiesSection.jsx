import React, { useState } from 'react';
import { Calendar, DollarSign, ExternalLink, Users, FileText, CheckCircle2 } from 'lucide-react';
import { I18N } from '../constants/languages';

export default function OpportunitiesSection({
  opportunities,
  currentLang,
  onCheckFamilyEligibility,
}) {
  const [filterType, setFilterType] = useState('all');

  const dict = (key) => (I18N[key] && I18N[key][currentLang]) || (I18N[key] && I18N[key].en) || '';

  const filterOptions = [
    { id: 'all', label: dict('filter_all') },
    { id: 'job', label: dict('filter_jobs') },
    { id: 'training', label: dict('filter_trainings') },
    { id: 'scheme', label: dict('filter_schemes') },
  ];

  const filteredOpps = opportunities.filter((o) => {
    if (filterType === 'all') return true;
    return (o.type || '').toLowerCase() === filterType;
  });

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
      {/* Top Header & Filter Row */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: '12px',
        marginBottom: '6px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <h2 style={{
            fontFamily: 'Outfit, sans-serif',
            fontSize: '20px',
            fontWeight: 800,
            color: '#ffffff',
            letterSpacing: '-0.3px',
          }}>
            {dict('hdr_opps')}
          </h2>
          <span style={{
            padding: '4px 12px',
            borderRadius: '9999px',
            fontSize: '11px',
            fontWeight: 700,
            background: 'rgba(59, 130, 246, 0.18)',
            color: '#60a5fa',
            border: '1px solid rgba(59, 130, 246, 0.35)',
          }}>
            {dict('badge_new_avail')}
          </span>
        </div>

        {/* Filter Pills */}
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {filterOptions.map((opt) => (
            <button
              key={opt.id}
              onClick={() => setFilterType(opt.id)}
              style={{
                padding: '6px 14px',
                borderRadius: '12px',
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer',
                border: filterType === opt.id
                  ? '1px solid #3b82f6'
                  : '1px solid rgba(255, 255, 255, 0.1)',
                background: filterType === opt.id
                  ? 'rgba(59, 130, 246, 0.25)'
                  : 'rgba(15, 23, 42, 0.7)',
                color: filterType === opt.id ? '#ffffff' : '#94a3b8',
                transition: 'all 0.2s',
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Opportunities List Cards */}
      {filteredOpps.length === 0 ? (
        <div className="glass-panel" style={{ padding: '36px', textAlign: 'center', color: '#94a3b8' }}>
          No opportunities available for this filter.
        </div>
      ) : (
        filteredOpps.map((opp) => {
          const title = opp.title_localized || (currentLang === 'hi' && opp.title_hi ? opp.title_hi : opp.title);
          const lastDate = opp.dates?.last_date || '2026-12-31';
          const fee = opp.fee !== undefined ? `₹${opp.fee}` : '₹0';
          const docs = opp.documents_required || [];

          return (
            <div
              key={opp.id}
              className="glass-panel"
              style={{
                padding: '22px 24px',
                display: 'flex',
                flexDirection: 'column',
                gap: '14px',
                background: 'rgba(15, 23, 42, 0.75)',
                border: '1px solid rgba(255, 255, 255, 0.09)',
              }}
            >
              {/* Card Header */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '16px' }}>
                <div>
                  <h3 style={{
                    fontFamily: 'Outfit, sans-serif',
                    fontSize: '18px',
                    fontWeight: 800,
                    color: '#ffffff',
                    lineHeight: 1.3,
                  }}>
                    {title}
                  </h3>
                  <div style={{
                    fontSize: '12px',
                    color: '#94a3b8',
                    marginTop: '4px',
                    fontWeight: 500,
                  }}>
                    {opp.org ? `${opp.org} • ` : ''}
                    <span style={{ textTransform: 'uppercase', color: '#60a5fa', fontWeight: 700 }}>
                      {opp.type || 'SCHEME'}
                    </span>
                  </div>
                </div>

                <span style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                  padding: '4px 10px',
                  borderRadius: '9999px',
                  fontSize: '11px',
                  fontWeight: 800,
                  background: 'rgba(16, 185, 129, 0.18)',
                  color: '#34d399',
                  border: '1px solid rgba(16, 185, 129, 0.35)',
                  whiteSpace: 'nowrap',
                }}>
                  <CheckCircle2 size={12} />
                  {dict('badge_active')}
                </span>
              </div>

              {/* Metadata Row & Actions */}
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: '12px',
                paddingTop: '8px',
                borderTop: '1px solid rgba(255, 255, 255, 0.05)',
              }}>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '20px',
                  fontSize: '13px',
                  color: '#94a3b8',
                  flexWrap: 'wrap',
                }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Calendar size={14} color="#64748b" />
                    {dict('lbl_last_date')}: <strong style={{ color: '#e2e8f0' }}>{lastDate}</strong>
                  </span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <DollarSign size={14} color="#64748b" />
                    {dict('lbl_fee')}: <strong style={{ color: '#e2e8f0' }}>{fee}</strong>
                  </span>
                  {opp.source_url && (
                    <a
                      href={opp.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px',
                        color: '#38bdf8',
                        textDecoration: 'none',
                        fontSize: '12px',
                        fontWeight: 600,
                      }}
                    >
                      <ExternalLink size={13} />
                      {dict('lbl_source')}
                    </a>
                  )}
                </div>

                <button
                  onClick={() => onCheckFamilyEligibility(opp)}
                  className="btn-primary"
                  style={{
                    padding: '8px 18px',
                    borderRadius: '12px',
                    fontSize: '13px',
                    fontWeight: 700,
                    background: 'linear-gradient(135deg, #2563eb, #3b82f6)',
                    boxShadow: '0 4px 14px rgba(37, 99, 235, 0.4)',
                  }}
                >
                  <Users size={15} />
                  {dict('btn_check_family')}
                </button>
              </div>

              {/* Documents lead-time banner if any */}
              {docs.length > 0 && (
                <div style={{
                  fontSize: '12px',
                  color: '#94a3b8',
                  background: 'rgba(0, 0, 0, 0.25)',
                  padding: '8px 12px',
                  borderRadius: '10px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                }}>
                  <FileText size={14} color="#60a5fa" />
                  <span>
                    <strong>Required Documents:</strong>{' '}
                    {docs.map((d) => `${d.name_hi || d.name} (${d.typical_lead_time_days || 0} days lead)`).join(', ')}
                  </span>
                </div>
              )}
            </div>
          );
        })
      )}
    </div>
  );
}

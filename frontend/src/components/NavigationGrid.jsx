import React from 'react';
import { Megaphone, Target, Users, Stethoscope, Clock, Building2 } from 'lucide-react';
import { I18N } from '../constants/languages';

export default function NavigationGrid({ activeTab, onSelectTab, currentLang }) {
  const dict = (key) => (I18N[key] && I18N[key][currentLang]) || (I18N[key] && I18N[key].en) || '';

  const navItems = [
    {
      id: 'opportunities',
      icon: Megaphone,
      label: dict('tab_opps'),
      sub: dict('tab_opps_sub'),
      color: '#ec4899',
      bgGlow: 'rgba(236, 72, 153, 0.15)',
    },
    {
      id: 'suggestions',
      icon: Target,
      label: dict('tab_sugg'),
      sub: dict('tab_sugg_sub'),
      color: '#f43f5e',
      bgGlow: 'rgba(244, 63, 94, 0.15)',
    },
    {
      id: 'family',
      icon: Users,
      label: dict('tab_fam'),
      sub: dict('tab_fam_sub'),
      color: '#f59e0b',
      bgGlow: 'rgba(245, 158, 11, 0.15)',
    },
    {
      id: 'health',
      icon: Stethoscope,
      label: dict('tab_health'),
      sub: dict('tab_health_sub'),
      color: '#06b6d4',
      bgGlow: 'rgba(6, 182, 212, 0.15)',
    },
    {
      id: 'reminders',
      icon: Clock,
      label: dict('tab_rem'),
      sub: dict('tab_rem_sub'),
      color: '#a855f7',
      bgGlow: 'rgba(168, 85, 247, 0.15)',
    },
    {
      id: 'dashboard',
      icon: Building2,
      label: dict('tab_dash'),
      sub: dict('tab_dash_sub'),
      color: '#3b82f6',
      bgGlow: 'rgba(59, 130, 246, 0.15)',
    },
  ];

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(6, 1fr)',
      gap: '14px',
      margin: '24px 0 28px 0',
    }}>
      {navItems.map((item) => {
        const IconComponent = item.icon;
        const isActive = activeTab === item.id;

        return (
          <button
            key={item.id}
            onClick={() => onSelectTab(item.id)}
            style={{
              background: isActive
                ? `linear-gradient(180deg, ${item.bgGlow} 0%, rgba(15, 23, 42, 0.85) 100%)`
                : 'rgba(15, 23, 42, 0.6)',
              backdropFilter: 'blur(16px)',
              border: isActive
                ? `2px solid ${item.color}`
                : '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '20px',
              padding: '20px 14px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              textAlign: 'center',
              cursor: 'pointer',
              transition: 'all 0.25s cubic-bezier(0.16, 1, 0.3, 1)',
              transform: isActive ? 'translateY(-2px)' : 'none',
              boxShadow: isActive
                ? `0 8px 24px ${item.bgGlow}`
                : '0 4px 16px rgba(0, 0, 0, 0.2)',
            }}
          >
            <div style={{
              width: '44px',
              height: '44px',
              borderRadius: '12px',
              background: isActive ? item.bgGlow : 'rgba(255, 255, 255, 0.04)',
              border: `1px solid ${isActive ? item.color : 'rgba(255, 255, 255, 0.08)'}`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: '10px',
              transition: 'all 0.2s',
            }}>
              <IconComponent size={22} color={item.color} />
            </div>

            <div style={{
              fontFamily: 'Outfit, sans-serif',
              fontSize: '14px',
              fontWeight: 700,
              color: isActive ? '#ffffff' : '#e2e8f0',
              lineHeight: 1.2,
            }}>
              {item.label}
            </div>

            <div style={{
              fontSize: '11px',
              color: isActive ? '#94a3b8' : '#64748b',
              marginTop: '4px',
              fontWeight: 500,
            }}>
              {item.sub}
            </div>
          </button>
        );
      })}
    </div>
  );
}

import React from 'react';
import { Building2, Megaphone, Users, UserCheck, ShieldCheck, Radio } from 'lucide-react';

export default function VillageDashboard({ stats, ledger }) {
  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '22px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <Building2 size={22} color="#3b82f6" />
        <h2 style={{ fontFamily: 'Outfit, sans-serif', fontSize: '20px', fontWeight: 800, color: '#ffffff' }}>
          Village Hub Operational Dashboard & Broadcast Ledger
        </h2>
      </div>

      {/* Metrics Stat Cards */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: '16px',
      }}>
        <div className="glass-panel" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: '#94a3b8', fontSize: '13px' }}>
            <span>Active Opportunities</span>
            <Megaphone size={18} color="#ec4899" />
          </div>
          <div style={{ fontFamily: 'Outfit', fontSize: '32px', fontWeight: 900, color: '#ffffff' }}>
            {stats?.active_opportunities ?? 0}
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: '#94a3b8', fontSize: '13px' }}>
            <span>Households Registered</span>
            <Users size={18} color="#f59e0b" />
          </div>
          <div style={{ fontFamily: 'Outfit', fontSize: '32px', fontWeight: 900, color: '#ffffff' }}>
            {stats?.registered_households ?? 0}
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: '#94a3b8', fontSize: '13px' }}>
            <span>Village Residents</span>
            <UserCheck size={18} color="#06b6d4" />
          </div>
          <div style={{ fontFamily: 'Outfit', fontSize: '32px', fontWeight: 900, color: '#ffffff' }}>
            {stats?.village_residents ?? 0}
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: '#94a3b8', fontSize: '13px' }}>
            <span>Verified Radio Packets</span>
            <ShieldCheck size={18} color="#10b981" />
          </div>
          <div style={{ fontFamily: 'Outfit', fontSize: '32px', fontWeight: 900, color: '#34d399' }}>
            {stats?.verified_broadcast_packets ?? 0}
          </div>
        </div>
      </div>

      {/* Broadcast Carousel Security Ledger */}
      <div className="glass-panel" style={{ padding: '22px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '16px', fontWeight: 800, color: '#e2e8f0' }}>
          <Radio size={18} color="#38bdf8" />
          Offline Radio Broadcast Carousel & Cryptographic Integrity
        </div>
        <p style={{ fontSize: '13px', color: '#94a3b8', lineHeight: 1.5 }}>
          The Village Hub works 100% offline. Broadcast packets are digitally signed using Ed25519 private keys at Tier 0 (Cloud Station) and verified offline at Tier 1 before updating the village database.
        </p>

        {ledger && ledger.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '6px' }}>
            {ledger.map((pkt, i) => (
              <div
                key={i}
                style={{
                  background: 'rgba(0, 0, 0, 0.3)',
                  border: '1px solid rgba(255, 255, 255, 0.06)',
                  borderRadius: '10px',
                  padding: '10px 14px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  fontSize: '12px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ color: '#34d399', fontWeight: 800 }}>✓ VERIFIED</span>
                  <span style={{ color: '#e2e8f0', fontFamily: 'monospace' }}>{pkt.packet_id}</span>
                </div>
                <span style={{ color: '#94a3b8' }}>Topic: {pkt.topic}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

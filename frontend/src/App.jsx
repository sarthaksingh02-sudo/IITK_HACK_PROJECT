import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import NavigationGrid from './components/NavigationGrid';
import OpportunitiesSection from './components/OpportunitiesSection';
import SuggestionsSection from './components/SuggestionsSection';
import FamilySection from './components/FamilySection';
import HealthSection from './components/HealthSection';
import RemindersSection from './components/RemindersSection';
import VillageDashboard from './components/VillageDashboard';
import FamilyEligibilityModal from './components/FamilyEligibilityModal';
import FloatingVoiceBar from './components/FloatingVoiceBar';

export default function App() {
  const [currentLang, setCurrentLang] = useState('hi');
  const [activeTab, setActiveTab] = useState('opportunities');
  const [isSyncing, setIsSyncing] = useState(false);
  const [isAsking, setIsAsking] = useState(false);

  // Data states
  const [opportunities, setOpportunities] = useState([]);
  const [households, setHouseholds] = useState([]);
  const [selectedPersonId, setSelectedPersonId] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [healthData, setHealthData] = useState(null);
  const [fastForwardDays, setFastForwardDays] = useState(0);
  const [reminders, setReminders] = useState([]);
  const [stats, setStats] = useState(null);

  // Modal states
  const [selectedOppForModal, setSelectedOppForModal] = useState(null);
  const [modalMatchResults, setModalMatchResults] = useState([]);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Load Opportunities
  const fetchOpportunities = async (lang = currentLang) => {
    try {
      const res = await fetch(`/api/opportunities?lang=${lang}`);
      if (res.ok) {
        const data = await res.json();
        setOpportunities(data.items || []);
      }
    } catch (err) {
      console.error('Failed to load opportunities:', err);
    }
  };

  // Load Households & set initial selected person
  const fetchHouseholds = async () => {
    try {
      const res = await fetch('/api/households');
      if (res.ok) {
        const data = await res.json();
        const items = data.items || [];
        setHouseholds(items);
        if (items.length > 0 && items[0].members?.length > 0 && !selectedPersonId) {
          const firstPersonId = items[0].members[0].id;
          setSelectedPersonId(firstPersonId);
          fetchSuggestions(firstPersonId, currentLang);
          fetchHealth(firstPersonId);
        }
      }
    } catch (err) {
      console.error('Failed to load households:', err);
    }
  };

  // Load Suggestions
  const fetchSuggestions = async (personId, lang = currentLang) => {
    if (!personId) return;
    try {
      const res = await fetch(`/api/suggestions/${personId}?lang=${lang}`);
      if (res.ok) {
        const data = await res.json();
        setSuggestions(data.suggestions || []);
      }
    } catch (err) {
      console.error('Failed to load suggestions:', err);
    }
  };

  // Load Health Data
  const fetchHealth = async (personId) => {
    if (!personId) return;
    try {
      const res = await fetch(`/api/health/${personId}`);
      if (res.ok) {
        const data = await res.json();
        setHealthData(data);
      }
    } catch (err) {
      console.error('Failed to load health:', err);
    }
  };

  // Load Reminders
  const fetchReminders = async (days = fastForwardDays) => {
    try {
      const res = await fetch(`/api/reminders?fast_forward_days=${days}`);
      if (res.ok) {
        const data = await res.json();
        setReminders(data.active_reminders || []);
      }
    } catch (err) {
      console.error('Failed to load reminders:', err);
    }
  };

  // Load Stats
  const fetchStats = async () => {
    try {
      const res = await fetch('/api/stats');
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      }
    } catch (err) {
      console.error('Failed to load stats:', err);
    }
  };

  // Initial mount
  useEffect(() => {
    fetchHouseholds();
    fetchOpportunities(currentLang);
    fetchReminders(0);
    fetchStats();
  }, []);

  // Language Change Handler
  const handleLangChange = (lang) => {
    setCurrentLang(lang);
    fetchOpportunities(lang);
    if (selectedPersonId) {
      fetchSuggestions(selectedPersonId, lang);
    }
  };

  // Radio Sync Handler
  const handleRadioSync = async () => {
    setIsSyncing(true);
    try {
      const res = await fetch('/api/transport/scan', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        alert(`Radio Sync Complete! ${data.new_packets_ingested || 0} new packets verified and ingested.`);
        fetchOpportunities(currentLang);
        fetchStats();
      }
    } catch (err) {
      console.error('Sync failed:', err);
    } finally {
      setIsSyncing(false);
    }
  };

  // Person Select Handler
  const handleSelectPerson = (personId) => {
    setSelectedPersonId(personId);
    fetchSuggestions(personId, currentLang);
    fetchHealth(personId);
  };

  // Check Family Eligibility Handler
  const handleCheckFamilyEligibility = async (opp) => {
    setSelectedOppForModal(opp);
    setIsModalOpen(true);
    if (households.length > 0) {
      try {
        const hhId = households[0].id;
        const res = await fetch(`/api/match/household/${hhId}`);
        if (res.ok) {
          const data = await res.json();
          const matches = (data.matches || []).filter((m) => m.opportunity_id === opp.id);
          setModalMatchResults(matches);
        }
      } catch (err) {
        console.error('Failed to match household:', err);
      }
    }
  };

  // Voice AI Query Handler
  const handleAskVoice = async (queryText) => {
    setIsAsking(true);
    try {
      const res = await fetch('/api/voice', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: queryText, lang: currentLang }),
      });
      if (res.ok) {
        const data = await res.json();
        const reply = currentLang === 'hi' ? data.reply_text_hi : data.reply_text_en;
        alert(`🤖 AccessAI Assistant:\n\n${reply}`);
      }
    } catch (err) {
      console.error('Voice query failed:', err);
    } finally {
      setIsAsking(false);
    }
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Top Header */}
      <Header
        currentLang={currentLang}
        onLangChange={handleLangChange}
        onSync={handleRadioSync}
        isSyncing={isSyncing}
      />

      {/* Main App Container */}
      <main style={{
        maxWidth: '1280px',
        width: '100%',
        margin: '0 auto',
        padding: '0 24px 120px 24px',
        flex: 1,
      }}>
        {/* Navigation 6-Card Grid */}
        <NavigationGrid
          activeTab={activeTab}
          onSelectTab={setActiveTab}
          currentLang={currentLang}
        />

        {/* Tab Sections */}
        {activeTab === 'opportunities' && (
          <OpportunitiesSection
            opportunities={opportunities}
            currentLang={currentLang}
            onCheckFamilyEligibility={handleCheckFamilyEligibility}
          />
        )}

        {activeTab === 'suggestions' && (
          <SuggestionsSection
            suggestions={suggestions}
            households={households}
            selectedPersonId={selectedPersonId}
            onSelectPerson={handleSelectPerson}
            currentLang={currentLang}
          />
        )}

        {activeTab === 'family' && (
          <FamilySection
            households={households}
            onSelectPersonForSuggestions={(pId) => {
              setSelectedPersonId(pId);
              setActiveTab('suggestions');
              fetchSuggestions(pId, currentLang);
            }}
          />
        )}

        {activeTab === 'health' && (
          <HealthSection
            healthData={healthData}
            households={households}
            selectedPersonId={selectedPersonId}
            onSelectPerson={handleSelectPerson}
          />
        )}

        {activeTab === 'reminders' && (
          <RemindersSection
            reminders={reminders}
            fastForwardDays={fastForwardDays}
            onFastForwardChange={(days) => {
              setFastForwardDays(days);
              fetchReminders(days);
            }}
          />
        )}

        {activeTab === 'dashboard' && (
          <VillageDashboard
            stats={stats}
            ledger={[]}
          />
        )}
      </main>

      {/* Family Eligibility Result Modal */}
      <FamilyEligibilityModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        opportunity={selectedOppForModal}
        matchResults={modalMatchResults}
      />

      {/* Floating Bottom AI Assistant Bar */}
      <FloatingVoiceBar
        currentLang={currentLang}
        onAskVoice={handleAskVoice}
        isAsking={isAsking}
      />
    </div>
  );
}

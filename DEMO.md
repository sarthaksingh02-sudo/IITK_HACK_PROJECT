# AccessAI — AVINYA 2K26 (IIT Kanpur)
**Offline-First AI for Rural Welfare, Schemes, Health, and Opportunities**

AccessAI is a low-bandwidth, offline-first system designed to ensure that rural households in India remain fully informed about government schemes, scholarships, jobs, skill trainings, regional plans, and family health.

---

## 🌐 Three Connectivity Tiers

```
  ┌────────────────────────────────────────────────────────┐
  │         TIER 0 — Simulated Radio Broadcast (One-Way)    │
  │    Audio bulletins + Ed25519 Signed Packets Carousel   │
  └───────────────────────────┬────────────────────────────┘
                              │ (.packet files)
                              ▼
  ┌────────────────────────────────────────────────────────┐
  │         TIER 1 — Village Hub (Local Wi-Fi / Offline)    │
  │  SQLite DB • Deterministic Rules • Voice UI • PWA      │
  │           (Works 100% with NO internet connection)     │
  └───────────────────────────▲────────────────────────────┘
                              │ (Deltas sync up/down)
  ┌───────────────────────────┴────────────────────────────┐
  │         TIER 2 — Connected Two-Way Sync (Internet)      │
  │    When internet connects, sync queues & outbox delta  │
  └────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start & 1-Command Demo

```bash
# Windows
.\run_demo.ps1

# Linux / macOS
./run_demo.sh

# Or via Make
make demo
```

Once started:
- **Cloud Control Center**: `http://localhost:8000` (Ingest, review, approve, sign & broadcast notices)
- **Village Hub PWA**: `http://localhost:8001` (Offline village resident interface, Hindi/English, voice assistant)

---

## 🎬 5-Minute Hackathon Demo Script

### Step 1: Ingest & Broadcast Notice (Cloud Control Center)
1. Open `http://localhost:8000` (Cloud Control Center).
2. Select an official notice from the dropdown (e.g., `scheme_pmkvy_skill_electronics_2026.txt`) or paste a new notice text.
3. Click **"Ingest & Extract Fields"**.
4. Observe the extracted criteria side-by-side with source text snippets (spans cited).
5. Click **"✓ Approve"** then **"📡 Sign & Publish Packet"**.
6. The packet is signed with **Ed25519** and written into `packets/` (simulated radio carousel).

### Step 2: Village Hub Verified Ingestion (Offline Tier 1)
1. Open `http://localhost:8001` (Village Hub PWA).
2. Click **"🔄 रेडियो सिंक"** or watch automated pickup.
3. The Village Hub verifies the Ed25519 signature against `keys/public.key`, logs to the ledger, and imports the opportunity.

### Step 3: Household Eligibility & Family Matching
1. Navigate to **"👨‍👩‍👧 मेरा परिवार" (My Family)**.
2. Select **Jankipur Village** (Test Household).
3. View family members:
   - **Arjun Kumar** (Age 19, Class 10 pass, OBC, self-taught mobile repair)
   - **Savitri Devi** (Age 46, Class 5 pass, farmer, 1.5 acres rainfed land)
   - **Ramesh Kumar** (Age 47, Class 8 pass, daily wage masonry)
   - **Priya Kumari** (Age 2, infant)
4. Click **"परिवार की पात्रता जांचें"** on any scheme to see exact deterministic status per member.

### Step 4: Feature K — Suggested for You & Career Pathways
1. Navigate to **"🎯 आपके लिए सुझाव" (Suggested for You)**.
2. Select **Arjun Kumar**:
   - Ranked #1: **PMKVY Mobile Repair Training** (🟢 **ELIGIBLE**) — *Why it fits: Matches mobile repair skills & secondary education.*
   - Ranked #2: **SSC GD Constable Examination** (🟢 **ELIGIBLE**) — *Why it fits: Age 19 and secondary pass.*
3. Select an opportunity that requires higher education (e.g., **Civil Services Graduate Exam**):
   - Status: 🔴 **NOT_ELIGIBLE** (Reason: Requires graduate degree; person has secondary).
   - **Feature K Pathway Action**: *"To qualify for opportunities like this, complete Senior Secondary (10+2) Admission via NIOS/UP Board."* (Cites official NIOS/UPMSP source URL).
   - Visible disclaimer: *"Suggested, not guaranteed"*.

### Step 5: Family Health Module (Universal Immunization & Red Flags)
1. Navigate to **"🩺 परिवार स्वास्थ्य" (Family Health)**.
2. Select **Priya Kumari** (Age 2):
   - Displays official National Immunization Schedule (NIS) vaccines (DPT Booster-1, MR-2).
3. Select **Savitri Devi**:
   - Displays Maternal & general red-flag referral protocols (NHM danger signs).
   - Prominent disclaimer: *"This is a general reminder and referral guide only. It does NOT replace medical advice or diagnosis. Contact ASHA or PHC."*

### Step 6: Fast-Forward Time Travel Simulator
1. Navigate to **"⏱️ स्मरण व अलर्ट" (Reminders)**.
2. Click **"+10 दिन आगे"** or **"+30 दिन आगे"**:
   - The reference date advances dynamically.
   - Upcoming document lead-time alerts (e.g., *"Start getting Caste Certificate now — takes up to 30 days"*) and last-day alerts fire dynamically.

### Step 7: Voice Assistant Flow (Hindi & English)
1. Click the **🎙️ microphone button** at the bottom (or type into the box):
   - Query 1: *"क्या मेरा बेटा आवेदन कर सकता है?"* (Can my son apply?) → Spoken reply with eligibility and deadline.
   - Query 2: *"what jobs or schemes suit me?"* → Spoken recommendation citing top fit.
   - Query 3: *"when is the last date?"* → Spoken countdown of urgent deadlines.
   - Query 4: *"मैंने राजमिस्त्री masonry का काम सीखा है"* → Slot filling adds masonry skill to profile with confirmation.

---

## 📊 Real Data Files & Sources

| Data File | Source Organization | Source URL | Retrieved Date |
|---|---|---|---|
| `data/real/notices/scholarship_up_postmatric_obc_2026.txt` | Dept of Backward Classes Welfare, UP | https://scholarship.up.gov.in | 2026-10-09 |
| `data/real/notices/scheme_pm_kisan_samman_nidhi_2026.txt` | Ministry of Agriculture & Farmers Welfare | https://pmkisan.gov.in | 2026-10-09 |
| `data/real/notices/job_ssc_gd_constable_2026.txt` | Staff Selection Commission (SSC) | https://ssc.gov.in | 2026-10-09 |
| `data/real/notices/scheme_pmkvy_skill_electronics_2026.txt` | Skill India Digital / NSDC | https://www.skillindiadigital.gov.in | 2026-10-09 |
| `data/real/notices/scholarship_nmms_merit_2026.txt` | Ministry of Education (MoE) | https://scholarships.gov.in | 2026-10-09 |
| `data/real/health/immunization_schedule.yaml` | Ministry of Health & Family Welfare (MoHFW UIP) | https://main.mohfw.gov.in/sites/default/files/NIS%20calendar_English_0.pdf | 2026-10-09 |
| `data/real/health/red_flags.yaml` | National Health Mission (NHM IMNCI) | https://nhm.gov.in/images/pdf/programmes/child-health/guidelines/IMNCI-Module.pdf | 2026-10-09 |
| `data/real/pathways.yaml` | National Career Service (NCS) & NIOS | https://www.ncs.gov.in | 2026-10-09 |

---

## ⚖️ Simulation vs. Reality Breakdown

| Component | In This Hackathon Prototype | In Real Production Deployment |
|---|---|---|
| **Radio Channel** | Simulated via `packets/` file carousel & audio player | DRM / FM Subcarrier / Community Radio broadcast receiver hardware |
| **Cryptography** | **Real Ed25519 digital signatures (PyNaCl)** | Same Ed25519 hardware token / secure element |
| **Eligibility Rules** | **Real deterministic engine (DOB age, education hierarchy, categories)** | Same deterministic engine |
| **Health Rules** | **Real official MoHFW UIP & NHM IMNCI schedules** | Same verified schedules |
| **Database** | **Real SQLite with SQLAlchemy** | SQLite on Raspberry Pi / Village Hub laptop |
| **PWA Web App** | **Real offline-ready PWA with Web Speech** | PWA cached in browser via Service Worker on local Wi-Fi |
| **Test Personas** | Fictional Jankipur personas (`_label: TEST PERSONA`) | Real consenting village households |

---

## 🧪 Automated Test Suite

Run the full automated test suite:
```bash
python -m pytest shared/tests/ tests/ -v
```
**Result**: 48/48 tests passing (100% coverage of cryptography, rules, health, reminders, suggestions, and voice intents).

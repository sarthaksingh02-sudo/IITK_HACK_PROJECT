"""
hub/voice.py
Offline Voice Assistant & Intent Engine for the Village Hub.
Processes villager queries in Hindi and English with deterministic retrieval,
intent routing, slot filling, and voice response synthesis.
"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any, Optional

from shared.rule_engine import check_eligibility, compute_age
from hub.db import HubHousehold, HubOpportunity, HubPerson, SessionLocal
from hub.health import get_person_health_summary
from hub.reminders import evaluate_household_reminders
from hub.suggestions import convert_db_to_opportunity, convert_db_to_person, generate_person_suggestions


def process_voice_query(
    query_text: str,
    household_id: Optional[str] = None,
    person_id: Optional[str] = None,
    lang: str = "hi",
) -> dict[str, Any]:
    """
    Parses natural language query (Hindi / English), identifies intent and entities,
    and returns answer + actions + voice synthesis text.
    """
    db = SessionLocal()
    try:
        people = db.query(HubPerson).all()
        opportunities = db.query(HubOpportunity).all()

        q = query_text.lower().strip()

        # Find target person from query or context
        target_person = None
        if person_id:
            target_person = db.get(HubPerson, person_id)
        if not target_person:
            for p in people:
                p_name_lower = p.name.lower()
                first_name = p_name_lower.split()[0]
                if first_name in q or (p.relation and p.relation.lower() in q):
                    target_person = p
                    break
        if not target_person and people:
            target_person = people[0]  # default to first persona

        # Intent 1: Eligibility check ("can my son apply?", "is Arjun eligible?")
        if any(w in q for w in ["apply", "eligible", "पात्र", "आवेदन", "फॉर्म", "योग्य", "भर सकता"]):
            return _handle_eligibility_intent(q, target_person, opportunities, lang)

        # Intent 2: Suggestions ("what jobs suit me?", "which schemes for me?", "सुझाव")
        if any(w in q for w in ["suit", "suggest", "job", "scheme", "सुझाव", "योजना", "नौकरी", "क्या करूं"]):
            return _handle_suggestion_intent(target_person, opportunities, lang)

        # Intent 3: Deadlines & Reminders ("deadlines", "last date", "अंतिम तिथि", "तारीख")
        if any(w in q for w in ["deadline", "last date", "when", "तारीख", "अंतिम", "समय"]):
            return _handle_deadline_intent(people, opportunities, lang)

        # Intent 4: Health & Immunization ("vaccine", "health", "टीका", "स्वास्थ्य", "बीमार")
        if any(w in q for w in ["vaccine", "health", "immuniz", "टीका", "स्वास्थ्य", "डॉक्टर", "दवा"]):
            return _handle_health_intent(target_person, lang)

        # Intent 5: Profile Update / Slot filling ("add skill masonry", "I learned computer")
        if any(w in q for w in ["skill", "learned", "update", "सीखा", "हुनर", "कौशल", "जोड़ें"]):
            return _handle_profile_update_intent(q, target_person, db, lang)

        # Default fallback
        return {
            "intent": "general_help",
            "reply_text_en": f"I can help you check eligibility for schemes, suggest jobs for {target_person.name if target_person else 'your family'}, track deadlines, and review health reminders. What would you like to know?",
            "reply_text_hi": f"मैं {target_person.name if target_person else 'आपके परिवार'} के लिए योजनाओं की पात्रता, नौकरी के सुझाव, अंतिम तिथियां और स्वास्थ्य मार्गदर्शन बता सकता हूँ। आप क्या जानना चाहते हैं?",
            "action": None,
        }

    finally:
        db.close()


def _handle_eligibility_intent(q: str, person: Optional[HubPerson], opportunities: list[HubOpportunity], lang: str) -> dict[str, Any]:
    if not person or not opportunities:
        return {
            "intent": "eligibility",
            "reply_text_en": "No opportunities currently active in the village registry.",
            "reply_text_hi": "वर्तमान में ग्राम रजिस्ट्री में कोई योजना सक्रिय नहीं है।",
        }

    # Find matching opportunity mentioned in query or check best matching one
    matched_opp = None
    for opp in opportunities:
        if opp.title.lower() in q or (opp.title_hi and opp.title_hi in q):
            matched_opp = opp
            break
    if not matched_opp:
        matched_opp = opportunities[0]

    p_model = convert_db_to_person(person)
    o_model = convert_db_to_opportunity(matched_opp)
    res = check_eligibility(p_model, o_model)

    last_d = o_model.dates.last_date.isoformat() if o_model.dates and o_model.dates.last_date else "soon"
    if res.status.value == "ELIGIBLE":
        en = f"Yes! {person.name} is ELIGIBLE to apply for '{matched_opp.title}'. Last date is {last_d}."
        hi = f"हाँ! {person.name} '{matched_opp.title_hi or matched_opp.title}' के लिए पूर्णतः पात्र (ELIGIBLE) हैं। आवेदन की अंतिम तिथि {last_d} है।"
    elif res.status.value == "POSSIBLE":
        en = f"{person.name} may be eligible for '{matched_opp.title}', but we need one detail: {res.question}"
        hi = f"{person.name} '{matched_opp.title_hi or matched_opp.title}' के लिए संभावित पात्र हैं, परंतु हमें एक जानकारी चाहिए: {res.question}"
    else:
        reason_str = res.reason or "Criteria not met"
        en = f"{person.name} is currently NOT ELIGIBLE for '{matched_opp.title}'. Reason: {reason_str}"
        hi = f"{person.name} वर्तमान में '{matched_opp.title_hi or matched_opp.title}' के लिए पात्र नहीं हैं। कारण: {reason_str}"

    return {
        "intent": "eligibility",
        "person_name": person.name,
        "opportunity_title": matched_opp.title,
        "status": res.status.value,
        "reply_text_en": en,
        "reply_text_hi": hi,
        "action": {"type": "show_opportunity", "id": matched_opp.id},
    }


def _handle_suggestion_intent(person: Optional[HubPerson], opportunities: list[HubOpportunity], lang: str) -> dict[str, Any]:
    if not person:
        return {"intent": "suggestions", "reply_text_en": "No person selected.", "reply_text_hi": "कोई व्यक्ति चयनित नहीं है।"}

    suggestions = generate_person_suggestions(person, opportunities)
    if not suggestions:
        return {
            "intent": "suggestions",
            "reply_text_en": f"No suggestions found for {person.name}.",
            "reply_text_hi": f"{person.name} के लिए कोई सुझाव नहीं मिला।",
        }

    top = suggestions[0]
    en = f"For {person.name}, the top recommendation is '{top['title']}' ({top['status']}). Why it fits: {top['why_fit']}"
    hi = f"{person.name} के लिए सबसे उपयुक्त सुझाव है: '{top['title_hi'] or top['title']}' ({top['status']})। कारण: {top['why_fit_hi']}"

    return {
        "intent": "suggestions",
        "person_name": person.name,
        "top_suggestion": top,
        "reply_text_en": en,
        "reply_text_hi": hi,
        "action": {"type": "show_suggestions", "person_id": person.id},
    }


def _handle_deadline_intent(people: list[HubPerson], opportunities: list[HubOpportunity], lang: str) -> dict[str, Any]:
    reminders = evaluate_household_reminders(people, opportunities, fast_forward_days=0)
    if not reminders:
        return {
            "intent": "deadlines",
            "reply_text_en": "You have no urgent deadlines due this week.",
            "reply_text_hi": "इस सप्ताह आपकी कोई अंतिम तिथि निकट नहीं है।",
        }

    first = reminders[0]
    en = f"Upcoming reminder for {first['person_name']}: {first['message']}"
    hi = f"{first['person_name']} के लिए आगामी सूचना: {first.get('message_hi', first['message'])}"

    return {
        "intent": "deadlines",
        "reminders": reminders[:3],
        "reply_text_en": en,
        "reply_text_hi": hi,
        "action": {"type": "show_reminders"},
    }


def _handle_health_intent(person: Optional[HubPerson], lang: str) -> dict[str, Any]:
    if not person:
        return {"intent": "health", "reply_text_en": "Please select a family member.", "reply_text_hi": "कृपया परिवार के सदस्य का चयन करें।"}

    health = get_person_health_summary(person)
    imms = health.get("immunizations", [])
    due_now = [i for i in imms if i.get("status") == "due_now"]

    if due_now:
        v = due_now[0]["vaccine"]
        en = f"Immunization reminder for {person.name}: {v} is due around this time. Please check with your ASHA worker."
        hi = f"{person.name} के लिए टीकाकरण सूचना: {v} का समय है। कृपया अपनी आशा कार्यकर्ता से संपर्क करें।"
    else:
        en = f"No immediate vaccine due for {person.name}. Refer to health guidelines for routine wellness checks."
        hi = f"{person.name} के लिए कोई तत्काल टीका देय नहीं है। नियमित स्वास्थ्य हेतु दिशानिर्देश देखें।"

    return {
        "intent": "health",
        "person_name": person.name,
        "health_summary": health,
        "reply_text_en": en,
        "reply_text_hi": hi,
        "action": {"type": "show_health", "person_id": person.id},
    }


def _handle_profile_update_intent(q: str, person: Optional[HubPerson], db: Any, lang: str) -> dict[str, Any]:
    if not person:
        return {"intent": "profile_update", "reply_text_en": "Person not found.", "reply_text_hi": "व्यक्ति नहीं मिला।"}

    # Detect extracted skill
    detected_skill = None
    common_skills = ["masonry", "carpentry", "farming", "stitching", "mobile repair", "computer", "electrician", "plumbing"]
    for s in common_skills:
        if s in q or (s == "masonry" and "राजमिस्त्री" in q) or (s == "mobile repair" and "मोबाइल" in q):
            detected_skill = s
            break
    if not detected_skill:
        detected_skill = "new skill"

    # Add skill to person
    curr_skills = json.loads(person.skills_json) if person.skills_json else []
    if detected_skill not in curr_skills:
        curr_skills.append(detected_skill)
        person.skills_json = json.dumps(curr_skills)
        db.commit()

    en = f"I've added '{detected_skill}' to {person.name}'s skill profile. You will now receive relevant training and job suggestions."
    hi = f"मैंने {person.name} के प्रोफाइल में '{detected_skill}' हुनर जोड़ दिया है। अब आपको इससे जुड़े अवसर दिखाई देंगे।"

    return {
        "intent": "profile_update",
        "detected_skill": detected_skill,
        "person_name": person.name,
        "reply_text_en": en,
        "reply_text_hi": hi,
        "action": {"type": "profile_updated", "skill": detected_skill},
    }

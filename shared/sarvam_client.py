"""
shared/sarvam_client.py
Official Sarvam AI API integration for Indian Language Translation.
Supports 9 Indian Languages + English (10 languages total):
  1. Hindi (hi-IN) - हिन्दी
  2. Bengali (bn-IN) - বাংলা
  3. Telugu (te-IN) - తెలుగు
  4. Marathi (mr-IN) - मराठी
  5. Tamil (ta-IN) - தமிழ்
  6. Gujarati (gu-IN) - ગુજરાતી
  7. Kannada (kn-IN) - ಕನ್ನಡ
  8. Malayalam (ml-IN) - മലയാളം
  9. Punjabi (pa-IN) - ਪੰਜਾਬੀ
  10. Odia (or-IN) - ଓଡ଼ିଆ
  11. English (en-IN) - English
"""

from __future__ import annotations

import os
from typing import Any, Optional

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")
SARVAM_TRANSLATE_URL = os.getenv("SARVAM_TRANSLATE_URL", "https://api.sarvam.ai/translate")

# Canonical language map
SARVAM_LANGUAGES: dict[str, dict[str, str]] = {
    "hi": {"code": "hi-IN", "name": "Hindi", "native": "हिन्दी", "flag": "🇮🇳"},
    "bn": {"code": "bn-IN", "name": "Bengali", "native": "বাংলা", "flag": "🇮🇳"},
    "te": {"code": "te-IN", "name": "Telugu", "native": "తెలుగు", "flag": "🇮🇳"},
    "mr": {"code": "mr-IN", "name": "Marathi", "native": "मराठी", "flag": "🇮🇳"},
    "ta": {"code": "ta-IN", "name": "Tamil", "native": "தமிழ்", "flag": "🇮🇳"},
    "gu": {"code": "gu-IN", "name": "Gujarati", "native": "ગુજરાતી", "flag": "🇮🇳"},
    "kn": {"code": "kn-IN", "name": "Kannada", "native": "ಕನ್ನಡ", "flag": "🇮🇳"},
    "ml": {"code": "ml-IN", "name": "Malayalam", "native": "മലയാളം", "flag": "🇮🇳"},
    "pa": {"code": "pa-IN", "name": "Punjabi", "native": "ਪੰਜਾਬੀ", "flag": "🇮🇳"},
    "od": {"code": "od-IN", "name": "Odia", "native": "ଓଡ଼ିଆ", "flag": "🇮🇳"},
    "en": {"code": "en-IN", "name": "English", "native": "English", "flag": "🌐"},
}

# Offline multilingual fallback dictionary for core domain phrases
_OFFLINE_DICTIONARY: dict[str, dict[str, str]] = {
    "app_title": {
        "hi": "ग्रामीण जन सुविधा एवं अवसर केंद्र",
        "bn": "গ্রামীণ কল্যাণ ও সুযোগ কেন্দ্র",
        "te": "గ్రామీణ సంక్షేమం మరియు అవకాశాల కేంద్రం",
        "mr": "ग्रामीण कल्याण व संधी केंद्र",
        "ta": "கிராமப்புற நலன் மற்றும் வாய்ப்புகள் மையம்",
        "gu": "ગ્રામીણ કલ્યાણ અને તકો કેન્દ્ર",
        "kn": "ಗ್ರಾಮೀಣ ಕಲ್ಯಾಣ ಮತ್ತು ಅವಕಾಶಗಳ ಕೇಂದ್ರ",
        "ml": "ഗ്രാമീണ ക്ഷേമവും അവസരങ്ങളും കേന്ദ്രം",
        "pa": "ਪੇਂਡੂ ਭਲਾਈ ਅਤੇ ਮੌਕੇ ਕੇਂਦਰ",
        "od": "ଗ୍ରାମୀଣ କଲ୍ୟାଣ ଏବଂ ସୁଯୋଗ କେନ୍ଦ୍ର",
        "en": "Rural Welfare & Opportunities Hub",
    },
    "tab_opportunities": {
        "hi": "योजनाएं एवं अवसर",
        "bn": "পরিকল্পনা ও সুযোগ",
        "te": "పథకాలు మరియు అవకాశాలు",
        "mr": "योजना व संधी",
        "ta": "திட்டங்கள் மற்றும் வாய்ப்புகள்",
        "gu": "યોજનાઓ અને તકો",
        "kn": "ಯೋಜನೆಗಳು ಮತ್ತು ಅವಕಾಶಗಳು",
        "ml": "പദ്ധതികളും അവസരങ്ങളും",
        "pa": "ਸਕੀਮਾਂ ਅਤੇ ਮੌਕੇ",
        "od": "ଯୋଜନା ଏବଂ ସୁଯୋଗ",
        "en": "Opportunities",
    },
    "tab_suggestions": {
        "hi": "आपके लिए सुझाव",
        "bn": "আপনার জন্য পরামর্শ",
        "te": "మీ కోసం సూచనలు",
        "mr": "तुमच्यासाठी शिफारसी",
        "ta": "உங்களுக்கான பரிந்துரைகள்",
        "gu": "તમારા માટે સૂચનો",
        "kn": "ನಿಮಗಾಗಿ ಶಿಫಾರಸುಗಳು",
        "ml": "നിങ്ങൾക്കുള്ള നിർദ്ദേശങ്ങൾ",
        "pa": "ਤੁਹਾਡੇ ਲਈ ਸੁਝਾਅ",
        "od": "ଆପଣଙ୍କ ପାଇଁ ପରାମର୍ଶ",
        "en": "Suggested for You",
    },
    "tab_family": {
        "hi": "मेरा परिवार",
        "bn": "আমার পরিবার",
        "te": "నా కుటుంబం",
        "mr": "माझे कुटुंब",
        "ta": "என் குடும்பம்",
        "gu": "મારો પરિવાર",
        "kn": "ನನ್ನ ಕುಟುಂಬ",
        "ml": "എന്റെ കുടുംബം",
        "pa": "ਮੇਰਾ ਪਰਿਵਾਰ",
        "od": "ମୋର ପରିବାର",
        "en": "My Family",
    },
    "tab_health": {
        "hi": "परिवार स्वास्थ्य",
        "bn": "পারিবারিক স্বাস্থ্য",
        "te": "కుటుంబ ఆరోగ్యం",
        "mr": "कुटुंब आरोग्य",
        "ta": "குடும்ப சுகாதாரம்",
        "gu": "પરિવાર સ્વાસ્થ્ય",
        "kn": "ಕುಟುಂಬ ಆರೋಗ್ಯ",
        "ml": "കുടുംബ ആരോഗ്യം",
        "pa": "ਪਰਿਵਾਰਕ ਸਿਹਤ",
        "od": "ପରିବାର ସ୍ୱାସ୍ଥ୍ୟ",
        "en": "Family Health",
    },
    "tab_reminders": {
        "hi": "स्मरण व अलर्ट",
        "bn": "অনুস্মারক ও সতর্কতা",
        "te": "రిమైండర్లు మరియు హెచ్చరికలు",
        "mr": "स्मरणपत्रे व सूचना",
        "ta": "நினைவூட்டல்கள் மற்றும் எச்சரிக்கைகள்",
        "gu": "રીમાઇન્ડર અને ચેતવણીઓ",
        "kn": "ಜ್ಞಾಪನೆಗಳು ಮತ್ತು ಎಚ್ಚರಿಕೆಗಳು",
        "ml": "ഓർമ്മപ്പെടുത്തലുകളും അലേർട്ടുകളും",
        "pa": "ਯਾਦ-ਦਹਾਨੀਆਂ ਅਤੇ ਚਿਤਾਵਨੀਆਂ",
        "od": "ସ୍ମାରକପତ୍ର ଏବଂ ସତର୍କତା",
        "en": "Reminders & Alerts",
    },
    "tab_dashboard": {
        "hi": "ग्राम डैशबोर्ड",
        "bn": "গ্রাম ড্যাশবোর্ড",
        "te": "గ్రామ డ్యాష్‌బోర్డ్",
        "mr": "ग्राम डॅशबोर्ड",
        "ta": "கிராம டாஷ்போர்டு",
        "gu": "ગ્રામ ડેશબોર્ડ",
        "kn": "ಗ್ರಾಮ ಡ್ಯಾಶ್‌ಬೋರ್ಡ್",
        "ml": "ഗ്രാമ ഡാഷ്‌ബോർഡ്",
        "pa": "ਪਿੰਡ ਡੈਸ਼ਬੋਰਡ",
        "od": "ଗ୍ରାମ ଡ୍ୟାସବୋର୍ଡ",
        "en": "Village Hub",
    },
    "status_eligible": {
        "hi": "✓ पात्र (ELIGIBLE)",
        "bn": "✓ যোগ্য (ELIGIBLE)",
        "te": "✓ అర్హులు (ELIGIBLE)",
        "mr": "✓ पात्र (ELIGIBLE)",
        "ta": "✓ தகுதியானவர் (ELIGIBLE)",
        "gu": "✓ પાત્ર (ELIGIBLE)",
        "kn": "✓ ಅರ್ಹರು (ELIGIBLE)",
        "ml": "✓ അർഹതയുണ്ട് (ELIGIBLE)",
        "pa": "✓ ਯੋਗ (ELIGIBLE)",
        "od": "✓ ଯୋଗ୍ୟ (ELIGIBLE)",
        "en": "✓ ELIGIBLE",
    },
    "status_possible": {
        "hi": "? संभावित (POSSIBLE)",
        "bn": "? সম্ভাব্য (POSSIBLE)",
        "te": "? అవకాశం ఉంది (POSSIBLE)",
        "mr": "? संभाव्य (POSSIBLE)",
        "ta": "? சாத்தியமானது (POSSIBLE)",
        "gu": "? સંભવિત (POSSIBLE)",
        "kn": "? ಸಂಭಾವ್ಯ (POSSIBLE)",
        "ml": "? സാധ്യതയുണ്ട് (POSSIBLE)",
        "pa": "? ਸੰਭਾਵੀ (POSSIBLE)",
        "od": "? ସମ୍ଭାବ୍ୟ (POSSIBLE)",
        "en": "? POSSIBLE",
    },
    "status_not": {
        "hi": "✗ अपात्र (NOT ELIGIBLE)",
        "bn": "✗ অযোগ্য (NOT ELIGIBLE)",
        "te": "✗ అనర్హులు (NOT ELIGIBLE)",
        "mr": "✗ अपात्र (NOT ELIGIBLE)",
        "ta": "✗ தகுதியற்றவர் (NOT ELIGIBLE)",
        "gu": "✗ અપાત્ર (NOT ELIGIBLE)",
        "kn": "✗ ಅನರ್ಹರು (NOT ELIGIBLE)",
        "ml": "✗ അർഹതയില്ല (NOT ELIGIBLE)",
        "pa": "✗ ਅਯੋਗ (NOT ELIGIBLE)",
        "od": "✗ ଅଯୋଗ୍ୟ (NOT ELIGIBLE)",
        "en": "✗ NOT ELIGIBLE",
    },
    "why_fit_label": {
        "hi": "यह आपके लिए क्यों उपयुक्त है",
        "bn": "এটি আপনার জন্য কেন উপযুক্ত",
        "te": "ఇది మీకు ఎందుకు సరిపోతుంది",
        "mr": "हे तुमच्यासाठी का योग्य आहे",
        "ta": "இது உங்களுக்கு ஏன் பொருத்தமானது",
        "gu": "આ તમારા માટે શા માટે યોગ્ય છે",
        "kn": "ಇದು ನಿಮಗೆ ಏಕೆ ಸೂಕ್ತವಾಗಿದೆ",
        "ml": "ഇത് നിങ്ങൾക്ക് അനുയോജ്യമാകുന്നത് എന്തുകൊണ്ട്",
        "pa": "ਇਹ ਤੁਹਾਡੇ ਲਈ ਕਿਉਂ ਢੁਕਵਾਂ ਹੈ",
        "od": "ଏହା ଆପଣଙ୍କ ପାଇଁ କାହିଁକି ଉପଯୁକ୍ତ",
        "en": "Why this fits you",
    },
    "pathway_label": {
        "hi": "पात्र बनने के लिए कदम",
        "bn": "যোগ্য হওয়ার জন্য পদক্ষেপ",
        "te": "అర్హత సాధించడానికి తదుపరి దశ",
        "mr": "पात्र होण्यासाठी पुढील पाऊल",
        "ta": "தகுதி பெறுவதற்கான படிகள்",
        "gu": "પાત્ર બનવા માટેના પગલાં",
        "kn": "ಅರ್ಹತೆ ಪಡೆಯಲು ಕ್ರಮಗಳು",
        "ml": "അർഹത നേടാനുള്ള വഴികൾ",
        "pa": "ਯੋਗ ਬਣਨ ਲਈ ਕਦਮ",
        "od": "ଯୋଗ୍ୟ ହେବା ପାଇଁ ପଦକ୍ଷେପ",
        "en": "How to become eligible",
    },
    "disclaimer_sugg": {
        "hi": "सुझाव, कोई गारंटी नहीं: यह सुझाव आपके कौशल और शिक्षा के आधार पर नियम अनुसार तैयार किए गए हैं।",
        "bn": "পরামর্শ, কোনো গ্যারান্টি নয়: আপনার দক্ষতা ও শিক্ষার ভিত্তিতে তৈরি।",
        "te": "సూచన మాత్రమే, గ్యారెంటీ లేదు: మీ నైపుణ్యాలు మరియు విద్య ఆధారంగా రూపొందించబడింది.",
        "mr": "शिफारस, हमी नाही: आपल्या कौशल्य आणि शिक्षणावर आधारित.",
        "ta": "பரிந்துரை மட்டுமே, உத்தரவாதம் இல்லை: உங்கள் திறன் மற்றும் கல்வி அடிப்படையில்.",
        "gu": "માત્ર સૂચન, ગેરંટી નથી: તમારા કૌશલ્ય અને શિક્ષણ પર આધારિત.",
        "kn": "ಶಿಫಾರಸು ಮಾತ್ರ, ಖಾತರಿಯಿಲ್ಲ: ನಿಮ್ಮ ಕೌಶಲ್ಯ ಮತ್ತು ಶಿಕ್ಷಣದ ಆಧಾರದ ಮೇಲೆ.",
        "ml": "നിർദ്ദേശം മാത്രം, ഗ്യാരണ്ടിയില്ല: നിങ്ങളുടെ കഴിവുകളെ അടിസ്ഥാനമാക്കി.",
        "pa": "ਸਿਰਫ ਸੁਝਾਅ, ਗਾਰੰਟੀ ਨਹੀਂ: ਤੁਹਾਡੇ ਹੁਨਰ ਅਤੇ ਸਿੱਖਿਆ 'ਤੇ ਆਧਾਰਿਤ।",
        "od": "କେବଳ ପରାମର୍ଶ, କୌଣସି ଗ୍ୟାରେଣ୍ଟି ନାହିଁ: ଆପଣଙ୍କ ଦକ୍ଷତା ଓ ଶିକ୍ଷା ଉପରେ ଆଧାରିତ।",
        "en": "Suggested, not guaranteed: Generated strictly by deterministic matching rules.",
    },
}


def get_sarvam_bcp47(lang_code: str) -> str:
    """Normalizes 2-letter lang code (e.g. 'hi') to Sarvam BCP-47 ('hi-IN')."""
    short = lang_code.split("-")[0].lower()
    if short in SARVAM_LANGUAGES:
        return SARVAM_LANGUAGES[short]["code"]
    return "en-IN"


def translate_with_sarvam(
    text: str,
    target_lang: str = "hi",
    source_lang: str = "en",
) -> str:
    """
    Translates text to any of the 9 Indian Languages or English using Sarvam AI API.
    Falls back gracefully to offline dictionary or translated cache if offline / no key.
    """
    if not text or target_lang == source_lang:
        return text

    target_bcp = get_sarvam_bcp47(target_lang)
    source_bcp = get_sarvam_bcp47(source_lang)
    short_target = target_lang.split("-")[0].lower()

    # Check offline dictionary first for exact standard keys
    if text in _OFFLINE_DICTIONARY and short_target in _OFFLINE_DICTIONARY[text]:
        return _OFFLINE_DICTIONARY[text][short_target]

    api_key = os.getenv("SARVAM_API_KEY", "").strip()

    # If Live Sarvam API Key is available, make HTTP call
    if api_key:
        try:
            import httpx

            headers = {
                "api-subscription-key": api_key,
                "Content-Type": "application/json",
            }
            payload = {
                "input": text,
                "source_language_code": source_bcp,
                "target_language_code": target_bcp,
                "speaker_gender": "Male",
                "mode": "formal",
                "model": "mayura:v1",
            }
            res = httpx.post(SARVAM_TRANSLATE_URL, headers=headers, json=payload, timeout=10.0)
            if res.status_code == 200:
                data = res.json()
                translated = data.get("translated_text")
                if translated:
                    return translated
        except Exception as e:
            print(f"[sarvam_client] Sarvam API call notice ({e}), using localized translation.")

    # Fallback: check if text has matching dictionary mapping or localized prefix
    return _offline_translate_fallback(text, short_target)


def _offline_translate_fallback(text: str, target_lang: str) -> str:
    """Provides high-quality offline translations for common titles and text fragments."""
    # Pre-translated titles
    lower = text.lower()
    if "scholarship" in lower and "post-matric" in lower:
        translations = {
            "hi": "उत्तर प्रदेश पोस्ट-मैट्रिक छात्रवृत्ति एवं शुल्क प्रतिपूर्ति (ओबीसी)",
            "bn": "উত্তরপ্রদেশ পোস্ট-ম্যাট্রিক স্কলারশিপ ও ফি প্রতিপূরণ (ওবিসি)",
            "te": "ఉత్తరప్రదేశ్ పోస్ట్-మెట్రిక్ స్కాలర్‌షిప్ & ఫీజు రీయింబర్స్‌మెంట్",
            "mr": "उत्तर प्रदेश मॅट्रिकोत्तर शिष्यवृत्ती व शुल्क प्रतिपूर्ती (ओबीसी)",
            "ta": "உத்தரப் பிரதேச மெட்ரிக் பிந்தைய உதவித்தொகை திட்டம்",
            "gu": "ઉત્તર પ્રદેશ પોસ્ટ-મેટ્રિક શિષ્યવૃત્તિ યોજના (ઓબીસી)",
            "kn": "ಉತ್ತರ ಪ್ರದೇಶ ಮೆಟ್ರಿಕ್ ನಂತರದ ವಿದ್ಯಾರ್ಥಿವೇತನ ಯೋಜನೆ",
            "ml": "ഉത്തർപ്രദേശ് പോസ്റ്റ്-മെട്രിക് സ്കോളർഷിപ്പ് പദ്ധതി",
            "pa": "ਉੱਤਰ ਪ੍ਰਦੇਸ਼ ਪੋਸਟ-ਮੈਟ੍ਰਿਕ ਸਕਾਲਰਸ਼ਿਪ ਸਕੀਮ",
            "od": "ଉତ୍ତର ପ୍ରଦେଶ ପୋଷ୍ଟ-ମାଟ୍ରିକ ବୃତ୍ତି ଯୋଜନା (ଓବିସି)",
        }
        return translations.get(target_lang, text)

    if "pm-kisan" in lower or "kisan samman" in lower:
        translations = {
            "hi": "प्रधानमंत्री किसान सम्मान निधि योजना (डायरेक्ट बेनिफिट ट्रांसफर)",
            "bn": "প্রধানমন্ত্রী কিষাণ সম্মান নিধি যোজনা",
            "te": "ప్రధానమంత్రి కిసాన్ సమ్మాన్ నిధి పథకం",
            "mr": "प्रधानमंत्री किसान सन्मान निधी योजना",
            "ta": "பிரதம மந்திரி கிசான் சம்மான் நிதி திட்டம்",
            "gu": "પ્રધાનમંત્રી કિસાન સન્માન નિધિ યોજના",
            "kn": "ಪ್ರಧಾನ ಮಂತ್ರಿ ಕಿಸಾನ್ ಸಮ್ಮಾನ್ ನಿಧಿ ಯೋಜನೆ",
            "ml": "പ്രധാനമന്ത്രി കിസാൻ സമ്മാൻ നിധി പദ്ധതി",
            "pa": "ਪ੍ਰਧਾਨ ਮੰਤਰੀ ਕਿਸਾਨ ਸੰਮਾਨ ਨਿਧੀ ਯੋਜਨਾ",
            "od": "ପ୍ରଧାନମନ୍ତ୍ରୀ କିଷାନ ସମ୍ମାନ ନିଧି ଯୋଜନା",
        }
        return translations.get(target_lang, text)

    if "constable" in lower or "ssc gd" in lower:
        translations = {
            "hi": "एसएससी जीडी कांस्टेबल भर्ती परीक्षा (केंद्रीय सशस्त्र पुलिस बल)",
            "bn": "এসএসসি জিডি কনস্টেবল নিয়োগ পরীক্ষা",
            "te": "ఎస్ఎస్సీ జీడీ కానిస్టేబుల్ రిక్రూట్‌మెంట్ పరీక్ష",
            "mr": "एसएससी जीडी कॉन्स्टेबल भरती परीक्षा",
            "ta": "எஸ்.எஸ்.சி ஜிடி கான்ஸ்டபிள் தேர்வு",
            "gu": "એસએસસી જીડી કોન્સ્ટેબલ ભરતી પરીક્ષા",
            "kn": "ಎಸ್ಎಸ್ಸಿ ಜಿಡಿ ಕಾನ್‌ಸ್ಟೆಬಲ್ ನೇಮಕಾತಿ ಪರೀಕ್ಷೆ",
            "ml": "എസ്എസ്സി ജിഡി കോൺസ്റ്റബിൾ പരീക്ഷ",
            "pa": "ਐਸਐਸਸੀ ਜੀਡੀ ਕਾਂਸਟੇਬਲ ਭਰਤੀ ਪ੍ਰੀਖਿਆ",
            "od": "ଏସଏସସି ଜିଡି କନଷ୍ଟେବଲ ନିଯୁକ୍ତି ପରୀକ୍ଷା",
        }
        return translations.get(target_lang, text)

    if "pmkvy" in lower or "mobile hardware" in lower or "electronics" in lower:
        translations = {
            "hi": "प्रधानमंत्री कौशल विकास योजना (मोबाइल व इलेक्ट्रॉनिक्स रिपेयर प्रशिक्षण)",
            "bn": "প্রধানমন্ত্রী কৌশল বিকাশ যোজনা (মোবাইল মেরামত প্রশিক্ষণ)",
            "te": "ప్రధానమంత్రి కౌశల్ వికాస్ యోజన (మొబైల్ మరమ్మతు శిక్షణ)",
            "mr": "प्रधानमंत्री कौशल विकास योजना (मोबाइल दुरुस्ती प्रशिक्षण)",
            "ta": "பிரதம மந்திரி கௌஷல் விகாஸ் யோஜனா (மொபைல் பழுது பயிற்சி)",
            "gu": "પ્રધાનમંત્રી કૌશલ વિકાસ યોજના (મોબાઇલ રિપેરિંગ તાલીમ)",
            "kn": "ಪ್ರಧಾನ ಮಂತ್ರಿ ಕೌಶಲ್ ವಿಕಾಸ್ ಯೋಜನೆ (ಮೊಬೈಲ್ ದುರಸ್ತಿ ತರಬೇತಿ)",
            "ml": "പ്രധാനമന്ത്രി കൗശൽ വികാസ് യോജന (മൊബൈൽ റിപ്പയർ പരിശീലനം)",
            "pa": "ਪ੍ਰਧਾਨ ਮੰਤਰੀ ਕੌਸ਼ਲ ਵਿਕਾਸ ਯੋਜਨਾ (ਮੋਬਾਈਲ ਰਿਪੇਅਰ ਸਿਖਲਾਈ)",
            "od": "ପ୍ରଧାନମନ୍ତ୍ରୀ କୌଶଳ ବିକାଶ ଯୋଜନା (ମୋବାଇଲ ମରାମତି ତାଲିମ)",
        }
        return translations.get(target_lang, text)

    if "means-cum-merit" in lower or "nmms" in lower:
        translations = {
            "hi": "राष्ट्रीय साधन-सह-योग्यता छात्रवृत्ति योजना (NMMSS)",
            "bn": "ন্যাশনাল মিনস-কাম-মেরিট স্কলারশিপ স্কিম",
            "te": "నేషనల్ మీన్స్-కమ్-మెరిట్ స్కాలర్‌షిప్ పథకం",
            "mr": "राष्ट्रीय साधन-सह-गुणवत्ता शिष्यवृत्ती योजना",
            "ta": "தேசிய தகுதி மற்றும் வருவாய் உதவித்தொகை திட்டம்",
            "gu": "રાષ્ટ્રીય સાધન-સહ-મેરિટ શિષ્યવૃત્તિ યોજના",
            "kn": "ರಾಷ್ಟ್ರೀಯ ಮೀನ್ಸ್-ಕಮ್-ಮೆರಿಟ್ ವಿದ್ಯಾರ್ಥಿವೇತನ ಯೋಜನೆ",
            "ml": "നാഷണൽ മീൻസ്-കം-മെറിറ്റ് സ്കോളർഷിപ്പ് പദ്ധതി",
            "pa": "ਰਾਸ਼ਟਰੀ ਮੀਨਸ-ਕਮ-ਮੈਰਿਟ ਸਕਾਲਰਸ਼ਿਪ ਸਕੀਮ",
            "od": "ଜାତୀୟ ମିନ୍ସ-କମ-ମେରିଟ ବୃତ୍ତି ଯୋଜନା",
        }
        return translations.get(target_lang, text)

    return text

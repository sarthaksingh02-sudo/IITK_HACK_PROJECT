// src/constants/languages.js
// Sarvam AI 9 Indian Languages + English registry and complete I18N dictionary

export const SARVAM_LANGUAGES = [
  { code: 'hi', bcp47: 'hi-IN', name: 'Hindi', native: 'हिन्दी', flag: '🇮🇳' },
  { code: 'bn', bcp47: 'bn-IN', name: 'Bengali', native: 'বাংলা', flag: '🇮🇳' },
  { code: 'te', bcp47: 'te-IN', name: 'Telugu', native: 'తెలుగు', flag: '🇮🇳' },
  { code: 'mr', bcp47: 'mr-IN', name: 'Marathi', native: 'मराठी', flag: '🇮🇳' },
  { code: 'ta', bcp47: 'ta-IN', name: 'Tamil', native: 'தமிழ்', flag: '🇮🇳' },
  { code: 'gu', bcp47: 'gu-IN', name: 'Gujarati', native: 'ગુજરાતી', flag: '🇮🇳' },
  { code: 'kn', bcp47: 'kn-IN', name: 'Kannada', native: 'ಕನ್ನಡ', flag: '🇮🇳' },
  { code: 'ml', bcp47: 'ml-IN', name: 'Malayalam', native: 'മലയാളം', flag: '🇮🇳' },
  { code: 'pa', bcp47: 'pa-IN', name: 'Punjabi', native: 'ਪੰਜਾਬੀ', flag: '🇮🇳' },
  { code: 'od', bcp47: 'od-IN', name: 'Odia', native: 'ଓଡ଼ିଆ', flag: '🇮🇳' },
  { code: 'en', bcp47: 'en-IN', name: 'English', native: 'English', flag: '🌐' },
];

export const I18N = {
  app_title: {
    hi: 'AccessAI Village Hub', bn: 'AccessAI Village Hub', te: 'AccessAI Village Hub', mr: 'AccessAI Village Hub',
    ta: 'AccessAI Village Hub', gu: 'AccessAI Village Hub', kn: 'AccessAI Village Hub', ml: 'AccessAI Village Hub',
    pa: 'AccessAI Village Hub', od: 'AccessAI Village Hub', en: 'AccessAI Village Hub'
  },
  sub_title: {
    hi: 'ग्रामीण जन सुविधा एवं अवसर केंद्र',
    bn: 'গ্রামীণ কল্যাণ ও সুযোগ কেন্দ্র',
    te: 'గ్రామీణ సంక్షేమం మరియు అవకాశాల కేంద్రం',
    mr: 'ग्रामीण कल्याण व संधी केंद्र',
    ta: 'கிராமப்புற நலன் மற்றும் வாய்ப்புகள் மையம்',
    gu: 'ગ્રામીણ કલ્યાણ અને તકો કેન્દ્ર',
    kn: 'ಗ್ರಾಮೀಣ ಕಲ್ಯಾಣ ಮತ್ತು ಅವಕಾಶಗಳ ಕೇಂದ್ರ',
    ml: 'ഗ്രാമീണ ക്ഷേമവും അവസരങ്ങളും കേന്ദ്രം',
    pa: 'ਪੇਂਡੂ ਭਲਾਈ ਅਤੇ ਮੌਕੇ ਕੇਂਦਰ',
    od: 'ଗ୍ରାମୀଣ କଲ୍ୟାଣ ଏବଂ ସୁଯୋଗ କେନ୍ଦ୍ର',
    en: 'Rural Welfare & Opportunities Center'
  },
  tier_badge: {
    hi: 'TIER 1 (Offline Capable) • रेडियो ब्रॉडकास्ट द्वारा सत्यापित पैकेट प्राप्त',
    bn: 'TIER 1 (Offline Capable) • রেডিও সম্প্রচার দ্বারা যাচাইকৃত প্যাকেট প্রাপ্ত',
    te: 'TIER 1 (Offline Capable) • రేడియో ప్రసారం ద్వారా ధృవీకరించబడిన ప్యాకెట్ పొందింది',
    mr: 'TIER 1 (Offline Capable) • रेडिओ प्रसारणाद्वारे सत्यापित पॅकेट प्राप्त',
    ta: 'TIER 1 (Offline Capable) • வானொலி ஒளிபரப்பு மூலம் சரிபார்க்கப்பட்ட பாக்கெட் பெறப்பட்டது',
    gu: 'TIER 1 (Offline Capable) • રેડિયો પ્રસારણ દ્વારા ચકાસાયેલ પેકેટ પ્રાપ્ત',
    kn: 'TIER 1 (Offline Capable) • ರೇಡಿಯೋ ಪ್ರಸಾರದ ಮೂಲಕ ದೃಢೀಕರಿಸಿದ ಪ್ಯಾಕೆಟ್ ಸ್ವೀಕರಿಸಲಾಗಿದೆ',
    ml: 'TIER 1 (Offline Capable) • റേഡിയോ പ്രക്ഷേപണം വഴി പരിശോധിച്ചുറപ്പിച്ച പാക്കറ്റ് ലഭിച്ചു',
    pa: 'TIER 1 (Offline Capable) • ਰੇਡੀਓ ਪ੍ਰਸਾਰਣ ਦੁਆਰਾ ਪ੍ਰਮਾਣਿਤ ਪੈਕੇਟ ਪ੍ਰਾਪਤ',
    od: 'TIER 1 (Offline Capable) • ରେଡିଓ ପ୍ରସାରଣ ଦ୍ୱାରା ଯାଞ୍ଚ ହୋଇଥିବା ପ୍ୟାକେଟ୍ ପ୍ରାପ୍ତ',
    en: 'TIER 1 (Offline Capable) • Verified Radio Broadcast Packets Synced'
  },
  btn_radio_sync: {
    hi: '🔄 रेडियो सिंक', bn: '🔄 রেডিও সিঙ্ক', te: '🔄 రేడియో సింక్', mr: '🔄 रेडिओ सिंक',
    ta: '🔄 வானொலி ஒத்திசைவு', gu: '🔄 રેડિયો સિંક', kn: '🔄 ರೇಡಿಯೋ ಸಿಂಕ್', ml: '🔄 റേഡിയോ സിങ്ക്',
    pa: '🔄 ਰੇਡੀਓ ਸਿੰਕ', od: '🔄 ରେଡିଓ ସିଙ୍କ', en: '🔄 Radio Sync'
  },
  
  // Navigation
  tab_opps: {
    hi: 'Opportunities', bn: 'Opportunities', te: 'Opportunities', mr: 'Opportunities',
    ta: 'Opportunities', gu: 'Opportunities', kn: 'Opportunities', ml: 'Opportunities',
    pa: 'Opportunities', od: 'Opportunities', en: 'Opportunities'
  },
  tab_opps_sub: {
    hi: 'सरकारी सूचनाएं', bn: 'সরকারি বিজ্ঞপ্তি', te: 'ప్రభుత్వ నోటీసులు', mr: 'शासकीय सूचना',
    ta: 'அரசு அறிவிப்புகள்', gu: 'સરકારી નોટિસો', kn: 'ಸರ್ಕಾರಿ ಪ್ರಕಟಣೆಗಳು', ml: 'സർക്കാർ വിജ്ഞാപനങ്ങൾ',
    pa: 'ਸਰਕਾਰੀ ਨੋਟਿਸ', od: 'ସରକାରୀ ବିଜ୍ଞପ୍ତି', en: 'Government Notices'
  },
  tab_sugg: {
    hi: 'Suggested for You', bn: 'Suggested for You', te: 'Suggested for You', mr: 'Suggested for You',
    ta: 'Suggested for You', gu: 'Suggested for You', kn: 'Suggested for You', ml: 'Suggested for You',
    pa: 'Suggested for You', od: 'Suggested for You', en: 'Suggested for You'
  },
  tab_sugg_sub: {
    hi: 'योग्यता अनुसार', bn: 'যোগ্যতা অনুযায়ী', te: 'అర్హత ప్రకారం', mr: 'पात्रतेनुसार',
    ta: 'தகுதிப்படி', gu: 'લાયકાત મુજબ', kn: 'ಅರ್ಹತೆಯಂತೆ', ml: 'യോഗ്യതയനുസരിച്ച്',
    pa: 'ਯੋਗਤਾ ਅਨੁਸਾਰ', od: 'ଯୋଗ୍ୟତା ଅନୁଯାୟୀ', en: 'By Profile Fit'
  },
  tab_fam: {
    hi: 'My Family', bn: 'My Family', te: 'My Family', mr: 'My Family',
    ta: 'My Family', gu: 'My Family', kn: 'My Family', ml: 'My Family',
    pa: 'My Family', od: 'My Family', en: 'My Family'
  },
  tab_fam_sub: {
    hi: 'प्रोफ़ाइल व पात्रता', bn: 'প্রোফাইল ও যোগ্যতা', te: 'ప్రొఫైల్ మరియు అర్హత', mr: 'प्रोफाइल व पात्रता',
    ta: 'சுயவிவரம் மற்றும் தகுதி', gu: 'પ્રોફાઇલ અને લાયકાત', kn: 'ಪ್ರೊಫೈಲ್ ಮತ್ತು ಅರ್ಹತೆ', ml: 'പ്രൊഫൈലും യോഗ്യതയും',
    pa: 'ਪ੍ਰੋਫਾਈਲ ਅਤੇ ਯੋਗਤਾ', od: 'ପ୍ରୋଫାଇଲ୍ ଏବଂ ଯୋଗ୍ୟତା', en: 'Profiles & Eligibility'
  },
  tab_health: {
    hi: 'Family Health', bn: 'Family Health', te: 'Family Health', mr: 'Family Health',
    ta: 'Family Health', gu: 'Family Health', kn: 'Family Health', ml: 'Family Health',
    pa: 'Family Health', od: 'Family Health', en: 'Family Health'
  },
  tab_health_sub: {
    hi: 'टीकाकरण व सलाह', bn: 'টিকাকরণ ও পরামর্শ', te: 'టీకాలు మరియు సలహాలు', mr: 'लसीकरण व सल्ला',
    ta: 'தடுப்பூசி மற்றும் ஆலோசனை', gu: 'રસીકરણ અને સલાહ', kn: 'ಲಸಿಕೆ ಮತ್ತು ಸಲಹೆ', ml: 'പ്രതിരോധ കുത്തിവയ്പ്പും ഉപദേശവും',
    pa: 'ਟੀਕਾਕਰਨ ਅਤੇ ਸਲਾਹ', od: 'ଟିକାକରଣ ଏବଂ ପରାମର୍ଶ', en: 'Immunization & Guidance'
  },
  tab_rem: {
    hi: 'Reminders', bn: 'Reminders', te: 'Reminders', mr: 'Reminders',
    ta: 'Reminders', gu: 'Reminders', kn: 'Reminders', ml: 'Reminders',
    pa: 'Reminders', od: 'Reminders', en: 'Reminders'
  },
  tab_rem_sub: {
    hi: 'अंतिम तिथियां', bn: 'শেষ তারিখসমূহ', te: 'గడువు తేదీలు', mr: 'अंतिम तारखा',
    ta: 'கடைசி தேதிகள்', gu: 'છેલ્લી તારીખો', kn: 'ಕೊನೆಯ ದಿನಾಂಕಗಳು', ml: 'അവസാന തീയതികൾ',
    pa: 'ਆਖਰੀ ਮਿਤੀਆਂ', od: 'ଶେଷ ତାରିଖ', en: 'Deadlines'
  },
  tab_dash: {
    hi: 'Village Hub', bn: 'Village Hub', te: 'Village Hub', mr: 'Village Hub',
    ta: 'Village Hub', gu: 'Village Hub', kn: 'Village Hub', ml: 'Village Hub',
    pa: 'Village Hub', od: 'Village Hub', en: 'Village Hub'
  },
  tab_dash_sub: {
    hi: 'हब स्थिति', bn: 'হাব স্থিতি', te: 'హబ్ స్థితి', mr: 'हब स्थिती',
    ta: 'மைய நிலை', gu: 'હબ સ્થિતિ', kn: 'ಹಬ್ ಸ್ಥಿತಿ', ml: 'ഹബ്ബ് അവസ്ഥ',
    pa: 'ਹੱਬ ਸਥਿਤੀ', od: 'ହବ୍ ସ୍ଥିତି', en: 'Status & Ledger'
  },

  // Opportunities Section
  hdr_opps: {
    hi: 'उपलब्ध सरकारी योजनाएं एवं नौकरियां',
    bn: 'উপলব্ধ সরকারি প্রকল্প ও চাকরি',
    te: 'అందుబాటులో ఉన్న ప్రభుత్వ పథకాలు మరియు ఉద్యోగాలు',
    mr: 'उपलब्ध शासकीय योजना व नोकऱ्या',
    ta: 'கிடைக்கும் அரசு திட்டங்கள் மற்றும் வேலைகள்',
    gu: 'ઉપલબ્ધ સરકારી યોજનાઓ અને નોકરીઓ',
    kn: 'ಲಭ್ಯವಿರುವ ಸರ್ಕಾರಿ ಯೋಜನೆಗಳು ಮತ್ತು ಉದ್ಯೋಗಗಳು',
    ml: 'ലഭ്യമായ സർക്കാർ പദ്ധതികളും ജോലികളും',
    pa: 'ਉਪਲਬਧ ਸਰਕਾਰੀ ਸਕੀਮਾਂ ਅਤੇ ਨੌਕਰੀਆਂ',
    od: 'ଉପଲବ୍ଧ ସରକାରୀ ଯୋଜନା ଏବଂ ଚାକିରି',
    en: 'Available Schemes, Scholarships & Jobs'
  },
  badge_new_avail: {
    hi: '2 New Available', bn: '2 New Available', te: '2 New Available', mr: '2 New Available',
    ta: '2 New Available', gu: '2 New Available', kn: '2 New Available', ml: '2 New Available',
    pa: '2 New Available', od: '2 New Available', en: '2 New Available'
  },
  filter_all: {
    hi: 'All (सभी)', bn: 'All (সব)', te: 'All (అన్నీ)', mr: 'All (सर्व)',
    ta: 'All (அனைத்தும்)', gu: 'All (બધા)', kn: 'All (ಎಲ್ಲವೂ)', ml: 'All (എല്ലാം)',
    pa: 'All (ਸਾਰੇ)', od: 'All (ସବୁ)', en: 'All'
  },
  filter_jobs: {
    hi: 'Jobs (नौकरियां)', bn: 'Jobs (চাকরি)', te: 'Jobs (ఉద్యోగాలు)', mr: 'Jobs (नोकऱ्या)',
    ta: 'Jobs (வேலைகள்)', gu: 'Jobs (નોકરીઓ)', kn: 'Jobs (ಉದ್ಯೋಗಗಳು)', ml: 'Jobs (ജോലികൾ)',
    pa: 'Jobs (ਨੌਕਰੀਆਂ)', od: 'Jobs (ଚାକିରି)', en: 'Jobs'
  },
  filter_trainings: {
    hi: 'Trainings (प्रशिक्षण)', bn: 'Trainings (প্রশিক্ষণ)', te: 'Trainings (శిక్షణ)', mr: 'Trainings (प्रशिक्षण)',
    ta: 'Trainings (பயிற்சி)', gu: 'Trainings (તાલીમ)', kn: 'Trainings (ತರಬೇತಿ)', ml: 'Trainings (പരിശീലനം)',
    pa: 'Trainings (ਸਿਖਲਾਈ)', od: 'Trainings (ପ୍ରଶିକ୍ଷଣ)', en: 'Trainings'
  },
  filter_schemes: {
    hi: 'Schemes (योजनाएं)', bn: 'Schemes (প্রকল্প)', te: 'Schemes (పథకాలు)', mr: 'Schemes (योजना)',
    ta: 'Schemes (திட்டங்கள்)', gu: 'Schemes (યોજનાઓ)', kn: 'Schemes (ಯೋಜನೆಗಳು)', ml: 'Schemes (പദ്ധതികൾ)',
    pa: 'Schemes (ਸਕੀਮਾਂ)', od: 'Schemes (ଯୋଜନା)', en: 'Schemes'
  },
  badge_active: {
    hi: 'सक्रिय ACTIVE', bn: 'সক্রিয় ACTIVE', te: 'సక్రియం ACTIVE', mr: 'सक्रिय ACTIVE',
    ta: 'செயலில் ACTIVE', gu: 'સક્રિય ACTIVE', kn: 'ಸಕ್ರಿಯ ACTIVE', ml: 'സജീവം ACTIVE',
    pa: 'ਚਾਲੂ ACTIVE', od: 'ସକ୍ରିୟ ACTIVE', en: 'ACTIVE'
  },
  lbl_last_date: {
    hi: 'Last Date', bn: 'Last Date', te: 'Last Date', mr: 'Last Date',
    ta: 'Last Date', gu: 'Last Date', kn: 'Last Date', ml: 'Last Date',
    pa: 'Last Date', od: 'Last Date', en: 'Last Date'
  },
  lbl_fee: {
    hi: 'Fee', bn: 'Fee', te: 'Fee', mr: 'Fee',
    ta: 'Fee', gu: 'Fee', kn: 'Fee', ml: 'Fee',
    pa: 'Fee', od: 'Fee', en: 'Fee'
  },
  lbl_source: {
    hi: 'Source', bn: 'Source', te: 'Source', mr: 'Source',
    ta: 'Source', gu: 'Source', kn: 'Source', ml: 'Source',
    pa: 'Source', od: 'Source', en: 'Source'
  },
  btn_check_family: {
    hi: 'Check Family Eligibility', bn: 'Check Family Eligibility', te: 'Check Family Eligibility', mr: 'Check Family Eligibility',
    ta: 'Check Family Eligibility', gu: 'Check Family Eligibility', kn: 'Check Family Eligibility', ml: 'Check Family Eligibility',
    pa: 'Check Family Eligibility', od: 'Check Family Eligibility', en: 'Check Family Eligibility'
  },

  // AI Bottom Bar
  ai_assistant: {
    hi: 'AI Assistant', bn: 'AI Assistant', te: 'AI Assistant', mr: 'AI Assistant',
    ta: 'AI Assistant', gu: 'AI Assistant', kn: 'AI Assistant', ml: 'AI Assistant',
    pa: 'AI Assistant', od: 'AI Assistant', en: 'AI Assistant'
  },
  input_placeholder: {
    hi: 'Ask: can my son apply?',
    bn: 'Ask: can my son apply?',
    te: 'Ask: can my son apply?',
    mr: 'Ask: can my son apply?',
    ta: 'Ask: can my son apply?',
    gu: 'Ask: can my son apply?',
    kn: 'Ask: can my son apply?',
    ml: 'Ask: can my son apply?',
    pa: 'Ask: can my son apply?',
    od: 'Ask: can my son apply?',
    en: 'Ask: can my son apply?'
  },
  btn_ask: {
    hi: 'Ask →', bn: 'Ask →', te: 'Ask →', mr: 'Ask →',
    ta: 'Ask →', gu: 'Ask →', kn: 'Ask →', ml: 'Ask →',
    pa: 'Ask →', od: 'Ask →', en: 'Ask →'
  }
};

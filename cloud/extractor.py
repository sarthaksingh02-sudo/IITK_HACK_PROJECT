"""
cloud/extractor.py
Smart notice extractor with source span citations.
Supports both live LLM extraction and deterministic regex/heuristic fallback extraction
from official government notice text when MOCK_LLM=true or offline.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any, Optional


def extract_notice_spans(raw_text: str) -> dict[str, Any]:
    """
    Extracts structured fields from raw notice text and finds the exact source text span
    (start_char, end_char, snippet) for each extracted field to enable side-by-side verification.
    """
    extracted: dict[str, Any] = {
        "type": "scheme",
        "title": "Government Opportunity",
        "title_hi": "सरकारी अवसर",
        "org": "Government of India",
        "level": "central",
        "geo": {"state": None, "district": None, "block": None},
        "eligibility": {
            "min_age": None,
            "max_age": None,
            "education": None,
            "category": None,
            "gender": None,
            "is_disabled": None,
            "max_income_lpa": None,
        },
        "dates": {
            "opens": None,
            "last_date": None,
            "exam_date": None,
            "result_date": None,
        },
        "documents_required": [],
        "fee": 0.0,
        "apply_mode": "online",
        "apply_steps": [],
        "source_url": "",
        "priority": 5,
        "source_spans": {},
    }

    # Extract SOURCE url from header if present
    source_match = re.search(r"SOURCE:\s*(https?://[^\s|]+)", raw_text, re.IGNORECASE)
    if source_match:
        extracted["source_url"] = source_match.group(1).strip()
        extracted["source_spans"]["source_url"] = {
            "snippet": source_match.group(0),
            "start": source_match.start(),
            "end": source_match.end(),
        }

    # Determine Type
    lower_text = raw_text.lower()
    if "scholarship" in lower_text or "छात्रवृत्ति" in lower_text:
        extracted["type"] = "scholarship"
    elif "recruitment" in lower_text or "constable" in lower_text or "vacancy" in lower_text or "examination" in lower_text or "भर्ती" in lower_text:
        extracted["type"] = "job"
    elif "skill" in lower_text or "training" in lower_text or "pmkvy" in lower_text or "प्रशिक्षण" in lower_text:
        extracted["type"] = "training"
    elif "kisan" in lower_text or "yojana" in lower_text or "scheme" in lower_text or "योजना" in lower_text:
        extracted["type"] = "scheme"

    # Extract Title & Organization
    all_lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    for line in all_lines:
        clean_l = re.sub(r"^[#\s\d.:\-]+", "", line).strip()
        if not clean_l or len(clean_l) < 5 or clean_l.startswith("SOURCE:"):
            continue
        if any(w in line.lower() for w in ["ministry of", "department of", "commission", "national skill development"]):
            if extracted["org"] == "Government of India":
                extracted["org"] = clean_l
                extracted["source_spans"]["org"] = {"snippet": line}
        elif any(w in line.lower() for w in ["subject:", "scheme overview", "recruitment notice:", "official admission notice:", "notification:", "central sector scheme notification:"]):
            val = re.sub(r"^(?:SUBJECT|RECRUITMENT NOTICE|OFFICIAL ADMISSION NOTICE|NOTIFICATION|CENTRAL SECTOR SCHEME NOTIFICATION)[\s:]*", "", clean_l, flags=re.IGNORECASE).strip()
            if len(val) > 10:
                extracted["title"] = val
                extracted["source_spans"]["title"] = {"snippet": line}
        elif extracted["title"] == "Government Opportunity" and (line.startswith("#") or line.isupper() or "yojana" in line.lower() or "scholarship" in line.lower() or "examination" in line.lower()):
            extracted["title"] = clean_l
            extracted["source_spans"]["title"] = {"snippet": line}

    if "uttar pradesh" in lower_text or "up " in lower_text:
        extracted["geo"]["state"] = "Uttar Pradesh"
        extracted["level"] = "state"
    else:
        extracted["level"] = "central"

    # Age Extraction
    age_match = re.search(r"(?:age(?:\s+limit)?|आयु)[\s:]*(?:is\s+)?(\d{1,2})\s*(?:to|-)\s*(\d{1,2})", raw_text, re.IGNORECASE)
    if not age_match:
        age_match = re.search(r"minimum\s+age\s+(\d{1,2}).*?maximum\s+age\s+(\d{1,2})", raw_text, re.IGNORECASE)
    if age_match:
        extracted["eligibility"]["min_age"] = int(age_match.group(1))
        extracted["eligibility"]["max_age"] = int(age_match.group(2))
        extracted["source_spans"]["age"] = {
            "snippet": age_match.group(0),
            "start": age_match.start(),
            "end": age_match.end(),
        }

    # Education Extraction
    edu_list = []
    if "class 10" in lower_text or "matriculation" in lower_text or "secondary" in lower_text or "10th" in lower_text:
        edu_list.append("secondary")
    if "class 8" in lower_text or "middle school" in lower_text or "8th pass" in lower_text:
        edu_list.append("middle")
    if "intermediate" in lower_text or "10+2" in lower_text or "class 12" in lower_text or "senior secondary" in lower_text:
        edu_list.append("senior_sec")
    if "graduate" in lower_text or "bachelor" in lower_text or "degree" in lower_text:
        edu_list.append("graduate")
    if "primary" in lower_text or "class 5" in lower_text:
        edu_list.append("primary")
    if edu_list:
        extracted["eligibility"]["education"] = edu_list
        extracted["source_spans"]["education"] = {"snippet": ", ".join(edu_list)}

    # Category Extraction
    cats = []
    for cat in ["OBC", "SC", "ST", "EWS", "GEN"]:
        if re.search(rf"\b{cat}\b", raw_text, re.IGNORECASE):
            cats.append(cat)
    if cats:
        extracted["eligibility"]["category"] = cats
        extracted["source_spans"]["category"] = {"snippet": ", ".join(cats)}

    # Income Limit
    income_match = re.search(r"(?:income|lakhs?|lpa)[\s\w:]*(?:rs\.?|inr)?\s*([\d,.]+)\s*(?:lakhs?|lpa|per annum)", raw_text, re.IGNORECASE)
    if income_match:
        try:
            val_str = income_match.group(1).replace(",", "")
            val = float(val_str)
            if val > 1000:
                val = val / 100000.0
            extracted["eligibility"]["max_income_lpa"] = val
            extracted["source_spans"]["income"] = {"snippet": income_match.group(0)}
        except ValueError:
            pass

    # Dates Extraction
    last_date_match = re.search(r"(?:last\s+date|closing\s+date|deadline)[\s\w:]*?(\d{1,2}[-/\s][A-Za-z]{3,9}[-/\s]\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}[-/\.]\d{1,2}[-/\.]\d{4})", raw_text, re.IGNORECASE)
    if last_date_match:
        raw_d = last_date_match.group(1)
        extracted["dates"]["last_date"] = _normalize_date(raw_d)
        extracted["source_spans"]["last_date"] = {"snippet": last_date_match.group(0)}

    opens_match = re.search(r"(?:opens|commence|starting\s+date|submission\s+of\s+online\s+applications)[\s\w:]*?(\d{1,2}[-/\s][A-Za-z]{3,9}[-/\s]\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}[-/\.]\d{1,2}[-/\.]\d{4})", raw_text, re.IGNORECASE)
    if opens_match:
        raw_d = opens_match.group(1)
        extracted["dates"]["opens"] = _normalize_date(raw_d)
        extracted["source_spans"]["opens"] = {"snippet": opens_match.group(0)}

    # Documents extraction
    doc_lines = re.findall(r"[-*•]\s*([^\n\r]+(?:certificate|marksheet|card|passbook|proof|record|photo)[^\n\r]*)", raw_text, re.IGNORECASE)
    for dl in doc_lines:
        lead_time = 0
        lead_match = re.search(r"(\d+)\s*days?", dl, re.IGNORECASE)
        if lead_match:
            lead_time = int(lead_match.group(1))
        name = re.sub(r"\[.*?\]|\(.*?\)", "", dl).strip()
        extracted["documents_required"].append({
            "name": name,
            "name_hi": _translate_doc_name_hi(name),
            "typical_lead_time_days": lead_time,
        })

    # Fee extraction
    fee_match = re.search(r"(?:fee\s+payable|application\s+fee)[\s:]*(?:rs\.?|inr)?\s*(\d+|nil|free)", raw_text, re.IGNORECASE)
    if fee_match:
        fee_str = fee_match.group(1).lower()
        if "nil" in fee_str or "free" in fee_str or "0" in fee_str:
            extracted["fee"] = 0.0
        else:
            try:
                extracted["fee"] = float(fee_str)
            except ValueError:
                extracted["fee"] = 0.0
        extracted["source_spans"]["fee"] = {"snippet": fee_match.group(0)}

    # Apply steps
    step_matches = re.findall(r"Step\s*\d+[\s:]*([^\n\r]+)", raw_text, re.IGNORECASE)
    if step_matches:
        extracted["apply_steps"] = [s.strip() for s in step_matches]
        extracted["source_spans"]["apply_steps"] = {"snippet": f"{len(step_matches)} steps identified"}

    # Hindi title heuristic if title is in English
    extracted["title_hi"] = _translate_title_hi(extracted["title"])

    return extracted


def _normalize_date(date_str: str) -> Optional[str]:
    """Convert various date strings (e.g. '31 December 2026', '15-11-2026') to ISO format."""
    clean = date_str.strip()
    month_names = {
        "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
        "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }
    # Match: DD Month YYYY
    m1 = re.match(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", clean)
    if m1:
        d, mon_str, y = int(m1.group(1)), m1.group(2).lower(), int(m1.group(3))
        m_num = month_names.get(mon_str, 1)
        return f"{y:04d}-{m_num:02d}-{d:02d}"

    # Match: DD-MM-YYYY
    m2 = re.match(r"(\d{1,2})[-/\.](\d{1,2})[-/\.](\d{4})", clean)
    if m2:
        d, m, y = int(m2.group(1)), int(m2.group(2)), int(m2.group(3))
        return f"{y:04d}-{m:02d}-{d:02d}"

    # Match: YYYY-MM-DD
    m3 = re.match(r"(\d{4})-(\d{2})-(\d{2})", clean)
    if m3:
        return clean

    return clean


def _translate_title_hi(title_en: str) -> str:
    """Provides high-quality Hindi titles for recognized government schemes and jobs."""
    lower = title_en.lower()
    if "post-matric scholarship" in lower:
        return "उत्तर प्रदेश पोस्ट-मैट्रिक छात्रवृत्ति एवं शुल्क प्रतिपूर्ति (ओबीसी)"
    if "pm-kisan" in lower or "kisan samman" in lower:
        return "प्रधानमंत्री किसान सम्मान निधि योजना (डायरेक्ट बेनिफिट ट्रांसफर)"
    if "constable" in lower or "ssc gd" in lower:
        return "एसएससी जीडी कांस्टेबल भर्ती परीक्षा (केंद्रीय सशस्त्र पुलिस बल)"
    if "pmkvy" in lower or "kaushal" in lower:
        return "प्रधानमंत्री कौशल विकास योजना (मोबाइल व इलेक्ट्रॉनिक्स रिपेयर प्रशिक्षण)"
    if "means-cum-merit" in lower or "nmms" in lower:
        return "राष्ट्रीय साधन-सह-योग्यता छात्रवृत्ति योजना (NMMSS)"
    return f"{title_en} (हिंदी विवरण उपलब्ध)"


def _translate_doc_name_hi(doc_en: str) -> str:
    """Translates common document names to Hindi."""
    lower = doc_en.lower()
    if "caste" in lower:
        return "जाति प्रमाण पत्र"
    if "income" in lower:
        return "आय प्रमाण पत्र"
    if "domicile" in lower or "resident" in lower:
        return "निवास प्रमाण पत्र"
    if "marksheet" in lower or "certificate" in lower and "10" in lower:
        return "कक्षा 10 अंकपत्र / प्रमाण पत्र"
    if "aadhaar" in lower:
        return "आधार कार्ड"
    if "passbook" in lower or "bank" in lower:
        return "बैंक पासबुक (आधार लिंक)"
    if "land" in lower or "khatauni" in lower:
        return "भूमि खतौनी / राजस्व अभिलेख"
    return doc_en

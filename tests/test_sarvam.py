"""
tests/test_sarvam.py
Test suite for Sarvam AI 9 Indian Languages + English integration.
Validates:
  - Canonical language mappings for all 10 languages (9 Indian + English).
  - BCP-47 tag resolution.
  - Multi-language text translation across all 10 languages.
  - Hub and Cloud REST endpoints /api/languages and /api/translate.
"""

import pytest
from fastapi.testclient import TestClient

from cloud.main import app as cloud_app
from hub.main import app as hub_app
from shared.sarvam_client import (
    SARVAM_LANGUAGES,
    get_sarvam_bcp47,
    translate_with_sarvam,
)


class TestSarvamIntegration:
    def test_sarvam_languages_registry(self):
        """Validates all 9 Indian languages + English are present."""
        expected_langs = ["hi", "bn", "te", "mr", "ta", "gu", "kn", "ml", "pa", "od", "en"]
        for lang in expected_langs:
            assert lang in SARVAM_LANGUAGES
            assert "code" in SARVAM_LANGUAGES[lang]
            assert "name" in SARVAM_LANGUAGES[lang]
            assert "native" in SARVAM_LANGUAGES[lang]

    def test_bcp47_resolution(self):
        """Verifies BCP-47 normalization."""
        assert get_sarvam_bcp47("hi") == "hi-IN"
        assert get_sarvam_bcp47("bn-IN") == "bn-IN"
        assert get_sarvam_bcp47("te") == "te-IN"
        assert get_sarvam_bcp47("mr") == "mr-IN"
        assert get_sarvam_bcp47("ta") == "ta-IN"
        assert get_sarvam_bcp47("gu") == "gu-IN"
        assert get_sarvam_bcp47("kn") == "kn-IN"
        assert get_sarvam_bcp47("ml") == "ml-IN"
        assert get_sarvam_bcp47("pa") == "pa-IN"
        assert get_sarvam_bcp47("od") == "od-IN"
        assert get_sarvam_bcp47("en") == "en-IN"
        assert get_sarvam_bcp47("unknown") == "en-IN"

    def test_multilingual_translation_for_all_nine_languages(self):
        """Tests translation output for core UI strings across all 9 Indian languages."""
        indian_langs = ["hi", "bn", "te", "mr", "ta", "gu", "kn", "ml", "pa", "od"]
        
        for lang in indian_langs:
            # Check dictionary phrase translation
            trans_opp = translate_with_sarvam("tab_opportunities", target_lang=lang)
            assert trans_opp is not None
            assert len(trans_opp) > 0
            assert trans_opp != "tab_opportunities"

            # Check status translation
            trans_elig = translate_with_sarvam("status_eligible", target_lang=lang)
            assert "ELIGIBLE" in trans_elig or len(trans_elig) > 0

            # Check pathway label translation
            trans_pathway = translate_with_sarvam("pathway_label", target_lang=lang)
            assert len(trans_pathway) > 0

            # Check scheme title fallback
            trans_title = translate_with_sarvam("UP Post-Matric Scholarship", target_lang=lang)
            assert len(trans_title) > 0

    def test_cloud_languages_and_translate_endpoint(self):
        client = TestClient(cloud_app)
        # Test /api/languages
        res = client.get("/api/languages")
        assert res.status_code == 200
        langs = res.json()["languages"]
        assert len(langs) >= 10
        assert "hi" in langs
        assert "bn" in langs
        assert "te" in langs

        # Test /api/translate
        res_tr = client.post("/api/translate", json={"text": "tab_opportunities", "target_lang": "hi"})
        assert res_tr.status_code == 200
        data = res_tr.json()
        assert data["translated"] == "योजनाएं एवं अवसर"
        assert data["engine"] == "sarvam-ai"

    def test_hub_languages_and_translate_endpoint(self):
        client = TestClient(hub_app)
        # Test /api/languages
        res = client.get("/api/languages")
        assert res.status_code == 200
        langs = res.json()["languages"]
        assert len(langs) >= 10

        # Test /api/translate
        for lang in ["bn", "te", "mr", "ta", "gu", "kn", "ml", "pa", "od"]:
            res_tr = client.post("/api/translate", json={"text": "tab_opportunities", "target_lang": lang})
            assert res_tr.status_code == 200
            assert res_tr.json()["translated"] != ""
            assert res_tr.json()["engine"] == "sarvam-ai"

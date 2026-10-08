"""
Tests for shared/packet.py — sign, verify, tamper detection, serialisation.

Run with:  pytest shared/tests/test_packet.py -v
"""

import json

import nacl.signing
import pytest

from shared.packet import (
    build_and_sign,
    packet_from_bytes,
    packet_from_json,
    packet_to_bytes,
    packet_to_json,
    verify_packet,
)
from shared.schemas import Geo, PacketKind, Topic


@pytest.fixture
def keypair():
    sk = nacl.signing.SigningKey.generate()
    vk = sk.verify_key
    return sk, vk


@pytest.fixture
def sample_packet(keypair):
    sk, _ = keypair
    return build_and_sign(
        payload={"title": "Test Opportunity [SAMPLE]", "id": "opp-001"},
        kind=PacketKind.opportunity,
        signing_key=sk,
        topic=Topic.education,
        geo=Geo(state="UP", district="Varanasi"),
        language="hi",
        priority=7,
    )


class TestSignAndVerify:
    def test_signature_present(self, sample_packet):
        assert sample_packet.signature is not None
        assert len(sample_packet.signature) == 128  # 64 bytes hex

    def test_verify_valid_packet(self, sample_packet, keypair):
        _, vk = keypair
        assert verify_packet(sample_packet, vk) is True

    def test_verify_wrong_key(self, sample_packet):
        other_sk = nacl.signing.SigningKey.generate()
        other_vk = other_sk.verify_key
        assert verify_packet(sample_packet, other_vk) is False

    def test_verify_no_signature(self, sample_packet, keypair):
        _, vk = keypair
        sample_packet.signature = None
        assert verify_packet(sample_packet, vk) is False

    def test_verify_tampered_payload(self, sample_packet, keypair):
        _, vk = keypair
        # Tamper with payload after signing
        sample_packet.payload["title"] = "TAMPERED"
        assert verify_packet(sample_packet, vk) is False

    def test_verify_tampered_priority(self, sample_packet, keypair):
        _, vk = keypair
        sample_packet.priority = 1
        assert verify_packet(sample_packet, vk) is False


class TestSerialization:
    def test_roundtrip_json(self, sample_packet, keypair):
        _, vk = keypair
        raw = packet_to_json(sample_packet)
        recovered = packet_from_json(raw)
        assert recovered.id == sample_packet.id
        assert recovered.signature == sample_packet.signature
        assert verify_packet(recovered, vk) is True

    def test_roundtrip_bytes(self, sample_packet, keypair):
        _, vk = keypair
        raw = packet_to_bytes(sample_packet)
        recovered = packet_from_bytes(raw)
        assert verify_packet(recovered, vk) is True

    def test_json_is_valid_json(self, sample_packet):
        raw = packet_to_json(sample_packet)
        parsed = json.loads(raw)
        assert "signature" in parsed
        assert "payload" in parsed

    def test_packet_id_preserved(self, keypair):
        sk, _ = keypair
        packet = build_and_sign(
            payload={"x": 1},
            kind=PacketKind.alert,
            signing_key=sk,
            packet_id="my-custom-id",
        )
        assert packet.id == "my-custom-id"


class TestPacketFields:
    def test_geo_fields(self, sample_packet):
        assert sample_packet.geo.state == "UP"
        assert sample_packet.geo.district == "Varanasi"

    def test_kind_and_topic(self, sample_packet):
        assert sample_packet.kind == PacketKind.opportunity
        assert sample_packet.topic == Topic.education

    def test_priority_range(self, keypair):
        sk, _ = keypair
        packet = build_and_sign(
            payload={}, kind=PacketKind.update, signing_key=sk, priority=3
        )
        assert packet.priority == 3

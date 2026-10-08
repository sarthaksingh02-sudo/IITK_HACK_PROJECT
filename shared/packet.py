"""
shared/packet.py
Ed25519 packet signing and verification using PyNaCl.

Sign:   build_and_sign(payload_dict, kind, ..., signing_key) -> Packet
Verify: verify_packet(packet) -> bool
"""

from __future__ import annotations

import json
import pathlib
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import nacl.encoding
import nacl.exceptions
import nacl.signing

from shared.schemas import Geo, Packet, PacketKind, Topic


# ── Canonical serialisation ───────────────────────────────────────────────────

def _canonical(data: dict[str, Any]) -> bytes:
    """
    Deterministic JSON encoding for signing.
    Keys sorted, no extra whitespace, UTF-8.
    """
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _packet_to_signable(packet: Packet) -> bytes:
    """Return canonical bytes of all fields EXCEPT 'signature'."""
    d = packet.model_dump(mode="json", exclude={"signature"})
    return _canonical(d)


def ensure_keys(private_path: str = "keys/private.key", public_path: str = "keys/public.key") -> tuple[nacl.signing.SigningKey, nacl.signing.VerifyKey]:
    """Ensures Ed25519 keypair exists on disk, generating new ones if missing."""
    priv_file = pathlib.Path(private_path)
    pub_file = pathlib.Path(public_path)
    priv_file.parent.mkdir(parents=True, exist_ok=True)

    if not priv_file.exists() or not pub_file.exists():
        sk = nacl.signing.SigningKey.generate()
        priv_file.write_bytes(bytes(sk))
        pub_file.write_bytes(bytes(sk.verify_key))
        return sk, sk.verify_key

    sk = nacl.signing.SigningKey(priv_file.read_bytes())
    vk = nacl.signing.VerifyKey(pub_file.read_bytes())
    return sk, vk


def load_signing_key(path: str = "keys/private.key") -> nacl.signing.SigningKey:
    """Load an Ed25519 signing key from a raw 32-byte file (auto-generating if missing)."""
    p = pathlib.Path(path)
    if not p.exists():
        sk, _ = ensure_keys(private_path=path)
        return sk
    return nacl.signing.SigningKey(p.read_bytes())


def load_verify_key(path: str = "keys/public.key") -> nacl.signing.VerifyKey:
    """Load an Ed25519 verify key from a raw 32-byte file (auto-generating if missing)."""
    p = pathlib.Path(path)
    if not p.exists():
        _, vk = ensure_keys(public_path=path)
        return vk
    return nacl.signing.VerifyKey(p.read_bytes())


def get_verify_key_from_signing_key(sk: nacl.signing.SigningKey) -> nacl.signing.VerifyKey:
    return sk.verify_key


# ── Build and sign ────────────────────────────────────────────────────────────

def build_and_sign(
    *,
    payload: dict[str, Any],
    kind: PacketKind,
    signing_key: nacl.signing.SigningKey,
    topic: Optional[Topic] = None,
    geo: Optional[Geo] = None,
    language: str = "hi",
    priority: int = 5,
    valid_until: Optional[datetime] = None,
    version: int = 1,
    packet_id: Optional[str] = None,
) -> Packet:
    """
    Construct and sign a Packet.
    Returns the Packet with the 'signature' field set to a hex string.
    """
    packet = Packet(
        id=packet_id or str(uuid.uuid4()),
        kind=kind,
        topic=topic,
        geo=geo or Geo(),
        language=language,
        priority=priority,
        valid_until=valid_until,
        version=version,
        payload=payload,
        signature=None,
    )

    signable = _packet_to_signable(packet)
    signed = signing_key.sign(signable)
    # signed.signature is raw 64-byte Ed25519 sig
    packet.signature = signed.signature.hex()
    return packet


# ── Verify ────────────────────────────────────────────────────────────────────

def verify_packet(packet: Packet, verify_key: nacl.signing.VerifyKey) -> bool:
    """
    Returns True if the packet signature is valid.
    Returns False (never raises) so calling code can log and discard bad packets.
    """
    if not packet.signature:
        return False
    try:
        sig_bytes = bytes.fromhex(packet.signature)
        message = _packet_to_signable(packet)
        verify_key.verify(message, sig_bytes)
        return True
    except (nacl.exceptions.BadSignatureError, ValueError):
        return False


# ── Serialise / deserialise ───────────────────────────────────────────────────

def packet_to_json(packet: Packet) -> str:
    return packet.model_dump_json()


def packet_from_json(raw: str | bytes) -> Packet:
    return Packet.model_validate_json(raw)


def packet_to_bytes(packet: Packet) -> bytes:
    return packet_to_json(packet).encode("utf-8")


def packet_from_bytes(data: bytes) -> Packet:
    return packet_from_json(data)


bytes_to_packet = packet_from_bytes

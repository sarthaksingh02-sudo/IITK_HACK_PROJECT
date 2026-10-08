"""
hub/transport/file_transport.py
FileTransport — watches the packets/ folder to simulate receiving Tier 0 radio broadcast packets.
Verifies Ed25519 signatures, logs to packet_ledger, and ingests payloads into the SQLite DB.
"""

from __future__ import annotations

import json
import os
import pathlib
from datetime import datetime, timezone
from typing import Callable, Optional

from shared.packet import bytes_to_packet, load_verify_key, verify_packet
from shared.schemas import Opportunity, Packet, PacketKind, Topic
from hub.db import HubOpportunity, HubUpdate, PacketLedger, SessionLocal

PUBLIC_KEY_PATH = os.getenv("PUBLIC_KEY_PATH", "keys/public.key")
PACKETS_DIR = pathlib.Path(os.getenv("PACKETS_DIR", "./packets"))


class FileTransport:
    def __init__(self, packets_dir: Optional[pathlib.Path] = None, public_key_path: Optional[str] = None):
        self.packets_dir = packets_dir or PACKETS_DIR
        self.public_key_path = public_key_path or PUBLIC_KEY_PATH
        self.vk = load_verify_key(self.public_key_path)

    def scan_and_ingest_all(self) -> int:
        """
        Scans packets/ directory for all .packet files, verifies signatures,
        and saves new packets to the database.
        Returns the count of newly ingested packets.
        """
        if not self.packets_dir.exists():
            return 0

        packet_files = sorted(self.packets_dir.glob("*.packet"))
        new_count = 0
        db = SessionLocal()
        now = datetime.now(timezone.utc).isoformat()

        try:
            for pfile in packet_files:
                raw_bytes = pfile.read_bytes()
                try:
                    packet = bytes_to_packet(raw_bytes)
                except Exception as e:
                    print(f"[file_transport] Failed to parse {pfile.name}: {e}")
                    continue

                # Check if already processed in ledger
                existing = db.get(PacketLedger, packet.id)
                if existing and existing.verified == 1:
                    continue

                # Verify Ed25519 signature
                is_valid = verify_packet(packet, self.vk)
                if not is_valid:
                    print(f"[file_transport] REJECTED: Invalid signature on packet {packet.id}")
                    ledger_entry = PacketLedger(packet_id=packet.id, received_at=now, verified=0)
                    db.merge(ledger_entry)
                    db.commit()
                    continue

                # Signature is VALID — store in DB
                ledger_entry = PacketLedger(packet_id=packet.id, received_at=now, verified=1)
                db.merge(ledger_entry)

                payload = packet.payload
                if packet.kind == PacketKind.opportunity:
                    geo = payload.get("geo") or {}
                    opp = HubOpportunity(
                        id=payload["id"],
                        type=payload.get("type", "scheme"),
                        title=payload.get("title", "Untitled"),
                        title_hi=payload.get("title_hi"),
                        org=payload.get("org"),
                        level=payload.get("level"),
                        geo_state=geo.get("state"),
                        geo_district=geo.get("district"),
                        geo_block=geo.get("block"),
                        eligibility_json=json.dumps(payload.get("eligibility", {})),
                        dates_json=json.dumps(payload.get("dates", {})),
                        documents_json=json.dumps(payload.get("documents_required", [])),
                        fee=payload.get("fee"),
                        apply_mode=payload.get("apply_mode"),
                        apply_steps_json=json.dumps(payload.get("apply_steps", [])),
                        source_url=payload.get("source_url", "https://gov.in"),
                        last_verified=payload.get("last_verified"),
                        priority=payload.get("priority", 5),
                        valid_until=payload.get("valid_until"),
                        synced_at=now,
                        is_sample=payload.get("is_sample", False),
                    )
                    db.merge(opp)
                    new_count += 1
                    print(f"[file_transport] INGESTED Opportunity: '{opp.title}' (ID: {opp.id})")

                elif packet.kind == PacketKind.update:
                    update_entry = HubUpdate(
                        id=packet.id,
                        topic=packet.topic.value if hasattr(packet.topic, "value") else str(packet.topic),
                        title=payload.get("title", "Regional Update"),
                        title_hi=payload.get("title_hi"),
                        body=payload.get("body"),
                        body_hi=payload.get("body_hi"),
                        geo_state=packet.geo.state if packet.geo else None,
                        geo_district=packet.geo.district if packet.geo else None,
                        priority=packet.priority,
                        valid_until=packet.valid_until,
                        published_at=packet.published_at,
                    )
                    db.merge(update_entry)
                    new_count += 1
                    print(f"[file_transport] INGESTED Regional Update: '{update_entry.title}'")

                db.commit()
        finally:
            db.close()

        return new_count

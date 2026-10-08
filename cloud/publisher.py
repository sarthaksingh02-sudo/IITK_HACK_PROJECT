"""
cloud/publisher.py
Build signed packets from approved opportunities and write them to the packets/ folder.
"""

from __future__ import annotations

import json
import os
import pathlib
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

from shared.packet import build_and_sign, load_signing_key, packet_to_bytes
from shared.schemas import Geo, PacketKind, Topic

PACKETS_DIR = pathlib.Path(os.getenv("PACKETS_DIR", "./packets"))
PRIVATE_KEY_PATH = os.getenv("PRIVATE_KEY_PATH", "keys/private.key")


def publish_opportunity_packet(opportunity_dict: dict) -> pathlib.Path:
    """
    Sign and write an opportunity packet to PACKETS_DIR.
    Returns the path to the written .packet file.
    """
    PACKETS_DIR.mkdir(parents=True, exist_ok=True)
    sk = load_signing_key(PRIVATE_KEY_PATH)

    geo_data = opportunity_dict.get("geo") or {}
    geo = Geo(
        state=geo_data.get("state"),
        district=geo_data.get("district"),
        block=geo_data.get("block"),
    )

    packet = build_and_sign(
        payload=opportunity_dict,
        kind=PacketKind.opportunity,
        signing_key=sk,
        topic=Topic.education,  # caller may override
        geo=geo,
        language=opportunity_dict.get("language", "hi"),
        priority=opportunity_dict.get("priority", 5),
    )

    filename = PACKETS_DIR / f"{packet.id}.packet"
    filename.write_bytes(packet_to_bytes(packet))
    print(f"[publisher] Written: {filename}")
    return filename


def publish_update_packet(update_dict: dict, topic: Topic = Topic.general) -> pathlib.Path:
    """Sign and write a regional update packet."""
    PACKETS_DIR.mkdir(parents=True, exist_ok=True)
    sk = load_signing_key(PRIVATE_KEY_PATH)

    geo_data = update_dict.get("geo") or {}
    geo = Geo(
        state=geo_data.get("state"),
        district=geo_data.get("district"),
        block=geo_data.get("block"),
    )

    packet = build_and_sign(
        payload=update_dict,
        kind=PacketKind.update,
        signing_key=sk,
        topic=topic,
        geo=geo,
        language=update_dict.get("language", "hi"),
        priority=update_dict.get("priority", 5),
    )

    filename = PACKETS_DIR / f"{packet.id}.packet"
    filename.write_bytes(packet_to_bytes(packet))
    print(f"[publisher] Written: {filename}")
    return filename

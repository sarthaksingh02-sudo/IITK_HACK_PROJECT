"""
hub/transport/http_sync.py
HttpSyncTransport — Tier 2 two-way sync with the cloud.
Used when internet is available. Downloads new packets from cloud,
uploads queued outbox records.
Phase 0: stub only. Implemented in Phase 6.
"""

from __future__ import annotations

from loguru import logger

from hub.transport.base import Transport


class HttpSyncTransport(Transport):
    """
    Two-way HTTP sync transport (Tier 2).
    [STUB — Phase 6]
    """

    @property
    def name(self) -> str:
        return "HttpSyncTransport (Tier 2, two-way)"

    def start(self) -> None:
        logger.info("[HttpSyncTransport] [STUB] Not yet implemented. Phase 6.")

    def stop(self) -> None:
        logger.info("[HttpSyncTransport] [STUB] Stopped.")

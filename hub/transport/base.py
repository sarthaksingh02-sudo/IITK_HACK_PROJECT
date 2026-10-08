"""
hub/transport/base.py
Abstract Transport interface.
All transports must implement:
  - start() — begin listening / polling
  - stop() — clean shutdown
  - on_packet(callback) — register callback(packet: Packet) -> None
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable

from shared.schemas import Packet


class Transport(ABC):
    """Pluggable packet transport interface."""

    def __init__(self):
        self._callback: Callable[[Packet], None] | None = None

    def on_packet(self, callback: Callable[[Packet], None]) -> None:
        """Register callback to be called when a valid, verified packet arrives."""
        self._callback = callback

    def _dispatch(self, packet: Packet) -> None:
        if self._callback:
            self._callback(packet)

    @abstractmethod
    def start(self) -> None:
        """Start listening/polling for packets."""
        ...

    @abstractmethod
    def stop(self) -> None:
        """Stop transport cleanly."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable transport name for logging."""
        ...

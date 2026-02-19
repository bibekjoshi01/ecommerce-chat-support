from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from app.infra.realtime.events import RealtimeEvent


class RealtimePublisher(Protocol):
    async def publish(
        self,
        channels: Sequence[str],
        event: RealtimeEvent,
        payload: Mapping[str, Any],
    ) -> None: ...


class NoopRealtimePublisher:
    async def publish(
        self,
        channels: Sequence[str],
        event: RealtimeEvent,
        payload: Mapping[str, Any],
    ) -> None:
        _ = channels
        _ = event
        _ = payload
        return None

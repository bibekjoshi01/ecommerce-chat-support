import asyncio
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from app.infra.realtime.events import RealtimeEvent


class InMemoryRealtimeHub:
    """In-process channel hub for websocket fanout."""

    def __init__(self) -> None:
        self._channel_subscribers: dict[str, set[WebSocket]] = defaultdict(set)
        self._socket_channels: dict[WebSocket, set[str]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()

    def subscriber_count(self, channel: str) -> int:
        subscribers = self._channel_subscribers.get(channel)
        if subscribers is None:
            return 0
        return len(subscribers)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            channels = self._socket_channels.pop(websocket, set())
            for channel in channels:
                subscribers = self._channel_subscribers.get(channel)
                if subscribers is None:
                    continue
                subscribers.discard(websocket)
                if not subscribers:
                    self._channel_subscribers.pop(channel, None)

    async def subscribe(self, websocket: WebSocket, channel: str) -> None:
        async with self._lock:
            self._channel_subscribers[channel].add(websocket)
            self._socket_channels[websocket].add(channel)

    async def unsubscribe(self, websocket: WebSocket, channel: str) -> None:
        async with self._lock:
            subscribers = self._channel_subscribers.get(channel)
            if subscribers is not None:
                subscribers.discard(websocket)
                if not subscribers:
                    self._channel_subscribers.pop(channel, None)

            channels = self._socket_channels.get(websocket)
            if channels is not None:
                channels.discard(channel)
                if not channels:
                    self._socket_channels.pop(websocket, None)

    async def publish(
        self,
        channels: Sequence[str],
        event: RealtimeEvent,
        payload: Mapping[str, Any],
    ) -> None:
        unique_channels = [channel for channel in dict.fromkeys(channels) if channel]
        if not unique_channels:
            return

        async with self._lock:
            recipients_by_channel = {
                channel: set(self._channel_subscribers.get(channel, set()))
                for channel in unique_channels
            }

        for channel, recipients in recipients_by_channel.items():
            if not recipients:
                continue

            envelope = {
                "event": event.value,
                "channel": channel,
                "payload": dict(payload),
                "sent_at": datetime.now(UTC).isoformat(),
            }

            stale: list[WebSocket] = []
            for websocket in recipients:
                try:
                    await websocket.send_json(envelope)
                except (RuntimeError, WebSocketDisconnect):
                    stale.append(websocket)

            if stale:
                async with self._lock:
                    for websocket in stale:
                        subscribed_channels = self._socket_channels.get(websocket, set())
                        subscribed_channels.discard(channel)
                        if not subscribed_channels:
                            self._socket_channels.pop(websocket, None)

                        channel_subscribers = self._channel_subscribers.get(channel)
                        if channel_subscribers is not None:
                            channel_subscribers.discard(websocket)
                            if not channel_subscribers:
                                self._channel_subscribers.pop(channel, None)

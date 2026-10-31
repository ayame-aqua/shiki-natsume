"""已连接的网页聊天套接字，供桌宠主动句复用同一套帧。"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ChatHub:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()

    def add(self, websocket: WebSocket) -> None:
        self._clients.add(websocket)

    def discard(self, websocket: WebSocket) -> None:
        self._clients.discard(websocket)

    def client_count(self) -> int:
        return len(self._clients)

    async def broadcast_json(self, payload: dict[str, Any]) -> None:
        stale: list[WebSocket] = []
        for websocket in self._clients:
            try:
                await websocket.send_json(payload)
            except Exception:
                logger.exception("chat hub broadcast failed")
                stale.append(websocket)
        for websocket in stale:
            self._clients.discard(websocket)

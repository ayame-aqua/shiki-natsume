"""短期会话上下文（进程内）。"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class Turn:
    role: str
    text: str
    emotion: str | None = None
    speech_ja: str | None = None


@dataclass
class SessionStore:
    max_turns: int = 20
    _turns: dict[str, list[Turn]] = field(default_factory=dict)
    _last_activity: dict[str, float] = field(default_factory=dict)

    def history(self, chat_id: str) -> list[Turn]:
        return list(self._turns.get(chat_id, []))

    def append(self, chat_id: str, turn: Turn) -> None:
        bucket = self._turns.setdefault(chat_id, [])
        bucket.append(turn)
        overflow = len(bucket) - self.max_turns
        if overflow > 0:
            del bucket[:overflow]
        self._last_activity[chat_id] = time.time()

    def last_activity_time(self, chat_id: str) -> float | None:
        """返回指定会话的最后活动时间戳（秒），无活动返回 None。"""
        return self._last_activity.get(chat_id)

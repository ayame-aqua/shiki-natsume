"""主动搭话判定与 HTTP 门闩。"""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient
from src.config import load_config
from src.core.agent import Agent
from src.core.llm import LLMError
from src.core.proactive import (
    REASON_COOLDOWN,
    REASON_DISABLED,
    REASON_DND,
    REASON_NOT_IDLE,
    decide_proactive,
)
from src.core.session import SessionStore, Turn
from src.core.types import InboundMessage
from src.main import create_app
from src.memory.store import MemoryStore
from tests.test_agent import PERSONA


class FakeLLM:
    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
        self.calls: list[list[dict[str, str]]] = []

    async def chat(self, messages: list[dict[str, str]]) -> str:
        self.calls.append(messages)
        if not self._replies:
            raise LLMError("empty script")
        return self._replies.pop(0)


def _settings(**proactive: object) -> dict:
    settings = load_config()
    block = {
        "enabled": True,
        "idle_timeout_s": 300,
        "cooldown_s": 600,
        "do_not_disturb": False,
    }
    block.update(proactive)
    settings["proactive"] = block
    return settings


def test_decide_proactive_gates() -> None:
    now = 1_000.0
    assert (
        decide_proactive(
            enabled=False,
            do_not_disturb=False,
            now=now,
            last_activity=None,
            started_at=now - 1_000,
            last_proactive=0.0,
        ).reason
        == REASON_DISABLED
    )
    assert (
        decide_proactive(
            enabled=True,
            do_not_disturb=True,
            now=now,
            last_activity=None,
            started_at=now - 1_000,
            last_proactive=0.0,
        ).reason
        == REASON_DND
    )
    assert (
        decide_proactive(
            enabled=True,
            do_not_disturb=False,
            now=now,
            last_activity=now - 10,
            started_at=now - 1_000,
            last_proactive=0.0,
        ).reason
        == REASON_NOT_IDLE
    )
    assert (
        decide_proactive(
            enabled=True,
            do_not_disturb=False,
            now=now,
            last_activity=now - 400,
            started_at=now - 1_000,
            last_proactive=now - 10,
        ).reason
        == REASON_COOLDOWN
    )
    allowed = decide_proactive(
        enabled=True,
        do_not_disturb=False,
        now=now,
        last_activity=now - 400,
        started_at=now - 1_000,
        last_proactive=0.0,
    )
    assert allowed.allowed is True


def test_proactive_status_and_dnd() -> None:
    app = create_app(_settings())
    client = TestClient(app)
    status = client.get("/api/proactive/status")
    assert status.status_code == 200
    body = status.json()
    assert body["enabled"] is True
    assert body["do_not_disturb"] is False
    assert body["idle_timeout_s"] == 300

    bad = client.post("/api/proactive/dnd", json={"enabled": "yes"})
    assert bad.status_code == 400
    ok = client.post("/api/proactive/dnd", json={"enabled": True})
    assert ok.status_code == 200
    assert ok.json()["do_not_disturb"] is True
    blocked = client.post("/api/proactive/trigger")
    assert blocked.status_code == 200
    assert blocked.json() == {"triggered": False, "reason": "do_not_disturb"}


def test_proactive_disabled_and_not_idle() -> None:
    disabled = TestClient(create_app(_settings(enabled=False)))
    assert disabled.post("/api/proactive/trigger").json()["reason"] == "disabled"

    app = create_app(_settings(idle_timeout_s=300))
    app.state.sessions.append("web:local", Turn(role="user", text="在吗"))
    client = TestClient(app)
    assert client.post("/api/proactive/trigger").json()["reason"] == "not_idle_yet"


class _BroadcastAgent:
    async def run(self, inbound: InboundMessage) -> object:
        from src.core.types import OutboundMessage

        return OutboundMessage(
            message_id="proactive-1",
            reply_to_id=inbound.message_id,
            chat_id=inbound.chat_id,
            texts=["还在吗"],
            speech_ja=None,
        )


def test_proactive_broadcasts_assistant_text() -> None:
    app = create_app(_settings(idle_timeout_s=1, cooldown_s=1))
    app.state.started_at = 0.0
    app.state.gateway.agent = _BroadcastAgent()  # type: ignore[assignment]
    client = TestClient(app)
    with client.websocket_connect("/ws/chat") as websocket:
        result = client.post("/api/proactive/trigger")
        body = result.json()
        assert body["triggered"] is True
        assert body["texts"] == ["还在吗"]
        frame = websocket.receive_json()
        assert frame["type"] == "assistant_text"
        assert frame["texts"] == ["还在吗"]
        idle = websocket.receive_json()
        assert idle == {"type": "status", "message_id": "proactive-1", "state": "idle"}


def test_agent_system_inbound_skips_user_turn() -> None:
    llm = FakeLLM(
        [
            '还在吗\n\n[[natsume]]\n{"emotion":"neutral","silent":false,"memory_candidates":[]}',
            "まだいる？",
        ]
    )
    sessions = SessionStore(max_turns=40)
    agent = Agent(
        persona_path=str(PERSONA),
        llm=llm,  # type: ignore[arg-type]
        sessions=sessions,
        memory=MemoryStore(),
    )
    inbound = InboundMessage(
        message_id="sys-1",
        channel="web",
        chat_type="system",
        chat_id="web:local",
        sender_id="system",
        sender_name="system",
        text="对方已经一段时间没有理你。请按人设主动开口。",
    )
    outbound = asyncio.run(agent.run(inbound))
    history = sessions.history("web:local")
    assert [turn.role for turn in history] == ["assistant"]
    assert history[0].text == "还在吗"
    assert outbound.texts == ["还在吗"]
    user_contents = [item["content"] for item in llm.calls[0] if item["role"] == "user"]
    assert inbound.text not in user_contents

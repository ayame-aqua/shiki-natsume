"""P5-S4 截屏黑名单、see_screen、识图提示。"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from src.config import load_config
from src.core.llm import LLMError
from src.core.policy.local import generate_proactive_prompt
from src.main import create_app
from src.vision.blacklist import is_capture_blocked
from src.vision.constants import SCENE_WORK
from src.vision.foreground import ForegroundInfo
from src.vision.see_screen import see_screen


def _info(title: str, process: str, *, is_self: bool = False) -> ForegroundInfo:
    scene = "self" if is_self else SCENE_WORK
    return ForegroundInfo(title=title, process=process, scene=scene, is_self=is_self)


def test_blacklist_blocks_password_manager() -> None:
    assert is_capture_blocked(_info("Vault", "KeePassXC.exe")) is True


def test_blacklist_blocks_payment_title() -> None:
    assert is_capture_blocked(_info("支付宝 - 支付", "msedge.exe")) is True


def test_blacklist_allows_normal_work() -> None:
    assert is_capture_blocked(_info("main.py - Cursor", "Cursor.exe")) is False


def test_qq_channel_cannot_see_screen() -> None:
    sight = asyncio.run(see_screen(None, channel="qq"))
    assert sight.blocked is True
    assert sight.reason == "qq_forbidden"
    assert sight.description is None


def test_paused_skips_capture() -> None:
    sight = asyncio.run(see_screen(None, paused=True, use_screenshot=True))
    assert sight.paused is True
    assert sight.reason == "paused"


def test_see_screen_describes_when_allowed() -> None:
    llm = AsyncMock()
    llm.describe_image = AsyncMock(return_value="编辑器里开着一段 Python 代码")
    info = _info("main.py - Cursor", "Cursor.exe")
    with patch("src.vision.see_screen.capture_screen_jpeg", return_value=b"jpeg"):
        sight = asyncio.run(
            see_screen(
                llm,
                channel="local",
                foreground=info,
                use_screenshot=True,
            )
        )
    assert sight.description == "编辑器里开着一段 Python 代码"
    assert sight.blocked is False
    llm.describe_image.assert_awaited_once()


def test_see_screen_falls_back_when_describe_fails() -> None:
    llm = AsyncMock()
    llm.describe_image = AsyncMock(side_effect=LLMError("no vision"))
    info = _info("main.py - Cursor", "Cursor.exe")
    with patch("src.vision.see_screen.capture_screen_jpeg", return_value=b"jpeg"):
        sight = asyncio.run(see_screen(llm, foreground=info))
    assert sight.description is None
    assert sight.reason == "describe_failed"


def test_proactive_prompt_includes_screen_description() -> None:
    text = generate_proactive_prompt(
        reason="idle",
        foreground=_info("main.py - Cursor", "Cursor.exe"),
        screen_description="编辑器里开着一段 Python 代码",
    )
    assert "屏幕上看起来" in text
    assert "Python" in text
    assert "memory_candidates" in text


def test_vision_pause_api() -> None:
    settings = load_config()
    client = TestClient(create_app(settings))
    bad = client.post("/api/vision/pause", json={"paused": "yes"})
    assert bad.status_code == 400
    ok = client.post("/api/vision/pause", json={"paused": True})
    assert ok.status_code == 200
    assert ok.json()["paused"] is True
    status = client.get("/api/vision/status")
    assert status.json()["paused"] is True


def test_see_screen_api_respects_pause() -> None:
    settings = load_config()
    app = create_app(settings)
    client = TestClient(app)
    client.post("/api/vision/pause", json={"paused": True})
    body = client.post("/api/vision/see_screen").json()
    assert body["paused"] is True
    assert body["description"] is None

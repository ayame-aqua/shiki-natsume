"""本机看屏工具。仅桌宠/本地 Agent 可用，禁止注册给 QQ。"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from src.core.llm import LLMClient, LLMError
from src.vision.blacklist import is_capture_blocked
from src.vision.capture import capture_screen_jpeg
from src.vision.constants import (
    DEFAULT_JPEG_QUALITY,
    DEFAULT_MAX_SIDE_PX,
    SCREEN_DESCRIBE_PROMPT,
)
from src.vision.foreground import ForegroundInfo, read_foreground

logger = logging.getLogger(__name__)

CHANNEL_LOCAL = "local"
CHANNEL_QQ = "qq"


@dataclass(frozen=True)
class ScreenSight:
    description: str | None
    blocked: bool
    paused: bool
    foreground: ForegroundInfo | None
    reason: str | None = None


async def see_screen(
    llm: LLMClient | None,
    *,
    channel: str = CHANNEL_LOCAL,
    paused: bool = False,
    use_screenshot: bool = True,
    foreground: ForegroundInfo | None = None,
    process_blacklist: list[str] | None = None,
    title_keywords_blacklist: list[str] | None = None,
    max_side_px: int = DEFAULT_MAX_SIDE_PX,
    jpeg_quality: int = DEFAULT_JPEG_QUALITY,
    vision_model: str | None = None,
) -> ScreenSight:
    """截屏并一句话描述。QQ 通道直接拒绝。"""
    if channel == CHANNEL_QQ:
        logger.warning("see_screen refused for qq channel")
        return ScreenSight(
            description=None,
            blocked=True,
            paused=paused,
            foreground=foreground,
            reason="qq_forbidden",
        )
    if paused:
        return ScreenSight(
            description=None,
            blocked=False,
            paused=True,
            foreground=foreground,
            reason="paused",
        )
    if not use_screenshot:
        return ScreenSight(
            description=None,
            blocked=False,
            paused=False,
            foreground=foreground,
            reason="screenshot_disabled",
        )

    info = foreground if foreground is not None else read_foreground()
    if is_capture_blocked(
        info,
        process_blacklist=process_blacklist,
        title_keywords_blacklist=title_keywords_blacklist,
    ):
        return ScreenSight(
            description=None,
            blocked=True,
            paused=False,
            foreground=info,
            reason="blacklist_or_self",
        )
    if llm is None:
        return ScreenSight(
            description=None,
            blocked=False,
            paused=False,
            foreground=info,
            reason="llm_unavailable",
        )

    jpeg = capture_screen_jpeg(max_side_px=max_side_px, quality=jpeg_quality)
    if not jpeg:
        return ScreenSight(
            description=None,
            blocked=False,
            paused=False,
            foreground=info,
            reason="capture_failed",
        )
    try:
        description = await llm.describe_image(
            prompt=SCREEN_DESCRIBE_PROMPT,
            jpeg_bytes=jpeg,
            model=vision_model,
        )
    except LLMError:
        logger.warning("screen describe failed; falling back to title only")
        return ScreenSight(
            description=None,
            blocked=False,
            paused=False,
            foreground=info,
            reason="describe_failed",
        )
    text = description.strip()
    if not text:
        return ScreenSight(
            description=None,
            blocked=False,
            paused=False,
            foreground=info,
            reason="empty_description",
        )
    return ScreenSight(
        description=text,
        blocked=False,
        paused=False,
        foreground=info,
        reason=None,
    )

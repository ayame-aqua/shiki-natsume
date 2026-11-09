"""本地主动搭话判定。不负责调模型或推 UI。"""

from __future__ import annotations

from dataclasses import dataclass

from src.core.policy.local import (
    ALLOW_PROACTIVE,
    DEFAULT_COOLDOWN_S,
    DEFAULT_IDLE_TIMEOUT_S,
)
from src.vision.constants import DEFAULT_FOCUS_IDLE_TIMEOUT_S, DEFAULT_TITLE_COOLDOWN_S
from src.vision.foreground import ForegroundInfo

REASON_DISABLED = "disabled"
REASON_DND = "do_not_disturb"
REASON_NOT_IDLE = "not_idle_yet"
REASON_COOLDOWN = "cooldown"
REASON_SAME_WINDOW = "same_window_cooldown"
REASON_IDLE = "idle"
REASON_FOCUS_CHANGE = "focus_change"


@dataclass(frozen=True)
class ProactiveDecision:
    allowed: bool
    reason: str | None = None


def decide_proactive(
    *,
    enabled: bool,
    do_not_disturb: bool,
    now: float,
    last_activity: float | None,
    started_at: float,
    last_proactive: float,
    idle_timeout_s: float = DEFAULT_IDLE_TIMEOUT_S,
    cooldown_s: float = DEFAULT_COOLDOWN_S,
    foreground: ForegroundInfo | None = None,
    last_seen_signature: str | None = None,
    last_commented_signature: str | None = None,
    last_title_comment_at: float = 0.0,
    title_cooldown_s: float = DEFAULT_TITLE_COOLDOWN_S,
    focus_idle_timeout_s: float = DEFAULT_FOCUS_IDLE_TIMEOUT_S,
    use_title: bool = True,
) -> ProactiveDecision:
    """冷场、窗口切换、冷却、勿扰都过了才允许主动。"""
    if not enabled or not ALLOW_PROACTIVE:
        return ProactiveDecision(False, REASON_DISABLED)
    if do_not_disturb:
        return ProactiveDecision(False, REASON_DND)
    if last_proactive > 0 and now - last_proactive < cooldown_s:
        return ProactiveDecision(False, REASON_COOLDOWN)

    idle_anchor = last_activity if last_activity is not None else started_at
    idle_for = now - idle_anchor
    focus_changed = _focus_changed(
        foreground,
        last_seen_signature,
        use_title=use_title,
    )
    same_window = _same_window_cooling(
        foreground,
        last_commented_signature=last_commented_signature,
        last_title_comment_at=last_title_comment_at,
        now=now,
        title_cooldown_s=title_cooldown_s,
        use_title=use_title,
    )

    if focus_changed and foreground is not None and not foreground.is_self:
        if same_window:
            return ProactiveDecision(False, REASON_SAME_WINDOW)
        if idle_for >= focus_idle_timeout_s:
            return ProactiveDecision(True, REASON_FOCUS_CHANGE)

    if idle_for < idle_timeout_s:
        return ProactiveDecision(False, REASON_NOT_IDLE)
    return ProactiveDecision(True, REASON_IDLE)


def should_attach_foreground(
    *,
    decision_reason: str | None,
    foreground: ForegroundInfo | None,
    last_commented_signature: str | None,
    last_title_comment_at: float,
    now: float,
    title_cooldown_s: float,
    use_title: bool,
) -> bool:
    """决定这轮 system 指令里要不要带窗口线索。"""
    if not use_title or foreground is None or foreground.is_self:
        return False
    if decision_reason == REASON_FOCUS_CHANGE:
        return True
    if _same_window_cooling(
        foreground,
        last_commented_signature=last_commented_signature,
        last_title_comment_at=last_title_comment_at,
        now=now,
        title_cooldown_s=title_cooldown_s,
        use_title=use_title,
    ):
        return False
    return True


def _focus_changed(
    foreground: ForegroundInfo | None,
    last_seen_signature: str | None,
    *,
    use_title: bool,
) -> bool:
    if not use_title or foreground is None or last_seen_signature is None:
        return False
    return foreground.signature != last_seen_signature


def _same_window_cooling(
    foreground: ForegroundInfo | None,
    *,
    last_commented_signature: str | None,
    last_title_comment_at: float,
    now: float,
    title_cooldown_s: float,
    use_title: bool,
) -> bool:
    if not use_title or foreground is None or foreground.is_self:
        return False
    if not last_commented_signature or last_title_comment_at <= 0:
        return False
    if foreground.signature != last_commented_signature:
        return False
    return now - last_title_comment_at < title_cooldown_s

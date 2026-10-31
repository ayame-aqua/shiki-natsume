"""本地主动搭话判定。不负责调模型或推 UI。"""

from __future__ import annotations

from dataclasses import dataclass

from src.core.policy.local import (
    ALLOW_PROACTIVE,
    DEFAULT_COOLDOWN_S,
    DEFAULT_IDLE_TIMEOUT_S,
)

REASON_DISABLED = "disabled"
REASON_DND = "do_not_disturb"
REASON_NOT_IDLE = "not_idle_yet"
REASON_COOLDOWN = "cooldown"


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
) -> ProactiveDecision:
    """冷场、冷却、勿扰都过了才允许主动。"""
    if not enabled or not ALLOW_PROACTIVE:
        return ProactiveDecision(False, REASON_DISABLED)
    if do_not_disturb:
        return ProactiveDecision(False, REASON_DND)
    idle_anchor = last_activity if last_activity is not None else started_at
    if now - idle_anchor < idle_timeout_s:
        return ProactiveDecision(False, REASON_NOT_IDLE)
    if last_proactive > 0 and now - last_proactive < cooldown_s:
        return ProactiveDecision(False, REASON_COOLDOWN)
    return ProactiveDecision(True)

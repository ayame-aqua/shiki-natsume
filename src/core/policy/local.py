"""本地陪伴策略（P5：主动搭话）。"""

from __future__ import annotations

from src.vision.constants import SCENE_LABELS, SCENE_SELF
from src.vision.foreground import ForegroundInfo

DEFAULT_SILENT = False
ALLOW_PROACTIVE = True
DEFAULT_IDLE_TIMEOUT_S = 300
DEFAULT_COOLDOWN_S = 600
DEFAULT_RANDOM_TALK_PROB = 0.1

PROACTIVE_IDLE_INSTRUCTION = (
    "对方已经一段时间没有理你。"
    "请按人设主动开口找对方，可以关心、撒娇或轻轻抱怨。"
    "不要复述本条说明，不要假装对方刚对你说了话。"
)

PROACTIVE_FOCUS_INSTRUCTION = (
    "对方刚切到另一个应用。"
    "请按人设轻轻提一句，可以关心或吐槽，不要盘问审讯。"
    "不要复述本条说明，不要假装对方刚对你说了话。"
)

PROACTIVE_VISION_RULES = (
    "若给出了前台窗口线索，可以轻轻提到你看见的情况；"
    "不要编造屏幕上的具体内容，也不要复述完整窗口标题。"
)


def generate_proactive_prompt(
    *,
    reason: str = "idle",
    foreground: ForegroundInfo | None = None,
) -> str:
    """送给 Agent 的 system 指令，不是伪装成用户说的话。"""
    base = PROACTIVE_FOCUS_INSTRUCTION if reason == "focus_change" else PROACTIVE_IDLE_INSTRUCTION
    vision = _foreground_hint(foreground)
    if vision:
        return f"{base}{PROACTIVE_VISION_RULES}\n{vision}"
    return base


def _foreground_hint(foreground: ForegroundInfo | None) -> str:
    if foreground is None or foreground.is_self or foreground.scene == SCENE_SELF:
        return ""
    label = SCENE_LABELS.get(foreground.scene, "在电脑前")
    process = foreground.process.strip() or "未知进程"
    title = _short_title(foreground.title)
    if title:
        return f"当前前台大致是：{label}（进程 {process}，窗口「{title}」）。"
    return f"当前前台大致是：{label}（进程 {process}）。"


def _short_title(title: str, *, max_chars: int = 48) -> str:
    text = " ".join((title or "").split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1] + "…"

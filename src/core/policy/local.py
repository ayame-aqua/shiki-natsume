"""本地陪伴策略（P5：主动搭话）。"""

from __future__ import annotations

DEFAULT_SILENT = False
ALLOW_PROACTIVE = True
DEFAULT_IDLE_TIMEOUT_S = 300
DEFAULT_COOLDOWN_S = 600
DEFAULT_RANDOM_TALK_PROB = 0.1

PROACTIVE_INSTRUCTION = (
    "对方已经一段时间没有理你。"
    "请按人设主动开口找对方，可以关心、撒娇或轻轻抱怨。"
    "不要复述本条说明，不要假装对方刚对你说了话。"
)


def generate_proactive_prompt() -> str:
    """送给 Agent 的 system 指令，不是伪装成用户说的话。"""
    return PROACTIVE_INSTRUCTION

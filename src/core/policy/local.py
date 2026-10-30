"""本地陪伴策略（P5 切片 2：主动搭话）。"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.types import InboundMessage

DEFAULT_SILENT = False
ALLOW_PROACTIVE = True

# 主动搭话提示模板
PROACTIVE_PROMPTS = [
    "很久没听到你的声音了。",
    "在忙吗？",
    "还在吗？",
    "突然有点想你。",
    "…嗯，该说点什么呢。",
    "无聊。",
]


def should_allow_proactive(inbound: InboundMessage | None = None) -> bool:
    """
    判断是否允许主动搭话。
    
    本地策略：始终允许（除非配置禁用）。
    QQ 策略会覆盖此函数。
    """
    del inbound
    return ALLOW_PROACTIVE


def generate_proactive_prompt() -> str:
    """
    生成主动搭话的用户消息文本。
    
    这是 system 或用户侧的触发文本，会送给 Agent。
    Agent 根据人设和上下文自己决定说什么。
    """
    return random.choice(PROACTIVE_PROMPTS)

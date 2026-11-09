"""看屏黑名单：命中则不截屏。"""

from __future__ import annotations

from src.vision.constants import DEFAULT_PROCESS_BLACKLIST, DEFAULT_TITLE_KEYWORDS_BLACKLIST
from src.vision.foreground import ForegroundInfo


def is_capture_blocked(
    foreground: ForegroundInfo | None,
    *,
    process_blacklist: list[str] | tuple[str, ...] | None = None,
    title_keywords_blacklist: list[str] | tuple[str, ...] | None = None,
) -> bool:
    """自窗或黑名单命中时禁止截屏。"""
    if foreground is None or foreground.is_self:
        return True
    processes = _normalize_list(process_blacklist, DEFAULT_PROCESS_BLACKLIST)
    titles = _normalize_list(title_keywords_blacklist, DEFAULT_TITLE_KEYWORDS_BLACKLIST)
    process = foreground.process.lower()
    title = foreground.title.lower()
    if any(item and item in process for item in processes):
        return True
    if any(item and item in title for item in titles):
        return True
    return False


def _normalize_list(
    configured: list[str] | tuple[str, ...] | None,
    defaults: tuple[str, ...],
) -> list[str]:
    raw = defaults if configured is None else configured
    return [str(item).strip().lower() for item in raw if str(item).strip()]

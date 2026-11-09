"""前台窗口标题与场景粗分（P5-S3）。不截屏。"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass

from src.vision.constants import (
    BROWSER_PROCESS_NAMES,
    GAME_PROCESS_KEYWORDS,
    GAME_TITLE_KEYWORDS,
    SCENE_BROWSE,
    SCENE_GAME,
    SCENE_SELF,
    SCENE_UNKNOWN,
    SCENE_VIDEO,
    SCENE_WORK,
    SELF_ELECTRON_TITLE_PREFIXES,
    SELF_PROCESS_NAMES,
    SELF_WINDOW_TITLES,
    VIDEO_PROCESS_NAMES,
    VIDEO_TITLE_KEYWORDS,
    WORK_PROCESS_KEYWORDS,
    WORK_TITLE_KEYWORDS,
)

logger = logging.getLogger(__name__)

IS_WINDOWS = sys.platform == "win32"


@dataclass(frozen=True)
class ForegroundInfo:
    title: str
    process: str
    scene: str
    is_self: bool

    @property
    def signature(self) -> str:
        return f"{self.process.lower()}|{self.title.strip().lower()}"


def classify_scene(process_name: str, title: str) -> str:
    """纯函数：进程名 + 标题 → 场景。测试不碰 Win32。"""
    process = (process_name or "").strip().lower()
    title_lower = (title or "").strip().lower()

    if _is_self(process, title_lower):
        return SCENE_SELF

    if process in VIDEO_PROCESS_NAMES:
        return SCENE_VIDEO
    if any(keyword in title_lower for keyword in VIDEO_TITLE_KEYWORDS):
        return SCENE_VIDEO

    if any(keyword in process for keyword in GAME_PROCESS_KEYWORDS):
        return SCENE_GAME
    if any(keyword in title_lower for keyword in GAME_TITLE_KEYWORDS):
        return SCENE_GAME

    if any(keyword in process for keyword in WORK_PROCESS_KEYWORDS):
        return SCENE_WORK
    if any(keyword in title_lower for keyword in WORK_TITLE_KEYWORDS):
        return SCENE_WORK

    if process in BROWSER_PROCESS_NAMES:
        return SCENE_BROWSE

    return SCENE_UNKNOWN


def read_foreground() -> ForegroundInfo | None:
    """读当前前台窗。非 Windows 或失败返回 None，调用方当没看见。"""
    if not IS_WINDOWS:
        return None
    try:
        return _read_windows_foreground()
    except Exception:
        logger.exception("foreground read failed")
        return None


def _is_self(process: str, title_lower: str) -> bool:
    base = os.path.basename(process).lower()
    stem = base[:-4] if base.endswith(".exe") else base
    if stem in SELF_PROCESS_NAMES or base in SELF_PROCESS_NAMES:
        return True
    if title_lower in SELF_WINDOW_TITLES:
        return True
    if base == "electron.exe" and any(
        title_lower.startswith(prefix) for prefix in SELF_ELECTRON_TITLE_PREFIXES
    ):
        return True
    return False


def _read_windows_foreground() -> ForegroundInfo | None:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    process_query_limited = 0x1000

    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None

    length = user32.GetWindowTextLengthW(hwnd)
    title_buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, title_buf, length + 1)
    title = title_buf.value.strip()

    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    process_name = ""
    handle = kernel32.OpenProcess(process_query_limited, False, pid.value)
    if handle:
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(1024)
            if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                process_name = os.path.basename(buf.value)
        finally:
            kernel32.CloseHandle(handle)

    scene = classify_scene(process_name, title)
    return ForegroundInfo(
        title=title,
        process=process_name,
        scene=scene,
        is_self=scene == SCENE_SELF,
    )

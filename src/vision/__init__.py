"""本机看屏（P5）。S3 标题；S4 截屏描述。"""

from __future__ import annotations

from src.vision.foreground import ForegroundInfo, classify_scene, read_foreground
from src.vision.see_screen import ScreenSight, see_screen

__all__ = [
    "ForegroundInfo",
    "ScreenSight",
    "classify_scene",
    "read_foreground",
    "see_screen",
]

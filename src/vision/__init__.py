"""本机看屏（P5）。S3 只做前台窗口标题；截屏在 S4。"""

from __future__ import annotations

from src.vision.foreground import ForegroundInfo, classify_scene, read_foreground

__all__ = ["ForegroundInfo", "classify_scene", "read_foreground"]

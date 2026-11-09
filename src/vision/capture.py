"""屏幕截图压缩为 JPEG。依赖 mss + Pillow；缺失则返回 None。"""

from __future__ import annotations

import io
import logging
from typing import Any

from src.vision.constants import DEFAULT_JPEG_QUALITY, DEFAULT_MAX_SIDE_PX

logger = logging.getLogger(__name__)


def capture_screen_jpeg(
    *,
    max_side_px: int = DEFAULT_MAX_SIDE_PX,
    quality: int = DEFAULT_JPEG_QUALITY,
    crop_rect: dict[str, int] | None = None,
) -> bytes | None:
    """截主屏（或裁切区）并缩到 max_side_px。失败返回 None，不落盘。"""
    try:
        import mss
        from PIL import Image
    except ImportError:
        logger.warning("vision capture deps missing; pip install mss Pillow")
        return None

    try:
        with mss.MSS() as sct:
            monitor = sct.monitors[1]
            box = _capture_box(monitor, crop_rect)
            raw = sct.grab(box)
            image = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
    except Exception:
        logger.exception("screen capture failed")
        return None

    side = max(1, int(max_side_px))
    if max(image.size) > side:
        image.thumbnail((side, side))
    quality = min(95, max(40, int(quality)))
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def _capture_box(
    monitor: dict[str, Any],
    crop_rect: dict[str, int] | None,
) -> dict[str, int]:
    if not crop_rect:
        return {
            "left": int(monitor["left"]),
            "top": int(monitor["top"]),
            "width": int(monitor["width"]),
            "height": int(monitor["height"]),
        }
    width = int(crop_rect.get("width", 0))
    height = int(crop_rect.get("height", 0))
    if width < 120 or height < 120:
        return {
            "left": int(monitor["left"]),
            "top": int(monitor["top"]),
            "width": int(monitor["width"]),
            "height": int(monitor["height"]),
        }
    left = max(int(monitor["left"]), int(crop_rect.get("left", monitor["left"])))
    top = max(int(monitor["top"]), int(crop_rect.get("top", monitor["top"])))
    right = min(
        int(monitor["left"]) + int(monitor["width"]),
        int(crop_rect.get("left", 0)) + width,
    )
    bottom = min(
        int(monitor["top"]) + int(monitor["height"]),
        int(crop_rect.get("top", 0)) + height,
    )
    out_w = right - left
    out_h = bottom - top
    if out_w < 100 or out_h < 100:
        return {
            "left": int(monitor["left"]),
            "top": int(monitor["top"]),
            "width": int(monitor["width"]),
            "height": int(monitor["height"]),
        }
    return {"left": left, "top": top, "width": out_w, "height": out_h}

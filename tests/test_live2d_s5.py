"""P5-S5：点击 motion 接线存在（无模型时仍不崩）。"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIVE2D_JS = ROOT / "web" / "live2d.js"
DESKTOP_CSS = ROOT / "web" / "desktop.css"
README = ROOT / "web" / "live2d" / "README.md"


def test_live2d_exposes_play_motion() -> None:
    text = LIVE2D_JS.read_text(encoding="utf-8")
    assert "playMotion" in text
    assert "DEFAULT_MOTION_MAP" in text
    assert "tap_head" in text
    assert "tap_body" in text
    assert "TAP_COOLDOWN_MS" in text
    assert "bindModelInteraction" in text


def test_desktop_canvas_is_no_drag() -> None:
    text = DESKTOP_CSS.read_text(encoding="utf-8")
    assert "#live2d-canvas" in text
    assert "-webkit-app-region: no-drag" in text


def test_motion_map_documented() -> None:
    text = README.read_text(encoding="utf-8")
    assert "motionMap" in text
    assert "tap_head" in text

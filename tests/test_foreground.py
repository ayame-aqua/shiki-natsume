"""P5-S3 前台窗口场景粗分。"""

from __future__ import annotations

from src.core.policy.local import generate_proactive_prompt
from src.core.proactive import (
    REASON_FOCUS_CHANGE,
    REASON_IDLE,
    REASON_SAME_WINDOW,
    decide_proactive,
    should_attach_foreground,
)
from src.vision.constants import SCENE_BROWSE, SCENE_GAME, SCENE_SELF, SCENE_VIDEO, SCENE_WORK
from src.vision.foreground import ForegroundInfo, classify_scene


def test_classify_work_cursor() -> None:
    assert classify_scene("Cursor.exe", "main.py - shiki-natsume - Cursor") == SCENE_WORK


def test_classify_video_bilibili_title() -> None:
    assert classify_scene("chrome.exe", "【直播】四季夏目 - 哔哩哔哩") == SCENE_VIDEO


def test_classify_game_steam() -> None:
    assert classify_scene("steam.exe", "Library") == SCENE_GAME


def test_classify_browse() -> None:
    assert classify_scene("msedge.exe", "GitHub") == SCENE_BROWSE


def test_classify_self_electron_pet() -> None:
    assert classify_scene("electron.exe", "四季夏目") == SCENE_SELF


def test_classify_does_not_treat_repo_name_as_self() -> None:
    assert classify_scene("Cursor.exe", "main.py - shiki-natsume - Cursor") == SCENE_WORK


def test_classify_does_not_treat_video_about_natsume_as_self() -> None:
    assert classify_scene("chrome.exe", "【直播】四季夏目 - 哔哩哔哩") == SCENE_VIDEO


def test_proactive_prompt_includes_scene() -> None:
    info = ForegroundInfo(
        title="main.py - atri - Cursor",
        process="Cursor.exe",
        scene=SCENE_WORK,
        is_self=False,
    )
    text = generate_proactive_prompt(reason="idle", foreground=info)
    assert "写代码或办公" in text
    assert "Cursor.exe" in text
    assert "不要编造" in text


def test_focus_change_allows_before_full_idle() -> None:
    info = ForegroundInfo(
        title="Library",
        process="steam.exe",
        scene=SCENE_GAME,
        is_self=False,
    )
    now = 10_000.0
    decision = decide_proactive(
        enabled=True,
        do_not_disturb=False,
        now=now,
        last_activity=now - 90,
        started_at=now - 1_000,
        last_proactive=now - 700,
        idle_timeout_s=300,
        cooldown_s=600,
        foreground=info,
        last_seen_signature="chrome.exe|github",
        last_commented_signature="chrome.exe|github",
        last_title_comment_at=now - 700,
        title_cooldown_s=600,
        focus_idle_timeout_s=60,
        use_title=True,
    )
    assert decision.allowed is True
    assert decision.reason == REASON_FOCUS_CHANGE


def test_same_window_blocks_focus_spam() -> None:
    info = ForegroundInfo(
        title="Library",
        process="steam.exe",
        scene=SCENE_GAME,
        is_self=False,
    )
    now = 10_000.0
    decision = decide_proactive(
        enabled=True,
        do_not_disturb=False,
        now=now,
        last_activity=now - 90,
        started_at=now - 1_000,
        last_proactive=now - 700,
        idle_timeout_s=300,
        cooldown_s=600,
        foreground=info,
        last_seen_signature="chrome.exe|github",
        last_commented_signature=info.signature,
        last_title_comment_at=now - 30,
        title_cooldown_s=600,
        focus_idle_timeout_s=60,
        use_title=True,
    )
    assert decision.allowed is False
    assert decision.reason == REASON_SAME_WINDOW


def test_idle_skips_repeating_title_in_prompt() -> None:
    info = ForegroundInfo(
        title="main.py - Cursor",
        process="Cursor.exe",
        scene=SCENE_WORK,
        is_self=False,
    )
    now = 10_000.0
    decision = decide_proactive(
        enabled=True,
        do_not_disturb=False,
        now=now,
        last_activity=now - 400,
        started_at=now - 1_000,
        last_proactive=0.0,
        idle_timeout_s=300,
        cooldown_s=600,
        foreground=info,
        last_seen_signature=info.signature,
        last_commented_signature=info.signature,
        last_title_comment_at=now - 30,
        title_cooldown_s=600,
        use_title=True,
    )
    assert decision.allowed is True
    assert decision.reason == REASON_IDLE
    assert (
        should_attach_foreground(
            decision_reason=decision.reason,
            foreground=info,
            last_commented_signature=info.signature,
            last_title_comment_at=now - 30,
            now=now,
            title_cooldown_s=600,
            use_title=True,
        )
        is False
    )

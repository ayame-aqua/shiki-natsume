"""看屏常量。S3 只有标题；截屏字段留给 S4。"""

from __future__ import annotations

SCENE_WORK = "work"
SCENE_GAME = "game"
SCENE_VIDEO = "video"
SCENE_BROWSE = "browse"
SCENE_UNKNOWN = "unknown"
SCENE_SELF = "self"

SCENE_LABELS: dict[str, str] = {
    SCENE_WORK: "写代码或办公",
    SCENE_GAME: "打游戏",
    SCENE_VIDEO: "看视频或直播",
    SCENE_BROWSE: "浏览网页",
    SCENE_UNKNOWN: "在电脑前",
    SCENE_SELF: "对着她自己",
}

DEFAULT_VISION_ENABLED = True
DEFAULT_USE_TITLE = True
DEFAULT_USE_SCREENSHOT = False
DEFAULT_TITLE_COOLDOWN_S = 600.0
DEFAULT_FOCUS_IDLE_TIMEOUT_S = 60.0

SELF_PROCESS_NAMES = frozenset(
    {
        "shiki-natsume-desktop",
    }
)

# 桌宠窗标题就是「四季夏目」；DevTools 另算。不要用子串匹配，免得误伤 Cursor 目录名或视频标题。
SELF_WINDOW_TITLES = frozenset(
    {
        "四季夏目",
    }
)

SELF_ELECTRON_TITLE_PREFIXES = (
    "developer tools - http://127.0.0.1:8787",
)

WORK_PROCESS_KEYWORDS = (
    "code",
    "cursor",
    "devenv",
    "pycharm",
    "idea64",
    "idea",
    "clion",
    "webstorm",
    "sublime_text",
    "notepad++",
    "windowsterminal",
    "wt.exe",
    "powershell",
    "pwsh",
    "cmd.exe",
)

WORK_TITLE_KEYWORDS = (
    "visual studio",
    "vscode",
    "cursor",
    "pycharm",
    "intellij",
    "clion",
    "webstorm",
    "terminal",
    "powershell",
)

GAME_PROCESS_KEYWORDS = (
    "steam",
    "epicgames",
    "genshin",
    "starrail",
    "honkai",
    "zenless",
    "wuthering",
    "league",
    "valorant",
    "cs2",
    "csgo",
    "dota2",
    "minecraft",
    "javaw",
    "overwatch",
    "apex",
    "pubg",
    "eldenring",
    "blackmyth",
    "wukong",
    "helldivers",
)

GAME_TITLE_KEYWORDS = (
    "steam",
    "原神",
    "崩坏",
    "星穹铁道",
    "绝区零",
    "鸣潮",
    "黑神话",
    "艾尔登",
    "游戏",
)

VIDEO_PROCESS_NAMES = frozenset(
    {
        "potplayer64.exe",
        "potplayer.exe",
        "vlc.exe",
        "mpv.exe",
        "bilibili.exe",
    }
)

VIDEO_TITLE_KEYWORDS = (
    "哔哩哔哩",
    "bilibili",
    "youtube",
    "腾讯视频",
    "爱奇艺",
    "优酷",
    "抖音",
    "douyin",
    "twitch",
    "直播",
    "番剧",
)

BROWSER_PROCESS_NAMES = frozenset(
    {
        "chrome.exe",
        "msedge.exe",
        "firefox.exe",
        "brave.exe",
        "opera.exe",
        "vivaldi.exe",
    }
)

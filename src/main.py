"""四季夏目应用入口：FastAPI + WebSocket 网页聊天。"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.channels.chat_hub import ChatHub
from src.channels.voice import VoiceChannel, inbound_from_transcript, parse_user_audio_frame
from src.channels.web import (
    assistant_audio_frame,
    assistant_text_frame,
    parse_user_text_frame,
    user_transcript_frame,
)
from src.config import REPO_ROOT, load_config
from src.core.agent import Agent
from src.core.errors import BAD_REQUEST, human_message
from src.core.living_notes import LivingNotesStore
from src.core.llm import LLMClient, LLMError
from src.core.persona import split_persona
from src.core.policy.local import (
    DEFAULT_COOLDOWN_S,
    DEFAULT_IDLE_TIMEOUT_S,
    generate_proactive_prompt,
)
from src.core.proactive import decide_proactive, should_attach_foreground
from src.core.session import SessionStore
from src.core.types import InboundMessage, OutboundMessage
from src.gateway import Gateway
from src.memory.constants import (
    DEFAULT_CHAT_ID,
    DEFAULT_CYCLE_ENABLED,
    DEFAULT_DIARY_KEEP,
    DEFAULT_EPISODE_MIN_SCORE,
    DEFAULT_EXTRACT_EVERY_N,
    DEFAULT_MOOD_DECAY_PER_HOUR,
    DEFAULT_RETRIEVE_K,
    DEFAULT_STYLE_MAX,
    STATUS_ACTIVE,
    STATUS_CONFIRMED,
    STATUS_PENDING,
    VECTOR_BACKEND_LANCEDB,
)
from src.memory.store import Diary, Episode, Fact, Impression, MemoryStore, StyleTerm
from src.memory.summarize import summarize_turns
from src.speech.asr import build_asr
from src.speech.constants import (
    DEFAULT_ASR_MODEL,
    DEFAULT_CACHE_DIR,
    DEFAULT_GPT_WEIGHTS,
    DEFAULT_REF_DIR,
    DEFAULT_SOVITS_WEIGHTS,
    DEFAULT_TTS_API_BASE,
    DEFAULT_TTS_TIMEOUT_S,
    STATUS_UNCLEAR,
    TTS_TEXT_LANG,
    UNCLEAR_REPLY,
    USER_AUDIO_TYPE,
    VAD_LEVEL_TYPE,
)
from src.speech.debug_log import speech_debug
from src.speech.tts import SoVitsTts, TtsError
from src.vision.constants import (
    DEFAULT_FOCUS_IDLE_TIMEOUT_S,
    DEFAULT_JPEG_QUALITY,
    DEFAULT_MAX_SIDE_PX,
    DEFAULT_TITLE_COOLDOWN_S,
    DEFAULT_USE_SCREENSHOT,
    DEFAULT_USE_TITLE,
    DEFAULT_VISION_ENABLED,
)
from src.vision.foreground import ForegroundInfo, read_foreground
from src.vision.see_screen import CHANNEL_LOCAL, see_screen

logger = logging.getLogger(__name__)
WEB_DIR = REPO_ROOT / "web"


def _attach_runtime(
    app: FastAPI,
    settings: dict[str, Any],
    *,
    persona_path: str,
    max_turns: int,
    dedup_ttl_s: float,
) -> None:
    try:
        llm = _build_llm(settings)
    except LLMError:
        logger.exception("llm client init failed")
        llm = None
    sessions = SessionStore(max_turns=max_turns * 2)
    memory_cfg = settings.get("memory") or {}
    sqlite_rel = str(memory_cfg.get("sqlite_path", "data/memory.sqlite"))
    sqlite_path = Path(sqlite_rel) if os.path.isabs(sqlite_rel) else REPO_ROOT / sqlite_rel
    vector_rel = str(memory_cfg.get("vector_path", "data/vectors"))
    vector_path = Path(vector_rel) if os.path.isabs(vector_rel) else REPO_ROOT / vector_rel
    backend = str(memory_cfg.get("vector_backend", VECTOR_BACKEND_LANCEDB))
    if backend != VECTOR_BACKEND_LANCEDB:
        logger.warning("memory vector_backend=%s unsupported, using lancedb", backend)
    retrieve_k = int(memory_cfg.get("retrieve_k", DEFAULT_RETRIEVE_K))
    style_max = int(memory_cfg.get("style_max", DEFAULT_STYLE_MAX))
    min_score = float(memory_cfg.get("episode_min_score", DEFAULT_EPISODE_MIN_SCORE))
    extract_every_n = int(memory_cfg.get("extract_every_n", DEFAULT_EXTRACT_EVERY_N))
    diary_keep = int(memory_cfg.get("diary_keep", DEFAULT_DIARY_KEEP))
    mood_cfg = memory_cfg.get("mood") or {}
    memory = MemoryStore(
        sqlite_path,
        seed=True,
        vector_path=vector_path,
        retrieve_k=retrieve_k,
        style_max=style_max,
        min_score=min_score,
        mood_enabled=bool(mood_cfg.get("enabled", True)),
        mood_decay_per_hour=float(mood_cfg.get("decay_per_hour", DEFAULT_MOOD_DECAY_PER_HOUR)),
        cycle_enabled=bool(mood_cfg.get("cycle_enabled", DEFAULT_CYCLE_ENABLED)),
        diary_keep=diary_keep,
    )
    living_notes = LivingNotesStore(REPO_ROOT / "data" / "living_notes.json")
    agent = (
        Agent(
            persona_path=persona_path,
            llm=llm,
            sessions=sessions,
            memory=memory,
            living_notes=living_notes,
            extract_every_n=extract_every_n,
        )
        if llm is not None
        else None
    )
    proactive_cfg = settings.get("proactive") or {}
    app.state.gateway = Gateway(dedup_ttl_s=dedup_ttl_s, agent=agent)
    app.state.memory = memory
    app.state.sessions = sessions
    app.state.llm = llm
    app.state.persona_path = persona_path
    app.state.llm_ready = llm is not None
    app.state.chat_hub = ChatHub()
    app.state.started_at = time.time()
    app.state.last_proactive_time = 0.0
    app.state.do_not_disturb = bool(proactive_cfg.get("do_not_disturb", False))
    app.state.last_seen_foreground_signature = None
    app.state.last_commented_foreground_signature = None
    app.state.last_title_comment_at = 0.0
    app.state.vision_paused = False
    speech_cfg = settings.get("speech") or {}
    api_base = str(speech_cfg.get("tts_api_base", DEFAULT_TTS_API_BASE))
    ref_rel = str(speech_cfg.get("tts_ref_dir", DEFAULT_REF_DIR))
    cache_rel = str(speech_cfg.get("tts_cache_dir", DEFAULT_CACHE_DIR))
    ref_dir = Path(ref_rel) if os.path.isabs(ref_rel) else REPO_ROOT / ref_rel
    cache_dir = Path(cache_rel) if os.path.isabs(cache_rel) else REPO_ROOT / cache_rel
    timeout_s = float(speech_cfg.get("tts_timeout_s", DEFAULT_TTS_TIMEOUT_S))
    text_lang = str(speech_cfg.get("tts_text_lang", TTS_TEXT_LANG))
    gpt_rel = str(speech_cfg.get("tts_gpt_weights", DEFAULT_GPT_WEIGHTS))
    sovits_rel = str(speech_cfg.get("tts_sovits_weights", DEFAULT_SOVITS_WEIGHTS))
    gpt_weights = Path(gpt_rel) if os.path.isabs(gpt_rel) else REPO_ROOT / gpt_rel
    sovits_weights = Path(sovits_rel) if os.path.isabs(sovits_rel) else REPO_ROOT / sovits_rel
    app.state.tts = SoVitsTts(
        api_base=api_base,
        ref_dir=ref_dir,
        cache_dir=cache_dir,
        timeout_s=timeout_s,
        text_lang=text_lang,
        gpt_weights=gpt_weights,
        sovits_weights=sovits_weights,
    )
    asr_model = str(speech_cfg.get("asr_model", DEFAULT_ASR_MODEL))
    channels_cfg = settings.get("channels") or {}
    voice_on = bool((channels_cfg.get("voice") or {}).get("enabled", True))
    if voice_on:
        asr = build_asr(asr_model)
        app.state.asr = asr
        app.state.voice = VoiceChannel(asr)
    else:
        app.state.asr = None
        app.state.voice = None


def _start_asr_warmup(app: FastAPI) -> asyncio.Task[None] | None:
    asr = getattr(app.state, "asr", None)
    if asr is None:
        return None
    task = asyncio.create_task(asr.warmup())
    task.add_done_callback(_log_socket_task)
    return task


def _build_llm(config: dict[str, Any]) -> LLMClient:
    llm_cfg = config.get("llm") or {}
    timeout_s = float(llm_cfg.get("timeout_s", 60))
    disable_thinking = bool(llm_cfg.get("disable_thinking", True))
    api_key = os.environ.get("LLM_API_KEY", "")
    base_url = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com")
    model = os.environ.get("LLM_MODEL", "deepseek-flash")
    return LLMClient(
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout_s=timeout_s,
        disable_thinking=disable_thinking,
    )


def create_app(config: dict[str, Any] | None = None) -> FastAPI:
    settings = config if config is not None else load_config()
    persona_rel = str(settings.get("character", "characters/natsume.md"))
    persona_path = persona_rel if os.path.isabs(persona_rel) else str(REPO_ROOT / persona_rel)
    session_cfg = settings.get("session") or {}
    max_turns = int(session_cfg.get("max_turns", 20))
    gateway_cfg = settings.get("gateway") or {}
    dedup_ttl_s = float(gateway_cfg.get("dedup_ttl_s", 600))
    server_cfg = settings.get("server") or {}

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )
        logger.info(
            "natsume web listening host=%s port=%s llm_ready=%s",
            server_cfg.get("host", "127.0.0.1"),
            server_cfg.get("port", 8787),
            app.state.llm_ready,
        )
        warmup = _start_asr_warmup(app)
        try:
            yield
        finally:
            if warmup is not None:
                warmup.cancel()

    app = FastAPI(title="shiki-natsume", lifespan=lifespan)
    _attach_runtime(
        app,
        settings,
        persona_path=persona_path,
        max_turns=max_turns,
        dedup_ttl_s=dedup_ttl_s,
    )

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {"ok": True, "llm_ready": bool(getattr(app.state, "llm_ready", False))}

    @app.get("/api/character")
    async def character() -> dict[str, Any]:
        meta, _body = split_persona(persona_path)
        name = meta.get("name") if isinstance(meta.get("name"), str) else "四季夏目"
        return {"name": name}

    @app.get("/memory")
    async def memory_page() -> FileResponse:
        return FileResponse(WEB_DIR / "memory.html")

    @app.get("/api/memory/facts")
    async def list_memory_facts(status: str = "active") -> dict[str, Any]:
        memory: MemoryStore = app.state.memory
        filter_status = None if status in {"", "all"} else status
        return {"facts": [_fact_json(item) for item in memory.list_facts(status=filter_status)]}

    @app.post("/api/memory/facts")
    async def create_memory_fact(payload: dict[str, Any]) -> dict[str, Any]:
        key = payload.get("key")
        value = payload.get("value")
        if not isinstance(key, str) or not key.strip():
            raise HTTPException(status_code=400, detail="key required")
        if not isinstance(value, str) or not value.strip():
            raise HTTPException(status_code=400, detail="value required")
        category = payload.get("category", "other")
        if not isinstance(category, str):
            category = "other"
        memory: MemoryStore = app.state.memory
        fact = memory.add_fact(
            key.strip(),
            value.strip(),
            category=category,
            source="manual",
            overwrite=True,
        )
        return _fact_json(fact)

    @app.patch("/api/memory/facts/{fact_id}")
    async def patch_memory_fact(fact_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        memory: MemoryStore = app.state.memory
        value = payload.get("value") if isinstance(payload.get("value"), str) else None
        status = payload.get("status") if isinstance(payload.get("status"), str) else None
        fact = memory.update_fact(fact_id, value=value, status=status)
        if fact is None:
            raise HTTPException(status_code=404, detail="fact not found")
        return _fact_json(fact)

    @app.delete("/api/memory/facts/{fact_id}")
    async def delete_memory_fact(fact_id: int) -> dict[str, Any]:
        memory: MemoryStore = app.state.memory
        if not memory.delete_fact(fact_id):
            raise HTTPException(status_code=404, detail="fact not found")
        return {"ok": True}

    @app.post("/api/memory/forget")
    async def forget_memory(payload: dict[str, Any]) -> dict[str, Any]:
        query = payload.get("query")
        if not isinstance(query, str) or not query.strip():
            raise HTTPException(status_code=400, detail="query required")
        memory: MemoryStore = app.state.memory
        hits = memory.forget(query.strip())
        return {"facts": [_fact_json(item) for item in hits]}

    @app.get("/api/memory/episodes")
    async def list_memory_episodes(status: str = "") -> dict[str, Any]:
        memory: MemoryStore = app.state.memory
        filter_status = None if status in {"", "all"} else status
        return {
            "episodes": [_episode_json(item) for item in memory.list_episodes(status=filter_status)]
        }

    @app.post("/api/memory/episodes/{episode_id}/confirm")
    async def confirm_memory_episode(episode_id: int) -> dict[str, Any]:
        memory: MemoryStore = app.state.memory
        episode = memory.update_episode(episode_id, status=STATUS_ACTIVE)
        if episode is None:
            raise HTTPException(status_code=404, detail="episode not found")
        return _episode_json(episode)

    @app.get("/api/memory/style")
    async def list_memory_style(status: str = "") -> dict[str, Any]:
        memory: MemoryStore = app.state.memory
        filter_status = None if status in {"", "all"} else status
        return {"style": [_style_json(item) for item in memory.list_style(status=filter_status)]}

    @app.post("/api/memory/style/{style_id}/confirm")
    async def confirm_memory_style(style_id: int) -> dict[str, Any]:
        memory: MemoryStore = app.state.memory
        term = memory.confirm_style(style_id)
        if term is None:
            raise HTTPException(status_code=404, detail="style not found")
        if term.status != STATUS_CONFIRMED:
            raise HTTPException(status_code=409, detail="style not confirmed")
        return _style_json(term)

    @app.post("/api/memory/summarize-session")
    async def summarize_memory_session(payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = payload or {}
        chat_id = body.get("chat_id")
        if not isinstance(chat_id, str) or not chat_id.strip():
            chat_id = DEFAULT_CHAT_ID
        sessions: SessionStore = app.state.sessions
        turns = sessions.history(chat_id.strip())
        if not turns:
            raise HTTPException(status_code=400, detail="session empty")
        llm = app.state.llm
        if llm is None:
            raise HTTPException(status_code=503, detail="llm not ready")
        try:
            summary = await summarize_turns(llm, turns)
        except (ValueError, TypeError, LLMError):
            logger.exception("summarize failed chat_id=%s", chat_id)
            raise HTTPException(status_code=502, detail="summarize failed") from None
        memory: MemoryStore = app.state.memory
        episode = memory.add_episode(summary, source_chat_id=chat_id, status=STATUS_PENDING)
        diary = memory.upsert_diary(summary)
        return {"episode": _episode_json(episode), "diary": _diary_json(diary)}

    @app.get("/api/memory/mood")
    async def get_memory_mood() -> dict[str, Any]:
        memory: MemoryStore = app.state.memory
        mood = memory.get_mood()
        return {
            "energy": mood.energy,
            "irritation": mood.irritation,
            "affection": mood.affection,
            "cycle_enabled": memory.cycle_enabled,
        }

    @app.post("/api/memory/impressions/{impression_id}/confirm")
    async def confirm_memory_impression(impression_id: int) -> dict[str, Any]:
        memory: MemoryStore = app.state.memory
        row = memory.update_impression(impression_id, status=STATUS_ACTIVE)
        if row is None:
            raise HTTPException(status_code=404, detail="impression not found")
        return _impression_json(row)

    @app.post("/api/memory/export")
    async def export_memory() -> dict[str, Any]:
        memory: MemoryStore = app.state.memory
        dest = REPO_ROOT / "data" / "memory" / "export.md"
        path = memory.export_markdown(dest)
        return {"path": str(path)}

    @app.get("/api/proactive/status")
    async def get_proactive_status() -> dict[str, Any]:
        proactive_cfg = settings.get("proactive") or {}
        vision_cfg = settings.get("vision") or {}
        sessions: SessionStore = app.state.sessions
        last_activity = sessions.last_activity_time(DEFAULT_CHAT_ID)
        return {
            "enabled": bool(proactive_cfg.get("enabled", False)),
            "do_not_disturb": bool(getattr(app.state, "do_not_disturb", False)),
            "idle_timeout_s": int(proactive_cfg.get("idle_timeout_s", DEFAULT_IDLE_TIMEOUT_S)),
            "cooldown_s": int(proactive_cfg.get("cooldown_s", DEFAULT_COOLDOWN_S)),
            "last_activity_ms": int(last_activity * 1000) if last_activity else None,
            "vision_enabled": bool(vision_cfg.get("enabled", DEFAULT_VISION_ENABLED)),
            "use_title": bool(vision_cfg.get("use_title", DEFAULT_USE_TITLE)),
            "use_screenshot": bool(vision_cfg.get("use_screenshot", DEFAULT_USE_SCREENSHOT)),
            "vision_paused": bool(getattr(app.state, "vision_paused", False)),
        }

    @app.get("/api/vision/foreground")
    async def get_foreground() -> dict[str, Any]:
        """本机冒烟：看当前前台标题/场景。不截屏。"""
        info = read_foreground()
        if info is None:
            return {"available": False}
        return {
            "available": True,
            "title": info.title,
            "process": info.process,
            "scene": info.scene,
            "is_self": info.is_self,
            "signature": info.signature,
        }

    @app.get("/api/vision/status")
    async def get_vision_status() -> dict[str, Any]:
        vision_cfg = settings.get("vision") or {}
        return {
            "enabled": bool(vision_cfg.get("enabled", DEFAULT_VISION_ENABLED)),
            "use_title": bool(vision_cfg.get("use_title", DEFAULT_USE_TITLE)),
            "use_screenshot": bool(vision_cfg.get("use_screenshot", DEFAULT_USE_SCREENSHOT)),
            "paused": bool(getattr(app.state, "vision_paused", False)),
            "max_side_px": int(vision_cfg.get("max_side_px", DEFAULT_MAX_SIDE_PX)),
        }

    @app.post("/api/vision/pause")
    async def set_vision_pause(payload: dict[str, Any]) -> dict[str, Any]:
        enabled = payload.get("paused")
        if not isinstance(enabled, bool):
            raise HTTPException(status_code=400, detail="paused must be boolean")
        app.state.vision_paused = enabled
        logger.info("vision paused=%s", enabled)
        return {"paused": enabled}

    @app.post("/api/vision/see_screen")
    async def api_see_screen() -> dict[str, Any]:
        """本机主动看一眼。不写记忆，不给 QQ 用。"""
        vision_cfg = settings.get("vision") or {}
        sight = await see_screen(
            getattr(app.state, "llm", None),
            channel=CHANNEL_LOCAL,
            paused=bool(getattr(app.state, "vision_paused", False)),
            use_screenshot=bool(vision_cfg.get("use_screenshot", DEFAULT_USE_SCREENSHOT)),
            process_blacklist=_string_list(vision_cfg.get("process_blacklist")),
            title_keywords_blacklist=_string_list(vision_cfg.get("title_keywords_blacklist")),
            max_side_px=int(vision_cfg.get("max_side_px", DEFAULT_MAX_SIDE_PX)),
            jpeg_quality=int(vision_cfg.get("jpeg_quality", DEFAULT_JPEG_QUALITY)),
            vision_model=os.environ.get("LLM_VISION_MODEL") or None,
        )
        return {
            "description": sight.description,
            "blocked": sight.blocked,
            "paused": sight.paused,
            "reason": sight.reason,
            "foreground": _foreground_json(sight.foreground),
        }

    @app.post("/api/proactive/trigger")
    async def trigger_proactive() -> dict[str, Any]:
        return await _trigger_proactive(app, settings)

    @app.post("/api/proactive/dnd")
    async def toggle_dnd(payload: dict[str, Any]) -> dict[str, Any]:
        enabled = payload.get("enabled")
        if not isinstance(enabled, bool):
            raise HTTPException(status_code=400, detail="enabled must be boolean")
        app.state.do_not_disturb = enabled
        logger.info("proactive dnd enabled=%s", enabled)
        return {"do_not_disturb": enabled}

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    @app.get("/media/tts/{audio_id}")
    async def tts_media(audio_id: str) -> FileResponse:
        tts: SoVitsTts | None = getattr(app.state, "tts", None)
        if tts is None:
            raise HTTPException(status_code=404, detail="tts not ready")
        path = tts.clip_path(audio_id)
        if path is None:
            raise HTTPException(status_code=404, detail="clip not found")
        return FileResponse(path, media_type="audio/wav")

    @app.websocket("/ws/chat")
    async def chat_socket(websocket: WebSocket) -> None:
        await websocket.accept()
        hub: ChatHub = app.state.chat_hub
        hub.add(websocket)
        gateway: Gateway = app.state.gateway
        try:
            while True:
                raw = await websocket.receive_text()
                await _handle_socket_text(websocket, gateway, raw)
        except WebSocketDisconnect:
            logger.info("websocket disconnected")
        finally:
            hub.discard(websocket)

    if WEB_DIR.is_dir():
        app.mount("/assets", StaticFiles(directory=WEB_DIR), name="assets")
    live2d_dir = WEB_DIR / "live2d"
    if live2d_dir.is_dir():
        app.mount("/live2d", StaticFiles(directory=live2d_dir), name="live2d")
    return app


async def _trigger_proactive(app: FastAPI, settings: dict[str, Any]) -> dict[str, Any]:
    proactive_cfg = settings.get("proactive") or {}
    vision_cfg = settings.get("vision") or {}
    sessions: SessionStore = app.state.sessions
    now = time.time()
    vision_on = bool(vision_cfg.get("enabled", DEFAULT_VISION_ENABLED))
    use_title = vision_on and bool(vision_cfg.get("use_title", DEFAULT_USE_TITLE))
    use_screenshot = vision_on and bool(vision_cfg.get("use_screenshot", DEFAULT_USE_SCREENSHOT))
    title_cooldown_s = float(vision_cfg.get("title_cooldown_s", DEFAULT_TITLE_COOLDOWN_S))
    focus_idle_timeout_s = float(
        vision_cfg.get("focus_idle_timeout_s", DEFAULT_FOCUS_IDLE_TIMEOUT_S)
    )
    vision_paused = bool(getattr(app.state, "vision_paused", False))

    foreground = read_foreground() if use_title or use_screenshot else None
    last_seen = getattr(app.state, "last_seen_foreground_signature", None)
    last_commented = getattr(app.state, "last_commented_foreground_signature", None)
    last_title_comment_at = float(getattr(app.state, "last_title_comment_at", 0.0))

    decision = decide_proactive(
        enabled=bool(proactive_cfg.get("enabled", False)),
        do_not_disturb=bool(getattr(app.state, "do_not_disturb", False)),
        now=now,
        last_activity=sessions.last_activity_time(DEFAULT_CHAT_ID),
        started_at=float(getattr(app.state, "started_at", now)),
        last_proactive=float(getattr(app.state, "last_proactive_time", 0.0)),
        idle_timeout_s=float(proactive_cfg.get("idle_timeout_s", DEFAULT_IDLE_TIMEOUT_S)),
        cooldown_s=float(proactive_cfg.get("cooldown_s", DEFAULT_COOLDOWN_S)),
        foreground=foreground,
        last_seen_signature=last_seen,
        last_commented_signature=last_commented,
        last_title_comment_at=last_title_comment_at,
        title_cooldown_s=title_cooldown_s,
        focus_idle_timeout_s=focus_idle_timeout_s,
        use_title=use_title,
    )
    if foreground is not None:
        app.state.last_seen_foreground_signature = foreground.signature
    if not decision.allowed:
        return {
            "triggered": False,
            "reason": decision.reason,
            "foreground": _foreground_json(foreground) if foreground else None,
        }

    attach = should_attach_foreground(
        decision_reason=decision.reason,
        foreground=foreground,
        last_commented_signature=last_commented,
        last_title_comment_at=last_title_comment_at,
        now=now,
        title_cooldown_s=title_cooldown_s,
        use_title=use_title,
    )
    prompt_foreground = foreground if attach else None
    screen_description = None
    screen_meta: dict[str, Any] | None = None
    if attach and use_screenshot and not vision_paused:
        sight = await see_screen(
            getattr(app.state, "llm", None),
            channel=CHANNEL_LOCAL,
            paused=False,
            use_screenshot=True,
            foreground=foreground,
            process_blacklist=_string_list(vision_cfg.get("process_blacklist")),
            title_keywords_blacklist=_string_list(vision_cfg.get("title_keywords_blacklist")),
            max_side_px=int(vision_cfg.get("max_side_px", DEFAULT_MAX_SIDE_PX)),
            jpeg_quality=int(vision_cfg.get("jpeg_quality", DEFAULT_JPEG_QUALITY)),
            vision_model=os.environ.get("LLM_VISION_MODEL") or None,
        )
        screen_description = sight.description
        screen_meta = {
            "blocked": sight.blocked,
            "reason": sight.reason,
            "has_description": bool(sight.description),
        }

    inbound = InboundMessage(
        message_id=str(uuid4()),
        channel="web",
        chat_type="system",
        chat_id=DEFAULT_CHAT_ID,
        sender_id="system",
        sender_name="system",
        text=generate_proactive_prompt(
            reason=decision.reason or "idle",
            foreground=prompt_foreground,
            screen_description=screen_description,
        ),
        created_at=now,
        raw_type="proactive",
        vision=(
            {"description": screen_description, "persist": False} if screen_description else None
        ),
    )
    gateway: Gateway = app.state.gateway
    result = await gateway.handle(inbound)
    if result.error_code or result.outbound is None:
        logger.warning(
            "proactive agent failed reason=%s error=%s",
            "agent_failed",
            result.error_code,
        )
        return {
            "triggered": False,
            "reason": "agent_failed",
            "error": result.error_code,
        }

    outbound = result.outbound
    app.state.last_proactive_time = now
    if attach and foreground is not None and not foreground.is_self:
        app.state.last_commented_foreground_signature = foreground.signature
        app.state.last_title_comment_at = now
    audio_url = await _synthesize_outbound_audio(app, outbound)
    await _broadcast_outbound(app, outbound, audio_url)
    logger.info(
        "proactive triggered message_id=%s reason=%s scene=%s screen=%s clients=%s",
        outbound.message_id,
        decision.reason,
        None if prompt_foreground is None else prompt_foreground.scene,
        bool(screen_description),
        app.state.chat_hub.client_count(),
    )
    return {
        "triggered": True,
        "message_id": outbound.message_id,
        "reason": decision.reason,
        "texts": outbound.texts,
        "emotion": outbound.emotion,
        "audio_url": audio_url,
        "foreground": _foreground_json(prompt_foreground),
        "screen": screen_meta,
    }


def _foreground_json(info: ForegroundInfo | None) -> dict[str, Any] | None:
    if info is None:
        return None
    return {
        "title": info.title,
        "process": info.process,
        "scene": info.scene,
        "is_self": info.is_self,
    }


def _string_list(value: object) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        return None
    return [str(item) for item in value if str(item).strip()]


async def _synthesize_outbound_audio(app: FastAPI, outbound: OutboundMessage) -> str | None:
    speech_ja = outbound.speech_ja
    if not speech_ja:
        return None
    tts = getattr(app.state, "tts", None)
    if not isinstance(tts, SoVitsTts):
        return None
    try:
        clip = await tts.synthesize_to_cache(speech_ja, outbound.emotion)
    except TtsError:
        logger.warning("proactive tts failed message_id=%s", outbound.message_id)
        return None
    outbound.audio_url = f"/media/tts/{clip.audio_id}"
    return outbound.audio_url


async def _broadcast_outbound(
    app: FastAPI,
    outbound: OutboundMessage,
    audio_url: str | None,
) -> None:
    hub: ChatHub = app.state.chat_hub
    await hub.broadcast_json(assistant_text_frame(outbound))
    if audio_url:
        await hub.broadcast_json(assistant_audio_frame(outbound, url=audio_url))
    await hub.broadcast_json({"type": "status", "message_id": outbound.message_id, "state": "idle"})


async def _handle_socket_text(websocket: WebSocket, gateway: Gateway, raw: str) -> None:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        await _send_error(websocket, None, BAD_REQUEST)
        return
    if not isinstance(payload, dict):
        await _send_error(websocket, None, BAD_REQUEST)
        return

    if payload.get("type") == VAD_LEVEL_TYPE:
        _log_vad_level(payload)
        return
    if payload.get("type") == USER_AUDIO_TYPE:
        task = asyncio.create_task(_handle_user_audio(websocket, gateway, payload))
        task.add_done_callback(_log_socket_task)
        return

    inbound = parse_user_text_frame(payload)
    if isinstance(inbound, str):
        await _send_error(websocket, payload.get("message_id"), inbound)
        return
    await _run_inbound(websocket, gateway, inbound)


def _log_socket_task(task: asyncio.Task[None]) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error("background task failed name=%s", task.get_name(), exc_info=exc)


def _log_vad_level(payload: dict[str, Any]) -> None:
    speech_debug(
        "vad",
        band=f"{_as_float(payload.get('band')):.3f}",
        floor=f"{_as_float(payload.get('floor')):.3f}",
        peak=f"{_as_float(payload.get('peak')):.3f}",
        rec=1 if payload.get("recording") else 0,
        voice=1 if payload.get("voice") else 0,
    )


def _as_float(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


async def _handle_user_audio(
    websocket: WebSocket,
    gateway: Gateway,
    payload: dict[str, Any],
) -> None:
    parsed = parse_user_audio_frame(payload)
    if isinstance(parsed, str):
        await _send_error(websocket, payload.get("message_id"), parsed)
        return
    speech_debug(
        "slice",
        message_id=parsed.message_id,
        bytes=len(parsed.audio),
        mime=parsed.mime,
    )
    voice = getattr(websocket.app.state, "voice", None)
    if not isinstance(voice, VoiceChannel):
        logger.error("voice channel missing message_id=%s", parsed.message_id)
        await _send_unclear(websocket, parsed.message_id, "")
        return
    result = await voice.transcribe(parsed)
    await websocket.send_json(
        user_transcript_frame(parsed.message_id, result.text, unclear=result.unclear)
    )
    if result.unclear:
        await _send_unclear(websocket, parsed.message_id, result.text)
        return
    await _run_inbound(websocket, gateway, inbound_from_transcript(parsed.message_id, result.text))


async def _send_unclear(websocket: WebSocket, message_id: str, text: str) -> None:
    del text
    await websocket.send_json(
        {
            "type": "status",
            "message_id": message_id,
            "state": STATUS_UNCLEAR,
            "message": UNCLEAR_REPLY,
        }
    )
    await websocket.send_json({"type": "status", "message_id": message_id, "state": "idle"})


async def _run_inbound(
    websocket: WebSocket,
    gateway: Gateway,
    inbound: InboundMessage,
) -> None:
    await websocket.send_json(
        {"type": "status", "message_id": inbound.message_id, "state": "thinking"}
    )
    result = await gateway.handle(inbound)
    if result.error_code or result.outbound is None:
        await _send_error(
            websocket,
            inbound.message_id,
            result.error_code or "INTERNAL",
        )
        await websocket.send_json(
            {"type": "status", "message_id": inbound.message_id, "state": "idle"}
        )
        return

    if result.replay:
        await websocket.send_json({"type": "duplicate", "message_id": inbound.message_id})
    await websocket.send_json(assistant_text_frame(result.outbound))
    await _send_assistant_audio(websocket, result.outbound)
    await websocket.send_json({"type": "status", "message_id": inbound.message_id, "state": "idle"})


async def _send_assistant_audio(websocket: WebSocket, outbound: OutboundMessage) -> None:
    speech_ja = outbound.speech_ja
    if not speech_ja:
        return
    tts = getattr(websocket.app.state, "tts", None)
    if not isinstance(tts, SoVitsTts):
        return
    try:
        clip = await tts.synthesize_to_cache(speech_ja, outbound.emotion)
    except TtsError:
        logger.warning("tts failed message_id=%s", outbound.message_id)
        await websocket.send_json(
            {
                "type": "status",
                "message_id": outbound.message_id,
                "state": "tts_failed",
            }
        )
        return
    outbound.audio_url = f"/media/tts/{clip.audio_id}"
    await websocket.send_json(
        assistant_audio_frame(
            outbound,
            url=outbound.audio_url,
            duration_ms=clip.duration_ms,
        )
    )


async def _send_error(websocket: WebSocket, message_id: object, code: str) -> None:
    frame: dict[str, Any] = {
        "type": "error",
        "code": code,
        "message": human_message(code),
    }
    if isinstance(message_id, str) and message_id:
        frame["message_id"] = message_id
    await websocket.send_json(frame)


def _fact_json(fact: Fact) -> dict[str, Any]:
    return {
        "id": fact.id,
        "key": fact.key,
        "value": fact.value,
        "category": fact.category,
        "status": fact.status,
        "source": fact.source,
        "evidence": fact.evidence,
    }


def _episode_json(episode: Episode) -> dict[str, Any]:
    return {
        "id": episode.id,
        "summary": episode.summary,
        "happened_at": episode.happened_at,
        "source_chat_id": episode.source_chat_id,
        "status": episode.status,
        "embedding_id": episode.embedding_id,
    }


def _style_json(term: StyleTerm) -> dict[str, Any]:
    return {
        "id": term.id,
        "term": term.term,
        "meaning": term.meaning,
        "usage": term.usage,
        "status": term.status,
        "evidence": term.evidence,
        "count": term.count,
    }


def _diary_json(row: Diary) -> dict[str, Any]:
    return {"id": row.id, "day": row.day, "summary": row.summary}


def _impression_json(row: Impression) -> dict[str, Any]:
    return {
        "id": row.id,
        "text": row.text,
        "status": row.status,
        "source": row.source,
    }


app = create_app()


def main() -> None:
    import uvicorn

    settings = load_config()
    server = settings.get("server") or {}
    host = str(server.get("host", "127.0.0.1"))
    port = int(server.get("port", 8787))
    uvicorn.run("src.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()

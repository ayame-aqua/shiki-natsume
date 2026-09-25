"""P3-B ASR：默认 Confucius4-R2T2（qwen-asr / transformers）；失败再 SenseVoice-Small。

Fun-ASR-Nano 仍可配。不上 vLLM。权重走 HuggingFace 缓存，不进 git。
"""

from __future__ import annotations

import asyncio
import logging
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from src.speech.constants import (
    ASR_BEAM_SIZE,
    ASR_INITIAL_PROMPT,
    ASR_LANGUAGE,
    ASR_MAX_AUDIO_BYTES,
    ASR_MIN_AUDIO_BYTES,
    ASR_MIN_TEXT_CHARS,
    ASR_MODEL_PREFIX,
    ASR_NO_SPEECH_MAX,
    ASR_WAV_RATE,
    CONFUCIUS4_BACKEND,
    CONFUCIUS4_LANGUAGE,
    CONFUCIUS4_MAX_NEW_TOKENS,
    CONFUCIUS4_MODEL_ID,
    DEFAULT_ASR_MODEL,
    FUNASR_NANO_BACKEND,
    FUNASR_NANO_ID,
    SENSEVOICE_BACKEND,
    SENSEVOICE_BATCH_SIZE_S,
    SENSEVOICE_LANGUAGE,
    SENSEVOICE_MERGE_LENGTH_S,
    SENSEVOICE_MODEL_ID,
    SENSEVOICE_VAD_MAX_MS,
    SENSEVOICE_VAD_MODEL,
    WHISPER_FALLBACK_SIZE,
)
from src.speech.debug_log import speech_debug

logger = logging.getLogger(__name__)

_SENSEVOICE_TAG = re.compile(r"<\|[^|]*\|>")
_CONFUCIUS_TOKENS = ("confucius", "r2t2", "孔子")
_NANO_TOKENS = ("nano", "fun-asr", "funasr")
_WHISPER_SIZES = ("tiny", "base", "small", "medium", "large-v2", "large-v3", "large")

_MIME_SUFFIX = {
    "audio/webm": ".webm",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".mp4",
    "audio/ogg": ".ogg",
}


class AsrError(Exception):
    """转写失败。调用方按没听清处理，不得写记忆。"""


@dataclass(frozen=True)
class FunasrSpec:
    """同一套 FunASR 加载路径，不同权重。"""

    model_id: str
    backend: str
    trust_remote_code: bool


class Confucius4Asr:
    """网易有道 Confucius4-R2T2。整段转写走 qwen-asr 的 transformers 后端，不上 vLLM。"""

    def __init__(self, model_id: str = CONFUCIUS4_MODEL_ID) -> None:
        self._model_id = model_id
        self._model: object | None = None

    async def transcribe(self, audio_bytes: bytes, mime: str) -> str:
        path = _write_temp_audio(audio_bytes, mime)
        if path is None:
            return ""
        wav_path: Path | None = None
        try:
            wav_path = await asyncio.to_thread(_ensure_wav, path)
            model = await asyncio.to_thread(self._ensure_model)
            return await asyncio.to_thread(self._transcribe_path, model, wav_path)
        finally:
            if wav_path is not None and wav_path != path:
                wav_path.unlink(missing_ok=True)
            path.unlink(missing_ok=True)

    async def warmup(self) -> None:
        await asyncio.to_thread(self._ensure_model)

    def _ensure_model(self) -> object:
        if self._model is not None:
            return self._model
        try:
            import torch
            from qwen_asr import Qwen3ASRModel
        except ImportError as exc:
            msg = "qwen-asr is not installed"
            raise AsrError(msg) from exc
        device = _torch_device()
        dtype = torch.bfloat16 if device.startswith("cuda") else torch.float32
        logger.info("asr loading model=%s device=%s", self._model_id, device)
        speech_debug("asr_load", backend=CONFUCIUS4_BACKEND, model=self._model_id, device=device)
        try:
            self._model = Qwen3ASRModel.from_pretrained(
                self._model_id,
                dtype=dtype,
                device_map=device,
                max_inference_batch_size=1,
                max_new_tokens=CONFUCIUS4_MAX_NEW_TOKENS,
            )
        except Exception as exc:
            msg = "confucius4 load failed"
            raise AsrError(msg) from exc
        return self._model

    def _transcribe_path(self, model: object, path: Path) -> str:
        transcribe = getattr(model, "transcribe", None)
        if transcribe is None:
            msg = "confucius4 missing transcribe"
            raise AsrError(msg)
        try:
            raw = transcribe(audio=str(path), language=CONFUCIUS4_LANGUAGE)
        except Exception as exc:
            msg = "confucius4 infer failed"
            raise AsrError(msg) from exc
        text = _confucius_text(raw)
        speech_debug("asr_text", backend=CONFUCIUS4_BACKEND, text=text)
        return text


class FunasrAsr:
    """SenseVoice / Fun-ASR-Nano 共用：16 kHz wav + fsmn-vad。"""

    def __init__(self, spec: FunasrSpec) -> None:
        self._spec = spec
        self._model: object | None = None

    async def transcribe(self, audio_bytes: bytes, mime: str) -> str:
        path = _write_temp_audio(audio_bytes, mime)
        if path is None:
            return ""
        wav_path: Path | None = None
        try:
            wav_path = await asyncio.to_thread(_ensure_wav, path)
            model = await asyncio.to_thread(self._ensure_model)
            return await asyncio.to_thread(self._transcribe_path, model, wav_path)
        finally:
            if wav_path is not None and wav_path != path:
                wav_path.unlink(missing_ok=True)
            path.unlink(missing_ok=True)

    async def warmup(self) -> None:
        await asyncio.to_thread(self._ensure_model)

    def _ensure_model(self) -> object:
        if self._model is not None:
            return self._model
        try:
            from funasr import AutoModel
        except ImportError as exc:
            msg = "funasr is not installed"
            raise AsrError(msg) from exc
        device = _torch_device()
        logger.info("asr loading model=%s device=%s", self._spec.model_id, device)
        speech_debug(
            "asr_load",
            backend=self._spec.backend,
            model=self._spec.model_id,
            device=device,
        )
        kwargs: dict[str, object] = {
            "model": self._spec.model_id,
            "vad_model": SENSEVOICE_VAD_MODEL,
            "vad_kwargs": {"max_single_segment_time": SENSEVOICE_VAD_MAX_MS},
            "device": device,
            "disable_update": True,
        }
        if self._spec.trust_remote_code:
            kwargs["trust_remote_code"] = True
        try:
            self._model = AutoModel(**kwargs)
        except Exception as exc:
            msg = "funasr load failed"
            raise AsrError(msg) from exc
        return self._model

    def _transcribe_path(self, model: object, path: Path) -> str:
        generate = getattr(model, "generate", None)
        if generate is None:
            msg = "funasr missing generate"
            raise AsrError(msg)
        try:
            raw = _funasr_generate(generate, path)
        except Exception as exc:
            msg = "funasr infer failed"
            raise AsrError(msg) from exc
        text = _sensevoice_text(raw)
        speech_debug("asr_text", backend=self._spec.backend, text=text)
        return text


class FasterWhisperAsr:
    def __init__(self, model_name: str = WHISPER_FALLBACK_SIZE) -> None:
        self._model_size = asr_model_size(model_name)
        self._model: object | None = None

    async def transcribe(self, audio_bytes: bytes, mime: str) -> str:
        path = _write_temp_audio(audio_bytes, mime)
        if path is None:
            return ""
        try:
            model = await asyncio.to_thread(self._ensure_model)
            return await asyncio.to_thread(self._transcribe_path, model, path)
        finally:
            path.unlink(missing_ok=True)

    async def warmup(self) -> None:
        await asyncio.to_thread(self._ensure_model)

    def _ensure_model(self) -> object:
        if self._model is not None:
            return self._model
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            msg = "faster-whisper is not installed"
            raise AsrError(msg) from exc
        device, compute_type = _pick_whisper_device()
        logger.info(
            "asr loading model=%s device=%s compute=%s",
            self._model_size,
            device,
            compute_type,
        )
        speech_debug(
            "asr_load",
            backend="faster-whisper",
            model=self._model_size,
            device=device,
        )
        self._model = WhisperModel(
            self._model_size,
            device=device,
            compute_type=compute_type,
        )
        return self._model

    def _transcribe_path(self, model: object, path: Path) -> str:
        transcribe = getattr(model, "transcribe", None)
        if transcribe is None:
            msg = "asr model missing transcribe"
            raise AsrError(msg)
        try:
            segments, _info = transcribe(
                str(path),
                language=ASR_LANGUAGE,
                initial_prompt=ASR_INITIAL_PROMPT,
                vad_filter=True,
                beam_size=ASR_BEAM_SIZE,
            )
        except Exception as exc:
            msg = "asr infer failed"
            raise AsrError(msg) from exc
        texts: list[str] = []
        no_speech: list[float] = []
        for segment in segments:
            piece = getattr(segment, "text", "")
            if isinstance(piece, str) and piece.strip():
                texts.append(piece.strip())
            prob = getattr(segment, "no_speech_prob", None)
            if isinstance(prob, (int, float)):
                no_speech.append(float(prob))
        if no_speech and (sum(no_speech) / len(no_speech)) >= ASR_NO_SPEECH_MAX:
            logger.info("asr no_speech_prob high n=%s", len(no_speech))
            return ""
        text = "".join(texts).strip()
        speech_debug("asr_text", backend="faster-whisper", text=text)
        return text


class FallbackAsr:
    """默认孔子 4；装不上或推理失败再 SenseVoice。Whisper 只在显式点名时当主力。"""

    def __init__(self, model_name: str = DEFAULT_ASR_MODEL) -> None:
        raw = (model_name or DEFAULT_ASR_MODEL).strip().lower()
        kind = resolve_asr_kind(raw)
        self._fallback: FunasrAsr | FasterWhisperAsr | None
        if kind == CONFUCIUS4_BACKEND:
            self._primary: Confucius4Asr | FunasrAsr | FasterWhisperAsr = Confucius4Asr()
            self._fallback = FunasrAsr(
                FunasrSpec(
                    model_id=SENSEVOICE_MODEL_ID,
                    backend=SENSEVOICE_BACKEND,
                    trust_remote_code=False,
                )
            )
        elif kind in {SENSEVOICE_BACKEND, FUNASR_NANO_BACKEND}:
            spec = resolve_funasr_spec(raw)
            if spec is None:
                msg = f"asr funasr spec missing kind={kind}"
                raise AsrError(msg)
            self._primary = FunasrAsr(spec)
            self._fallback = FasterWhisperAsr(WHISPER_FALLBACK_SIZE)
        else:
            self._primary = FasterWhisperAsr(raw)
            self._fallback = None
        self._primary_failed = False

    async def transcribe(self, audio_bytes: bytes, mime: str) -> str:
        if self._primary_failed:
            if self._fallback is None:
                msg = "asr primary already failed"
                raise AsrError(msg)
            return await self._fallback.transcribe(audio_bytes, mime)
        try:
            return await self._primary.transcribe(audio_bytes, mime)
        except AsrError:
            if self._fallback is None:
                raise
            self._primary_failed = True
            to_name = _backend_name(self._fallback)
            logger.exception("asr primary failed, falling back to %s", to_name)
            speech_debug("asr_fallback", to=to_name)
            return await self._fallback.transcribe(audio_bytes, mime)

    async def warmup(self) -> None:
        """首句之前把主力权重读进显存。孔子 4 约 2B，冷启动会拉 HuggingFace 缓存。"""
        try:
            await self._primary.warmup()
        except AsrError:
            self._primary_failed = True
            logger.exception("asr warmup failed backend=%s", _backend_name(self._primary))
            speech_debug("asr_warmup_fail", backend=_backend_name(self._primary))


def build_asr(model_name: str = DEFAULT_ASR_MODEL) -> FallbackAsr:
    return FallbackAsr(model_name)


def resolve_asr_kind(model_name: str) -> str:
    raw = (model_name or DEFAULT_ASR_MODEL).strip().lower()
    if raw.startswith(ASR_MODEL_PREFIX) or raw in _WHISPER_SIZES or "whisper" in raw:
        return "whisper"
    if _wants_confucius(raw):
        return CONFUCIUS4_BACKEND
    if any(token in raw for token in _NANO_TOKENS):
        return FUNASR_NANO_BACKEND
    if "sensevoice" in raw:
        return SENSEVOICE_BACKEND
    return CONFUCIUS4_BACKEND


def resolve_funasr_spec(model_name: str) -> FunasrSpec | None:
    """配置名 → FunASR 规格。孔子 4 / Whisper 返回 None。"""
    kind = resolve_asr_kind(model_name)
    if kind == FUNASR_NANO_BACKEND:
        return FunasrSpec(
            model_id=FUNASR_NANO_ID,
            backend=FUNASR_NANO_BACKEND,
            trust_remote_code=True,
        )
    if kind == SENSEVOICE_BACKEND:
        return FunasrSpec(
            model_id=SENSEVOICE_MODEL_ID,
            backend=SENSEVOICE_BACKEND,
            trust_remote_code=False,
        )
    return None


def asr_model_size(name: str) -> str:
    raw = (name or DEFAULT_ASR_MODEL).strip().lower()
    if raw.startswith(ASR_MODEL_PREFIX):
        raw = raw[len(ASR_MODEL_PREFIX) :]
    kind = resolve_asr_kind(raw)
    if kind == CONFUCIUS4_BACKEND:
        return CONFUCIUS4_BACKEND
    if kind == SENSEVOICE_BACKEND:
        return "sensevoice-small"
    if kind == FUNASR_NANO_BACKEND:
        return "fun-asr-nano"
    return raw or WHISPER_FALLBACK_SIZE


def _wants_confucius(name: str) -> bool:
    raw = (name or "").strip().lower()
    return any(token in raw for token in _CONFUCIUS_TOKENS)


def is_clear_transcript(text: str) -> bool:
    """只认中文。英文幻觉（如 T very social）当没听清。"""
    cjk = re.findall(r"[\u4e00-\u9fff]", text or "")
    return len(cjk) >= ASR_MIN_TEXT_CHARS


def _funasr_generate(generate: object, path: Path) -> object:
    """SenseVoice 吃 language/use_itn/merge_vad；Nano 的 generate 签名更窄，退一级。"""
    try:
        return generate(
            input=str(path),
            cache={},
            language=SENSEVOICE_LANGUAGE,
            use_itn=True,
            batch_size_s=SENSEVOICE_BATCH_SIZE_S,
            merge_vad=True,
            merge_length_s=SENSEVOICE_MERGE_LENGTH_S,
            ban_emo_unk=True,
        )
    except TypeError:
        return generate(
            input=str(path),
            cache={},
            language=SENSEVOICE_LANGUAGE,
            use_itn=True,
            batch_size_s=SENSEVOICE_BATCH_SIZE_S,
        )


def _ensure_wav(path: Path) -> Path:
    """SenseVoice 吃 wav；浏览器上行是 webm，复用 Faster-Whisper 的解码。"""
    if path.suffix.lower() == ".wav":
        return path
    try:
        from faster_whisper.audio import decode_audio
    except ImportError as exc:
        msg = "faster-whisper decode missing"
        raise AsrError(msg) from exc
    try:
        samples = decode_audio(str(path), sampling_rate=ASR_WAV_RATE)
    except Exception as exc:
        msg = "asr decode failed"
        raise AsrError(msg) from exc
    dest = path.with_suffix(".wav")
    _write_pcm_wav(dest, samples)
    return dest


def _write_pcm_wav(dest: Path, samples: object) -> None:
    import wave

    import numpy as np

    pcm = np.asarray(samples, dtype=np.float32).reshape(-1)
    pcm = np.clip(pcm, -1.0, 1.0)
    ints = (pcm * 32767.0).astype(np.int16)
    with wave.open(str(dest), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(ASR_WAV_RATE)
        handle.writeframes(ints.tobytes())


def _write_temp_audio(audio_bytes: bytes, mime: str) -> Path | None:
    if len(audio_bytes) < ASR_MIN_AUDIO_BYTES:
        logger.info("asr skip short audio bytes=%s", len(audio_bytes))
        speech_debug("asr_skip", reason="short", bytes=len(audio_bytes))
        return None
    if len(audio_bytes) > ASR_MAX_AUDIO_BYTES:
        msg = f"asr audio too large bytes={len(audio_bytes)}"
        raise AsrError(msg)
    suffix = _suffix_for_mime(mime)
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
        handle.write(audio_bytes)
        return Path(handle.name)


def _suffix_for_mime(mime: str) -> str:
    raw = (mime or "").split(";", 1)[0].strip().lower()
    return _MIME_SUFFIX.get(raw, ".webm")


def _confucius_text(raw: object) -> str:
    if isinstance(raw, list) and raw:
        return _confucius_text(raw[0])
    text = getattr(raw, "text", None)
    if isinstance(text, str):
        return " ".join(text.split()).strip()
    if isinstance(raw, dict):
        piece = raw.get("text")
        if isinstance(piece, str):
            return " ".join(piece.split()).strip()
    if isinstance(raw, str):
        return " ".join(raw.split()).strip()
    return ""


def _sensevoice_text(raw: object) -> str:
    text = ""
    if isinstance(raw, list) and raw:
        first = raw[0]
        if isinstance(first, dict):
            piece = first.get("text")
            if isinstance(piece, str):
                text = piece
        elif isinstance(first, str):
            text = first
    elif isinstance(raw, dict):
        piece = raw.get("text")
        if isinstance(piece, str):
            text = piece
    elif isinstance(raw, str):
        text = raw
    try:
        from funasr.utils.postprocess_utils import rich_transcription_postprocess

        text = rich_transcription_postprocess(text)
    except Exception:
        text = _SENSEVOICE_TAG.sub("", text)
    return " ".join(text.split()).strip()


def _backend_name(asr: Confucius4Asr | FunasrAsr | FasterWhisperAsr) -> str:
    spec = getattr(asr, "_spec", None)
    if isinstance(spec, FunasrSpec):
        return spec.backend
    if isinstance(asr, Confucius4Asr):
        return CONFUCIUS4_BACKEND
    return type(asr).__name__


def _torch_device() -> str:
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda:0"
    except ImportError:
        pass
    return "cpu"


def _pick_whisper_device() -> tuple[str, str]:
    try:
        import ctranslate2

        if int(ctranslate2.get_cuda_device_count()) > 0:
            return "cuda", "float16"
    except Exception:
        pass
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda", "float16"
    except ImportError:
        pass
    return "cpu", "int8"

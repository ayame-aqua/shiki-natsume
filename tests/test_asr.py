"""P3-B ASR 包装：不下载模型。"""

from __future__ import annotations

import asyncio

from src.speech.asr import (
    AsrError,
    FasterWhisperAsr,
    FunasrAsr,
    asr_model_size,
    build_asr,
    is_clear_transcript,
    resolve_funasr_spec,
)
from src.speech.constants import FUNASR_NANO_ID, SENSEVOICE_MODEL_ID


def test_asr_model_size_strips_prefix() -> None:
    assert asr_model_size("faster-whisper-small") == "small"
    assert asr_model_size("base") == "base"
    assert asr_model_size("sensevoice-small") == "sensevoice-small"
    assert asr_model_size("fun-asr-nano") == "fun-asr-nano"
    assert asr_model_size("funasr") == "fun-asr-nano"


def test_resolve_funasr_spec_defaults_to_sensevoice() -> None:
    spec = resolve_funasr_spec("sensevoice-small")
    assert spec is not None
    assert spec.model_id == SENSEVOICE_MODEL_ID
    assert spec.trust_remote_code is False
    nano = resolve_funasr_spec("fun-asr-nano")
    assert nano is not None
    assert nano.model_id == FUNASR_NANO_ID
    assert nano.trust_remote_code is True
    assert resolve_funasr_spec("small") is None


def test_build_asr_defaults_to_sensevoice() -> None:
    asr = build_asr()
    assert isinstance(asr._primary, FunasrAsr)
    assert asr._primary._spec.model_id == SENSEVOICE_MODEL_ID
    assert asr._fallback is not None
    assert asr._primary._model is None


def test_build_asr_can_still_select_nano() -> None:
    asr = build_asr("fun-asr-nano")
    assert isinstance(asr._primary, FunasrAsr)
    assert asr._primary._spec.model_id == FUNASR_NANO_ID


def test_fallback_sticks_after_primary_fail() -> None:
    asr = build_asr("sensevoice-small")

    class _Boom:
        async def transcribe(self, audio_bytes: bytes, mime: str) -> str:
            raise AsrError("primary down")

    asr._primary = _Boom()  # type: ignore[assignment]
    text = asyncio.run(asr.transcribe(b"xx", "audio/webm"))
    assert text == ""
    assert asr._primary_failed is True


def test_clear_transcript_rejects_noise() -> None:
    assert is_clear_transcript("") is False
    assert is_clear_transcript("……") is False
    assert is_clear_transcript("嗯") is False
    assert is_clear_transcript("在吗") is True
    assert is_clear_transcript("hi") is False
    assert is_clear_transcript("T very social.") is False


def test_transcribe_short_audio_returns_empty() -> None:
    asr = FasterWhisperAsr("small")
    text = asyncio.run(asr.transcribe(b"xx", "audio/webm"))
    assert text == ""
    assert asr._model is None

# ☕ Shiki Natsume (四季夏目)

[中文](README.md) · **English** · [日本語](README.ja.md)

A private local companion: chat, long-term memory, listen and speak, a moving Live2D skin, and later a desktop pet that can see your screen. QQ / WeChat come last. No livestream. She is not a helpdesk.

> She looks cold. She is just bad at saying what she actually feels.

![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)
![Python: 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)
![CI](https://img.shields.io/github/actions/workflow/status/ayame-aqua/shiki-natsume/ci.yml?branch=main&label=CI)
![Latest Tag](https://img.shields.io/github/v/tag/ayame-aqua/shiki-natsume?label=release&color=cyan)

[Plan](docs/开发计划/开发文档.md) · [Two modes](docs/开发计划/双模式说明.md) · [Character](characters/natsume.md) · [What we borrow](docs/开发计划/借鉴.md) · [Changelog](docs/变更/README.md)

---

## What this is

A **Shiki Natsume** from *Café Stella and the Reaper's Butterflies*. Canon lives in `characters/natsume.md`. Do not write her as a generic assistant, and do not write her as ATRI.

The main line tracks [Project AIRI](https://github.com/moeru-ai/airi)-class local features (chat / memory / voice / Live2D / screen), **with our own models**. Copy the wiring. Do not fork another AIRI or Artemis.

Local talk and QQ talk are **not the same voice**:

| | Local / desktop pet | QQ (P6, last) |
| --- | --- | --- |
| Pace | Continuous, she often starts | She decides whether to speak |
| What she sees | Later: your screen | Group messages |
| How she answers | Text + Japanese TTS + skin | Short lines, stickers, MCP images |

Current tag **v0.58**. Web chat, memory, the voice path, and a Live2D placeholder are in the repo. The desktop window, screen watch, and QQ login are not.

---

## What actually runs

Acceptance is on this machine. Marketing does not count.

| Feature | Status |
| --- | --- |
| Web text chat + `[[natsume]]` trailer | Closed (P1) |
| SQLite facts / episode vectors / relationship axes | Accepted locally (P2) |
| Japanese TTS after you type | Wired; wait until you hear a local wav (P3-A) |
| Mic ASR, Talk button, auto turn | Wired; wait until you speak two turns (P3-B / P3-C) |
| Left-side Live2D or “no model” | Wired (P4). No skin in the repo |
| Lip sync / five emotions | AnalyserNode + `emotionMap` wired; needs a Cubism 4 skin |
| Transparent pet window, screen, barge-in | Not started (P5) |
| QQ / WeChat login | Forbidden until P5 is accepted. QQ will be DSH qqbot I/O only (P6) |

---

## Architecture

```
Browser 127.0.0.1:8787
  text / mic / TTS playback
  Live2D canvas (only if a skin is present)
        │  WebSocket /ws/chat
        ▼
FastAPI  src/main.py
        │
        ▼
Gateway ──► Agent (persona + memory + LLM)
        │         parse [[natsume]]
        ▼
   Outbound.texts / speech_ja / emotion
        │
        ├─► Chinese bubble
        └─► local GPT-SoVITS :9880  → wav → AudioContext → mouth
```

LLM defaults to a cloud OpenAI-compatible API (DeepSeek Flash). Keys stay in `.env`. A local base model is P8. Do not kill the chat model to make TTS work.

---

## Quick start

### Needs

- Windows. Python 3.11+
- Chrome / Edge
- An LLM key (DeepSeek by default)
- Voice: a local GPT-SoVITS `api_v2` on `127.0.0.1:9880`. Weights live in another project and stay out of this repo
- Hearing you: `pip install -e ".[speech]"`, plus local `torch`. Default ASR is Confucius 4; SenseVoice is the fallback

```text
git clone https://github.com/ayame-aqua/shiki-natsume.git
cd shiki-natsume
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
# fill LLM_API_KEY
python -m src.main
```

Open `http://127.0.0.1:8787`. Without a skin the left panel says the model is missing; chat on the right still works.

Start SoVITS from its own project, for example:

```text
python api_v2.py -a 127.0.0.1 -p 9880 -c GPT_SoVITS/configs/tts_infer_natsume.yaml
```

Details: [local assets](docs/本地资源.md).

---

## Live2D (P4)

Driving follows AIRI’s `pixi-live2d-display` and Artemis’s thin control surface. The mouth uses RMS of the TTS wav, not a fake open. Emotion comes only from the five `[[natsume]]` states: `neutral` / `happy` / `sad` / `angry` / `shy`.

Runtime:

- PixiJS 7.4.2
- `pixi-live2d-display@0.5.0-beta` (cubism4)
- Cubism **Core 4** (official CDN). Core 5+ clips and breaks layers
- Export with **Cubism 4**, not 5

Put a skin you have the right to use in `web/live2d/natsume/` and edit `web/live2d/model_dict.json`:

```json
[
  {
    "name": "natsume",
    "url": "/live2d/natsume/model.model3.json",
    "kScale": 0.4,
    "emotionMap": {
      "neutral": "idle",
      "happy": "smile",
      "sad": "sad",
      "angry": "angry",
      "shy": "blush"
    }
  }
]
```

`.png` / `.moc3` / `.model3.json` and friends are gitignored. Do **not** push official unpacks or Cubism Core. See [web/live2d/README.md](web/live2d/README.md) and the [P4 plan](docs/开发计划/P4-Live2D口型与表情/方案.md).

GPT can draw the art. It cannot emit `.moc3`. Mesh and rigging stay in Live2D Cubism Editor.

---

## Voice (P3)

| | Engine | Notes |
| --- | --- | --- |
| Speak | Local GPT-SoVITS | Only Japanese `speech_ja`. Chinese bubble is a parallel translation |
| Hear | Confucius 4 first | Sticky fallback to SenseVoice-Small |
| Turns | Browser VAD | Talk starts capture on first speech; no new turn while she talks |

The first TTS clip uses an already-unlocked `AudioContext` so the click gesture does not expire. Capture must not loop the speakers, or the volume meter stays at 0.

---

## Memory (P2)

Recall order is fixed: **persona < full profile < core impressions < relationship < style ≤8 < episodes that pass the bar**.

- P2-A: name, relation, explicit “remember this”, forget, `/memory`
- P2-B: episode vectors (LanceDB), slang, pending confirmations
- P2-C: diary, retrieval threshold, energy / awkwardness / closeness (tone only; they do not change who she is)

Unconfirmed pending facts stay out of the prompt. `data/` is not in git.

---

## Roadmap

Numbers are execution order. A hard dependency that is not accepted blocks the next hard stage.

`P1 → P2-A → P3-A → P4 → P5 → (local alignment) → P6 → P7`. P3-B / P3-C do not block lip sync. P8 does not block the pet window.

| | Stage | Status |
| --- | --- | --- |
| P1 | Web text + persona | Closed |
| P2-A / B / C | Long-term memory | Accepted / closed |
| P3-A | Speak | Wired in repo |
| P3-B / C | Hear / live turns | Wired in repo |
| P4 | Live2D mouth + face | Wired; waiting for a skin |
| P5 | Pet window + screen + barge-in | Not started. Local alignment closes here |
| P6 | QQ | Last. DSH qqbot is I/O only |
| P7 | WeChat | Last. Compliance first |
| P8 | Own base model + LoRA | Source lines from the original Natsume; no training now |

No QQ / WeChat login code until P5 passes.

---

## Stack

| Layer | Now |
| --- | --- |
| Language | Python 3.11+ |
| Backend | FastAPI + WebSocket |
| Frontend | Static HTML / JS / CSS |
| LLM | Cloud OpenAI-compatible; DeepSeek Flash by default |
| Persona | `characters/natsume.md` + `[[natsume]]` |
| Memory | SQLite + LanceDB |
| TTS | Local GPT-SoVITS HTTP |
| ASR | Confucius 4 → SenseVoice → Whisper |
| Live2D | pixi-live2d-display 0.5.0-beta + Cubism Core 4 |
| QQ (planned) | Official DSH qqbot as a pipe only |

Rules live in `.cursor/rules/` plus the Alibaba engineer handbook floor: names that mean something, no magic numbers, failures get logs, secrets stay out of logs.

---

## Layout

```text
shiki-natsume/
  characters/natsume.md
  config.yaml
  docs/开发计划/          plan, two modes, P1–P8, what we borrow
  docs/变更/              every small version
  src/core/               Agent, protocol, session
  src/memory/
  src/speech/
  src/channels/           web / voice; qq and wechat are shells
  web/                    chat page + live2d.js
  web/live2d/             config; skins stay local
  tests/
```

---

## Docs

- [Plan](docs/开发计划/开发文档.md)
- [Two modes](docs/开发计划/双模式说明.md)
- [P1](docs/开发计划/P1-网页文字聊天与人设/方案.md) · [P2](docs/开发计划/P2-长期记忆/方案.md) · [P3](docs/开发计划/P3-语音听和说/方案.md) · [P4](docs/开发计划/P4-Live2D口型与表情/方案.md) · [P5](docs/开发计划/P5-打断情绪与桌宠/方案.md) · [P6](docs/开发计划/P6-QQ通道/方案.md) · [P7](docs/开发计划/P7-微信通道/方案.md) · [P8](docs/开发计划/P8-自有底模与LoRA/方案.md)
- [AIRI / FaustBot / Artemis / DSH](docs/开发计划/借鉴.md)
- [Local speech assets](docs/本地资源.md)
- [Changelog](docs/变更/README.md)

---

## Privacy and copyright

1. Personal use. Source is MIT. The character is from Yuzusoft’s *Café Stella and the Reaper's Butterflies*; rights stay with the rights holders.
2. Official unpacked models, Cubism Core, SoVITS weights, reference wavs, and game lines **must not** enter the public repo.
3. Learn Artemis / AIRI wiring. Do not copy their skins or weights.
4. Keys stay in `.env`. Logs never print tokens.
5. Personal WeChat needs a compliance path first; otherwise keep only an uninstallable experiment adapter.

---

## Thanks

- [Project AIRI](https://github.com/moeru-ai/airi) — pet window, pixi-live2d-display, SoVITS HTTP, screenshot wiring
- [Artemis](https://github.com/momori777/Artemis) — persona alignment, memory layers, thin Live2D HTTP bridge, Cubism Core 4. Official skins stay out
- [FaustBot](https://github.com/liwusen/FaustBot-llm-vtuber) — structure only (GPL; no code)
- [pixi-live2d-display](https://github.com/guansss/pixi-live2d-display) — @guansss
- Live2D Inc. — Cubism SDK (non-commercial terms are theirs)

Source is [MIT](LICENSE). May she be the overly sweet coffee on the other side of your screen.

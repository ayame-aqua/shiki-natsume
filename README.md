# ☕ 四季夏目 (Shiki Natsume)

**中文** · [English](README.en.md) · [日本語](README.ja.md)

只给自己用的本机数字陪伴：先做成能对话、有长期记忆、能听能说、皮会动、知道你电脑上在做什么的桌宠。QQ / 微信放在最后。不直播。她不是客服。

> 「看起来很高冷，其实只是不太擅长把心事说出口。」

![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)
![Python: 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)
![CI](https://img.shields.io/github/actions/workflow/status/ayame-aqua/shiki-natsume/ci.yml?branch=main&label=CI)
![Latest Tag](https://img.shields.io/github/v/tag/ayame-aqua/shiki-natsume?label=release&color=cyan)

[总纲](docs/开发计划/开发文档.md) · [双模式](docs/开发计划/双模式说明.md) · [人设](characters/natsume.md) · [借鉴](docs/开发计划/借鉴.md) · [变更](docs/变更/README.md)

---

## 这是什么

做一个 **四季夏目**（《星光咖啡馆与死神之蝶》）。人设以 `characters/natsume.md` 为准，不要写成通用助手，也不要写成亚托莉。

主线对齐 [Project AIRI](https://github.com/moeru-ai/airi) 那类本机能力（对话 / 记忆 / 语音 / Live2D / 看屏），**模型跑我们自己的**。抄接法，不 Fork 成又一个 AIRI / Artemis。

本地和 QQ **不是同一种说话方式**：

| | 本机 / 桌宠 | QQ（P6，最后出门） |
| --- | --- | --- |
| 节奏 | 连续聊，经常主动找你 | 自己决定说不说 |
| 看见什么 | 以后能看你电脑上在做什么 | 群消息 |
| 表达 | 文字 + 日语 TTS + 皮 | 短句、表情包、MCP 生图 |

当前版本 **v0.62**。网页聊天、记忆、语音链路、Live2D 占位、透明桌宠窗和冷场主动已经在仓库里。看屏、打断、QQ 登录还没有。

---

## 现在能跑什么

以本机验收为准，不是 README 吹过就算。

| 能力 | 状态 |
| --- | --- |
| 网页文字聊天 + `[[natsume]]` 尾块 | 已关闭（P1） |
| SQLite 事实 / 情节向量 / 相处状态 | 本机已验收（P2） |
| 打字后 GPT-SoVITS 播日语 | 仓库已接线，待你本机听过 wav（P3-A） |
| 麦克风转写、点「对话」自动切句 | 仓库已接线，待本机说两轮（P3-B / P3-C） |
| 聊天页左侧 Live2D 或「未配置模型」 | 仓库已接线（P4）。仓库里没有皮 |
| TTS 口型 / 五态表情 | 代码已接 AnalyserNode 与 `emotionMap`，待本机挂 Cubism 4 皮 |
| 透明桌宠窗、冷场主动、勿扰 | 仓库已接线（P5 切片 1–2）。看屏 / 打断未做 |
| QQ / 微信登录 | 禁止。P5 没验收不开工。QQ 通道已定为 DSH qqbot 只收发（P6） |

---

## 架构

```
浏览器 127.0.0.1:8787
  文字 / 麦克风 / 播放 TTS
  Live2D canvas（有皮才渲染）
        │  WebSocket /ws/chat
        ▼
FastAPI  src/main.py
        │
        ▼
Gateway ──► Agent（人设 + 记忆 + LLM）
        │         解析 [[natsume]]
        ▼
   Outbound.texts / speech_ja / emotion
        │
        ├─► 中文气泡
        └─► 本机 GPT-SoVITS :9880  → wav → AudioContext → 口型
```

LLM 默认云端 OpenAI 兼容接口（DeepSeek Flash）。密钥只在 `.env`。本机大模型排 P8，不为 TTS 杀掉对话模型。

---

## 快速开始

### 环境

- Windows。Python 3.11+
- 浏览器用 Chrome / Edge
- LLM Key（默认 DeepSeek）
- 要出声：本机已启动的 GPT-SoVITS `api_v2`（默认 `127.0.0.1:9880`）。权重在别的项目，不进本仓库
- 要听你：`pip install -e ".[speech]"`，另需本机 `torch`。默认 ASR 是孔子 4，失败退 SenseVoice

```text
git clone https://github.com/ayame-aqua/shiki-natsume.git
cd shiki-natsume
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
# 填 LLM_API_KEY
python -m src.main
```

打开 `http://127.0.0.1:8787`。没配皮时左侧是「未配置模型」，右边照常聊天。

### 桌宠窗口（P5）

```bash
cd desktop
npm install  # 首次运行
npm start
```

透明、置顶、可拖拽，自动加载上述 FastAPI。冷场后会主动开口，托盘可开勿扰。详见 [desktop/README.md](desktop/README.md)。

SoVITS 在原工程目录启动，例如：

```text
python api_v2.py -a 127.0.0.1 -p 9880 -c GPT_SoVITS/configs/tts_infer_natsume.yaml
```

细节见 [本地资源](docs/本地资源.md)。

### DeepSeek Harness（旁路，不是大脑）

双击 `scripts/start_dsh.bat`，或在仓库根目录：

```text
.\scripts\start_dsh.bat
```

从用户主目录起官方 `dsh web`（默认 `http://127.0.0.1:3080`）。本机需已装 Node 24.9+ 和全局 `dsh`（`npm install -g @deepseek-ai/dsh`）。关掉它不影响网页 / 语音 / 桌宠。P6 QQ 桥还没接，这个脚本不登录 QQ。

---

## Live2D（P4）

驱法借鉴 AIRI 的 `pixi-live2d-display` 和 Artemis 的薄控制面。口型吃 TTS 的 wav RMS，不走假张嘴。emotion 只来自 `[[natsume]]` 五态：`neutral` / `happy` / `sad` / `angry` / `shy`。

运行时：

- PixiJS 7.4.2
- `pixi-live2d-display@0.5.0-beta`（cubism4）
- Cubism **Core 4**（官方 CDN）。Core 5+ 会裁切、图层花掉
- 导出请用 **Cubism 4**，不要 5

本机自备有权使用的皮，放到 `web/live2d/natsume/`，编辑 `web/live2d/model_dict.json`：

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

`.png` / `.moc3` / `.model3.json` 等已 gitignore。官方拆包、Cubism Core **不要 push**。说明见 [web/live2d/README.md](web/live2d/README.md) 和 [P4 方案](docs/开发计划/P4-Live2D口型与表情/方案.md)。

GPT 可以出原画，交不出 `.moc3`。切层和绑模用 Live2D Cubism Editor。

---

## 语音（P3）

| | 引擎 | 说明 |
| --- | --- | --- |
| 说 | 本机 GPT-SoVITS | 只吃日语 `speech_ja`。中文气泡并行翻译 |
| 听 | 默认孔子 4（Confucius4-R2T2） | 失败粘住退 SenseVoice-Small |
| 轮次 | 浏览器 VAD | 点「对话」开口即采；她说话时不新开一句 |

第一句 TTS 走已解锁的 `AudioContext`，避免点击手势过期被浏览器拦播放。采集不回灌扬声器，否则音量条会一直是 0。

---

## 记忆（P2）

召回顺序写死：**人设 < profile 全量 < 核心印象 < 相处状态 < style ≤8 < 过线的 episodes**。

- P2-A：称呼、关系、明确「记住」的事实、忘掉、`/memory` 页
- P2-B：情节向量（LanceDB）、风格/黑话、pending 确认
- P2-C：日记、检索门槛、精力/别扭/亲近三轴（只调语气，不改她是谁）

未确认的 pending 不进 prompt。`data/` 不进 git。

---

## 路线图

编号 = 执行顺序。硬依赖未验收，不开始下一硬依赖阶段。

`P1 → P2-A → P3-A → P4 → P5 →（本机对齐）→ P6 → P7`。P3-B / P3-C 不挡口型。P8 不挡桌宠。

| | 阶段 | 状态 |
| --- | --- | --- |
| P1 | 网页文字 + 人设 | 已关闭 |
| P2-A / B / C | 长期记忆 | 已验收 / 已关闭 |
| P3-A | 出声 | 仓库已接线 |
| P3-B / C | 听你 / 实时轮次 | 仓库已接线 |
| P4 | Live2D 口型与表情 | 仓库已接线；待挂皮 |
| P5 | 桌宠窗 + 看屏 + 打断 | 窗 + 冷场主动已接线；看屏 / 打断未做 |
| P6 | QQ | 最后出门。DSH qqbot 只收发 |
| P7 | 微信 | 最后出门。先过合规门 |
| P8 | 自有底模 + LoRA | 主料原作夏目台词；现在不训 |

P5 没过，不开 QQ / 微信登录代码。

---

## 技术选型

| 层 | 现在用什么 |
| --- | --- |
| 语言 | Python 3.11+ |
| 后端 | FastAPI + WebSocket |
| 前端 | 静态 HTML / JS / CSS |
| LLM | 云端 OpenAI 兼容；默认 DeepSeek Flash |
| 人设 | `characters/natsume.md` + `[[natsume]]` |
| 记忆 | SQLite + LanceDB |
| TTS | 本机 GPT-SoVITS HTTP |
| ASR | 孔子 4 → SenseVoice → Whisper |
| Live2D | pixi-live2d-display 0.5.0-beta + Cubism Core 4 |
| 桌宠窗口 | Electron 28（Windows 优先） |
| QQ（计划） | DSH 官方 qqbot 只当通道 |

规范见 `.cursor/rules/` 与阿里巴巴程序员白皮书底线：见名知意、禁止魔法值、失败要有日志、密钥不进日志。

---

## 目录

```text
shiki-natsume/
  characters/natsume.md
  config.yaml
  docs/开发计划/          总纲、双模式、P1–P8 方案、借鉴
  docs/变更/              每个小版本
  src/core/               Agent、协议、会话
  src/memory/
  src/speech/
  src/channels/           web / voice；qq、wechat 空壳
  desktop/                P5 Electron 桌宠窗口
  web/                    聊天页 + live2d.js
  web/live2d/             配置；皮自备不入库
  tests/
```

---

## 文档

- [总纲](docs/开发计划/开发文档.md)
- [双模式](docs/开发计划/双模式说明.md)
- [P1](docs/开发计划/P1-网页文字聊天与人设/方案.md) · [P2](docs/开发计划/P2-长期记忆/方案.md) · [P3](docs/开发计划/P3-语音听和说/方案.md) · [P4](docs/开发计划/P4-Live2D口型与表情/方案.md) · [P5](docs/开发计划/P5-打断情绪与桌宠/方案.md) · [P6](docs/开发计划/P6-QQ通道/方案.md) · [P7](docs/开发计划/P7-微信通道/方案.md) · [P8](docs/开发计划/P8-自有底模与LoRA/方案.md)
- [借鉴：AIRI / FaustBot / Artemis / DSH](docs/开发计划/借鉴.md)
- [本地语音资源](docs/本地资源.md)
- [变更记录](docs/变更/README.md)

---

## 隐私与版权

1. 自用。源码 MIT。角色出自柚子社《星光咖啡馆与死神之蝶》，版权归权利方。
2. 官方拆包模型、Cubism Core、SoVITS 权重、参考 wav、游戏台词 **不准推进公开仓库**。
3. 学 Artemis / AIRI 的接法，不搬他们仓库里的皮和权重。
4. 密钥只在 `.env`。日志不打 Token。
5. 个人微信必须先有合规路径；没有就只留可卸载的实验适配器。

---

## 致谢

- [Project AIRI](https://github.com/moeru-ai/airi) — 桌宠窗、pixi-live2d-display、SoVITS HTTP、截屏接法
- [Artemis](https://github.com/momori777/Artemis) — 人设对齐、记忆分层、薄 Live2D HTTP 桥、Cubism Core 4 约束。不搬官方皮
- [FaustBot](https://github.com/liwusen/FaustBot-llm-vtuber) — 只学结构（GPL，不合入代码）
- [pixi-live2d-display](https://github.com/guansss/pixi-live2d-display) — @guansss
- Live2D Inc. — Cubism SDK（非商用条款以官方为准）

源码 [MIT](LICENSE)。愿她成为你屏幕彼端那杯加了很多糖的咖啡。

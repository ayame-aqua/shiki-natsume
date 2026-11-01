# ☕ 四季ナツメ (Shiki Natsume)

[中文](README.md) · [English](README.en.md) · **日本語**

自分用のローカルなデジタルコンパニオンです。会話、長期記憶、聞き取りと発話、動く Live2D、あとで画面を見られるデスクトップペット。QQ / WeChat は最後。配信しない。彼女はヘルプデスクではない。

> 冷たく見えるだけ。本音をうまく言えないだけ。

![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)
![Python: 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)
![CI](https://img.shields.io/github/actions/workflow/status/ayame-aqua/shiki-natsume/ci.yml?branch=main&label=CI)
![Latest Tag](https://img.shields.io/github/v/tag/ayame-aqua/shiki-natsume?label=release&color=cyan)

[総綱](docs/开发计划/开发文档.md) · [二つの話し方](docs/开发计划/双模式说明.md) · [人設](characters/natsume.md) · [借りたもの](docs/开发计划/借鉴.md) · [変更](docs/变更/README.md)

---

## これは何か

『喫茶ステラと死神の蝶』の **四季ナツメ**。人設は `characters/natsume.md` が正。汎用アシスタントにも、アトリにもしない。

主線は [Project AIRI](https://github.com/moeru-ai/airi) 級のローカル能力（会話 / 記憶 / 音声 / Live2D / 画面）に揃える。**モデルはこちらで動かす。** 配線は借りる。AIRI や Artemis の二番煎じにはしない。

ローカルと QQ は **同じ口調ではない**：

| | ローカル / デスクトップペット | QQ（P6、最後） |
| --- | --- | --- |
| テンポ | 続きで話す。彼女から来ることも多い | 話すか黙るかは彼女が決める |
| 見えるもの | あとで：あなたの画面 | グループの発言 |
| 返し方 | 文字 + 日本語 TTS + 皮 | 短い文、スタンプ、MCP 画像 |

いまのタグは **v0.62**。ウェブチャット、記憶、音声経路、Live2D のプレースホルダ、透明ペット窓、沈黙後の話しかけはリポジトリにある。画面監視、割り込み、QQ ログインはまだない。

---

## いま動くもの

受け入れは本機。README に書いただけでは通らない。

| 機能 | 状態 |
| --- | --- |
| ウェブ文字チャット + `[[natsume]]` 末尾ブロック | 閉じた（P1） |
| SQLite 事実 / エピソードベクトル / 関係の軸 | 本機で受け入れ済み（P2） |
| 入力後に GPT-SoVITS で日本語を再生 | 配線済み。本機で wav を聞いてから完了（P3-A） |
| マイク転写、「対話」で自動ターン | 配線済み。本機で二往復してから（P3-B / P3-C） |
| 左の Live2D、または「モデル未設定」 | 配線済み（P4）。皮はリポジトリにない |
| リップシンク / 五つの表情 | AnalyserNode と `emotionMap` は配線済み。Cubism 4 の皮が要る |
| 透明ペット窓、沈黙後の話しかけ、邪魔しない | 配線済み（P5 切片 1–2）。画面 / 割り込みは未着手 |
| QQ / WeChat ログイン | 禁止。P5 未受け入れでは着手しない。QQ は DSH qqbot の送受信だけ（P6） |

---

## 構成

```
ブラウザ 127.0.0.1:8787
  文字 / マイク / TTS 再生
  Live2D canvas（皮があるときだけ描画）
        │  WebSocket /ws/chat
        ▼
FastAPI  src/main.py
        │
        ▼
Gateway ──► Agent（人設 + 記憶 + LLM）
        │         [[natsume]] を解釈
        ▼
   Outbound.texts / speech_ja / emotion
        │
        ├─► 中国語の吹き出し
        └─► 本機 GPT-SoVITS :9880  → wav → AudioContext → 口
```

LLM は既定でクラウドの OpenAI 互換（DeepSeek Flash）。鍵は `.env` だけ。本機の大規模モデルは P8。TTS のために会話モデルを殺さない。

---

## クイックスタート

### 必要なもの

- Windows。Python 3.11+
- Chrome / Edge
- LLM のキー（既定は DeepSeek）
- 声：本機の GPT-SoVITS `api_v2`（既定 `127.0.0.1:9880`）。重みは別プロジェクト。このリポジトリには入れない
- 聞き取り：`pip install -e ".[speech]"` と本機の `torch`。既定 ASR は孔子 4。失敗したら SenseVoice

```text
git clone https://github.com/ayame-aqua/shiki-natsume.git
cd shiki-natsume
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
# LLM_API_KEY を書く
python -m src.main
```

`http://127.0.0.1:8787` を開く。皮が無いとき左は「モデル未設定」。右のチャットはそのまま使える。

### デスクトップ窓（P5）

```bash
cd desktop
npm install
npm start
```

枠なし・透明・最前面。しばらく無視すると彼女から話す。トレイで「邪魔しない」にできる。詳細は [desktop/README.md](desktop/README.md)。

SoVITS は元の工程ディレクトリで起動する。例：

```text
python api_v2.py -a 127.0.0.1 -p 9880 -c GPT_SoVITS/configs/tts_infer_natsume.yaml
```

詳細は [ローカル資源](docs/本地资源.md)。

### DeepSeek Harness（傍系。脳ではない）

`scripts/start_dsh.bat` をダブルクリックするか、リポジトリ根で：

```text
.\scripts\start_dsh.bat
```

ユーザーホームから公式 `dsh web` を起動する（既定 `http://127.0.0.1:3080`）。Node 24.9+ とグローバル `dsh`（`npm install -g @deepseek-ai/dsh`）が必要。止めても Web / 音声 / デスクトップ窓は影響しない。P6 の QQ 橋はまだ無い。このスクリプトは QQ にログインしない。

---

## Live2D（P4）

駆動は AIRI の `pixi-live2d-display` と Artemis の薄い制御面を借りる。口は TTS の wav の RMS。偽の開閉は使わない。emotion は `[[natsume]]` の五態だけ：`neutral` / `happy` / `sad` / `angry` / `shy`。

実行時：

- PixiJS 7.4.2
- `pixi-live2d-display@0.5.0-beta`（cubism4）
- Cubism **Core 4**（公式 CDN）。Core 5+ は切れたりレイヤーが壊れたりする
- 書き出しは **Cubism 4**。5 は使わない

使う権利のある皮を `web/live2d/natsume/` に置き、`web/live2d/model_dict.json` を書く：

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

`.png` / `.moc3` / `.model3.json` などは gitignore 済み。公式の分解モデルと Cubism Core は **push しない**。説明は [web/live2d/README.md](web/live2d/README.md) と [P4 方案](docs/开发计划/P4-Live2D口型与表情/方案.md)。

GPT は原画は出せる。`.moc3` は出せない。メッシュとリグは Live2D Cubism Editor。

---

## 音声（P3）

| | エンジン | 説明 |
| --- | --- | --- |
| 話す | 本機 GPT-SoVITS | 日本語 `speech_ja` だけ。中国語吹き出しは並行翻訳 |
| 聞く | まず孔子 4 | 失敗したら SenseVoice-Small に固定 |
| ターン | ブラウザ VAD | 「対話」で発話開始から収録。彼女が話している間は新しい一文を開かない |

最初の TTS は、すでに解除した `AudioContext` で再生する。クリックのジェスチャが切れてブラウザに止められないようにする。収録がスピーカーを回すと、音量バーがずっと 0 になる。

---

## 記憶（P2）

想起の順は固定：**人設 < profile 全量 < 核の印象 < 関係の状態 < style ≤8 < 閾値を超えた episodes**。

- P2-A：呼び方、関係、「覚えて」と明示した事実、忘れ、`/memory`
- P2-B：エピソードベクトル（LanceDB）、スラング、pending 確認
- P2-C：日記、検索の閾値、元気 / ぎこちなさ / 親しさ（口調だけ。彼女は誰かは変えない）

未確認の pending は prompt に入れない。`data/` は git に入れない。

---

## ロードマップ

番号は実行順。硬い依存が未受け入れなら、次の硬い段階は始めない。

`P1 → P2-A → P3-A → P4 → P5 →（本機揃え）→ P6 → P7`。P3-B / P3-C は口パクを止めない。P8 はペット窓を止めない。

| | 段階 | 状態 |
| --- | --- | --- |
| P1 | ウェブ文字 + 人設 | 閉じた |
| P2-A / B / C | 長期記憶 | 受け入れ / 閉じた |
| P3-A | 発話 | リポジトリに配線済み |
| P3-B / C | 聞き取り / リアルタイムターン | リポジトリに配線済み |
| P4 | Live2D の口と表情 | 配線済み。皮待ち |
| P5 | ペット窓 + 画面 + 割り込み | 窓と沈黙後の話しかけは配線済み。画面 / 割り込みは未着手 |
| P6 | QQ | 最後。DSH qqbot は送受信だけ |
| P7 | WeChat | 最後。まずコンプライアンス |
| P8 | 自前の基盤 + LoRA | 原作ナツメの台詞が主。いまは訓練しない |

P5 が通るまで、QQ / WeChat のログインコードは書かない。

---

## 技術

| 層 | いま使うもの |
| --- | --- |
| 言語 | Python 3.11+ |
| バックエンド | FastAPI + WebSocket |
| フロント | 静的 HTML / JS / CSS |
| LLM | クラウド OpenAI 互換。既定 DeepSeek Flash |
| 人設 | `characters/natsume.md` + `[[natsume]]` |
| 記憶 | SQLite + LanceDB |
| TTS | 本機 GPT-SoVITS HTTP |
| ASR | 孔子 4 → SenseVoice → Whisper |
| Live2D | pixi-live2d-display 0.5.0-beta + Cubism Core 4 |
| ペット窓 | Electron 28（Windows 優先） |
| QQ（予定） | 公式 DSH qqbot を通路だけにする |

規則は `.cursor/rules/` とアリババの技術者白書の底線：名前は意味を持つ、マジックナンバー禁止、失敗はログ、鍵はログに出さない。

---

## ディレクトリ

```text
shiki-natsume/
  characters/natsume.md
  config.yaml
  docs/开发计划/          総綱、二つの話し方、P1–P8、借りたもの
  docs/变更/              小さな版ごと
  src/core/               Agent、プロトコル、セッション
  src/memory/
  src/speech/
  src/channels/           web / voice。qq と wechat は殻
  desktop/                P5 Electron ペット窓
  web/                    チャットページ + live2d.js
  web/live2d/             設定。皮は入れない
  tests/
```

---

## 文書

- [総綱](docs/开发计划/开发文档.md)
- [二つの話し方](docs/开发计划/双模式说明.md)
- [P1](docs/开发计划/P1-网页文字聊天与人设/方案.md) · [P2](docs/开发计划/P2-长期记忆/方案.md) · [P3](docs/开发计划/P3-语音听和说/方案.md) · [P4](docs/开发计划/P4-Live2D口型与表情/方案.md) · [P5](docs/开发计划/P5-打断情绪与桌宠/方案.md) · [P6](docs/开发计划/P6-QQ通道/方案.md) · [P7](docs/开发计划/P7-微信通道/方案.md) · [P8](docs/开发计划/P8-自有底模与LoRA/方案.md)
- [AIRI / FaustBot / Artemis / DSH](docs/开发计划/借鉴.md)
- [ローカル音声資源](docs/本地资源.md)
- [変更記録](docs/变更/README.md)

---

## プライバシーと著作権

1. 自分用。ソースは MIT。キャラはゆずソフト『喫茶ステラと死神の蝶』。権利は権利者。
2. 公式の分解モデル、Cubism Core、SoVITS の重み、参照 wav、ゲーム台詞は **公開リポジトリに入れない**。
3. Artemis / AIRI の配線は学ぶ。皮と重みは持ってこない。
4. 鍵は `.env` だけ。ログに Token を出さない。
5. 個人 WeChat は先にコンプライアンス経路。無ければ外せる実験アダプタだけ。

---

## 謝辞

- [Project AIRI](https://github.com/moeru-ai/airi) — ペット窓、pixi-live2d-display、SoVITS HTTP、画面キャプチャ
- [Artemis](https://github.com/momori777/Artemis) — 人設、記憶の層、薄い Live2D HTTP 橋、Cubism Core 4。公式皮は持ってこない
- [FaustBot](https://github.com/liwusen/FaustBot-llm-vtuber) — 構造だけ（GPL。コードは入れない）
- [pixi-live2d-display](https://github.com/guansss/pixi-live2d-display) — @guansss
- Live2D Inc. — Cubism SDK（非商用条件は公式）

ソースは [MIT](LICENSE)。画面の向こうの、砂糖をたくさん入れた一杯になりますように。

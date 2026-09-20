# 「听你走 AudioTTS、她仍走 GPT-SoVITS」可行性

| 项 | 内容 |
| --- | --- |
| 日期 | 2026-09-20 |
| 相关阶段 | [P3 方案](./方案.md) P3-B（听）/ P3-A（说） |
| 问题 | 现在识别你的声音很不准；想把 **识别** 换成 AudioTTS；**她说话仍走 GPT-SoVITS** |
| 结论 | **听和说拆开这条路线可行，而且仓库已经是这样拆的。** 名为 AudioTTS 的公开产品是 **文字转语音下载器，不能识别人声**，不能当 ASR 换上去。若你指的是 **FunAudioLLM** 这一家：识别侧我们已经在用它的 **Fun-ASR-Nano**；要试更准，应换同栈的 **SenseVoice-Small**，而不是换 CosyVoice / AudioTTS。 |

---

## 1. 结论（先看这张表）

| 说法 | 是否可行 | 说明 |
| --- | --- | --- |
| 识别换引擎，她出声仍用 GPT-SoVITS | **可行** | `transcribe()` 和 `synthesize()` 已经分开；P3-A 只打 `9880` |
| 用网上的 **AudioTTS**（Chrome 扩展）听你说话 | **不可行** | 那是网页 **TTS 下载**，没有语音转文字接口 |
| 用 **FunAudioLLM 的 CosyVoice** 听你说话 | **不可行** | CosyVoice 是 **合成**，不是识别；还会和夏目 SoVITS 抢「谁出声」 |
| 用 **FunAudioLLM 的 SenseVoice** 听你说话，SoVITS 不动 | **可行，建议先试** | 同一套 FunASR 加载路径；`asr_model: sensevoice-small` |
| 继续用 Fun-ASR-Nano，只换 AudioTTS 当「更准的识别」 | **无效** | 当前主力已经是 `FunAudioLLM/Fun-ASR-Nano-2512` |

**她说话走 GPT-SoVITS 不变：这条约束成立，也不该动。**

---

## 2. 你要的拆法，架构上已经成立

```
你的麦克风  -->  ASR（只产出中文文本）--> 同一条 Agent / 记忆
她的日语台词 -->  GPT-SoVITS 9880   --> wav 播放（P3-A，不换）
```

代码边界：

- 听：`src/speech/asr.py` 的 `transcribe`
- 说：`src/speech/tts.py` 的 `synthesize`，只吃 `speech_ja`

换识别后端 **不必** 改 Agent、不必改 SoVITS 权重、不必改口型用的 wav。这是对的技术路线。

不准的是 **听**，不是 **说**。把 TTS 产品接到识别口上，方向反了。

---

## 3. 「AudioTTS」对上的三件事

公开检索里，叫 AudioTTS 的东西是 Chrome 扩展：从 Azure / Google / ChatGPT 页面 **下载合成音频**。没有麦克风转写、没有本地 `transcribe` API。接到本仓库的 `user_audio` 上 **做不到**。

FunAudioLLM 这一家容易口误成「Audio TTS」，因为它同时卖听和说：

| 组件 | 干什么 | 我们现在 |
| --- | --- | --- |
| Fun-ASR-Nano | 识别（LLM 解码） | **正在用**（`config.yaml`：`asr_model: fun-asr-nano`） |
| SenseVoice-Small | 识别（更快、中文 CER 略好） | 代码已认 `sensevoice`，**默认没开** |
| CosyVoice | 合成（克隆音色） | **不要接**；夏目音色已经在 SoVITS |

所以：若「试试 AudioTTS」是想换一家识别，**不是新路线，是已经在用的那一家**；要更准，试 SenseVoice，不要试 CosyVoice / Chrome AudioTTS。

---

## 4. 为什么现在会「非常不准」（不一定是模型选错）

Fun-ASR-Nano 公开中文 CER 大约 8%，比 Whisper-small（二十多）好一截。体感「非常不准」更常见是 **送进模型的音频已经坏了**，或 **后处理把对的句子丢掉**：

1. **P3-C 前端切句**：停顿约半秒、最长 7 秒强制切断。半句话、气口、环境声都会进 ASR。
2. **浏览器是 webm**：先解码再写成 16 kHz wav。麦驱动、回声消除、她外放漏进麦，都会脏。
3. **`is_clear_transcript` 只认 ≥2 个汉字**：英文幻觉会丢掉（这是对的）；「嗯」「好」这种短答应也会当没听清。
4. **Fun-ASR-Nano 是小 LLM 解码**：短、吵、被切碎的片段更容易编词，不像 SenseVoice 那种非自回归一遍出字。
5. **失败退 Faster-Whisper `small`**：中文更差。若 FunASR 加载失败，你会在不知情时走 Whisper。

在换产品之前，应先确认日志里 `asr_ok` / `asr_unclear` / `asr_fallback` 走的是哪条后端，以及切句长度是否只有几百毫秒。

---

## 5. 若目标是「听得更准、SoVITS 不动」——建议顺序

**可以做（本机、不挡 P3-A）：**

1. 默认 ASR 改 **SenseVoice-Small**（`iic/SenseVoiceSmall`）。同一 FunASR + `fsmn-vad`，改 `config.yaml` 一行。公开数字上中文 CER 略优于 Nano，且更不容易「编一句」。
2. 对同一段你的录音，用 `scripts/check_asr.py` 并排看 Nano vs SenseVoice vs Whisper，避免只靠聊天体感。
3. 仍不准再查切句：外放改耳机、把最短有效语音加长、确认没有 fallback。

**可以以后做、现在不必：**

- 云端中文 ASR（阿里云 / 腾讯云一句话识别）：准，但密钥、延迟、隐私；不是 AudioTTS。
- Paraformer-zh：普通话生产栈，同样走 FunASR。

**不要做：**

- 用 AudioTTS 扩展、CosyVoice、任何 TTS 去「识别」。
- 为了识别去换 GPT-SoVITS，或让 CosyVoice 顶替夏目出声。
- 把听和说合成一个 Audio LLM 全双工（那是另一条产品线，会搅乱 Agent 和记忆）。

---

## 6. 总判

- **「识别换路、合成仍 SoVITS」：可行。**
- **「识别走 AudioTTS」：按该名字的公开产品，不可行。**
- **「识别走 FunAudioLLM 里真正负责听的模型」：可行；Nano 已在用，下一步试 SenseVoice，而不是 TTS。**

P3-A 的 GPT-SoVITS 约束保持不变。

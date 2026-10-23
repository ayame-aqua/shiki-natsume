# Live2D 模型目录（P4）

## 目录结构

将有权使用的 Cubism 3–5 模型放到本目录下的子文件夹中，例如：

```
web/live2d/
├── model_dict.json          # 模型配置文件
├── natsume/                 # 夏目模型目录（示例）
│   ├── model.model3.json    # Cubism 3 模型定义
│   ├── *.moc3               # 模型数据
│   ├── *.png                # 纹理贴图
│   ├── motions/             # 动作文件
│   └── expressions/         # 表情文件
└── README.md
```

## 配置文件示例

编辑 `model_dict.json`：

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

### 配置说明

- `name`：模型名称（标识用）
- `url`：模型 JSON 文件的 URL 路径（相对于 `/live2d`）
- `kScale`：缩放比例（0.1–1.0，根据模型大小调整）
- `emotionMap`：表情映射关系
  - 键：Agent 输出的 emotion（neutral/happy/sad/angry/shy）
  - 值：模型中对应的 motion 名称（需与模型文件中的 motion 组名对应）

## 表情映射

Agent 会输出以下 5 种基础情绪：

- `neutral`：中性、平静
- `happy`：高兴、开心
- `sad`：悲伤、失落
- `angry`：生气、不满
- `shy`：害羞、腼腆

将这些情绪映射到模型中的 motion 名称。如果模型中没有对应的 motion，会回退到 `idle` 并在控制台输出警告。

## 版权声明

**重要提示：**

- 仅使用您有权使用的模型文件
- 官方游戏拆包的模型、Cubism SDK Core、未授权的角色资源**禁止**提交到公开仓库
- `.gitignore` 已屏蔽 `*.png` 和 `*.moc3`，但请自觉遵守版权规范
- 本项目仅供个人学习研究使用

## 功能说明

- **自动口型同步**：播放 TTS 时，根据音频振幅驱动 `ParamMouthOpenY`
- **表情切换**：根据对话内容自动切换表情，2 秒后回到中性
- **Idle 动画**：
  - 眨眼：每 4 秒触发一次
  - 呼吸：平滑循环变化
- **优雅降级**：未配置模型时显示"未配置模型"占位符，不影响聊天和语音功能

## 故障排查

### 模型不显示

1. 检查 `model_dict.json` 是否配置正确
2. 确认模型文件路径是否正确（相对于 `web/live2d/`）
3. 打开浏览器控制台查看错误日志
4. 确认模型是 Cubism 3–5 格式（不支持 Cubism 2）

### 表情不切换

1. 检查 `emotionMap` 中的 motion 名称是否与模型文件中的一致
2. 查看浏览器控制台是否有"Emotion motion not found"警告
3. 确认模型的 `.model3.json` 中定义了对应的 motion 组

### 口型不动

1. 确认 TTS 音频正常播放
2. 检查模型是否有 `ParamMouthOpenY` 参数
3. 查看浏览器控制台是否有 AudioContext 错误

## 技术细节

- 前端库：pixi.js@7.4.2 + pixi-live2d-display@1.2.0
- 驱动方式：RMS 振幅分析（AnalyserNode）
- 平滑系数：0.35（可在 `web/live2d.js` 中调整）
- 口型参数：`ParamMouthOpenY`（标准 Cubism 参数）

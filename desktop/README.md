# 四季夏目桌宠窗口

P5 桌宠：Electron 透明窗口 + 主动搭话。

## 功能

### 切片 1（v0.59）
- ✅ 无边框透明窗口
- ✅ 始终置顶
- ✅ 可拖拽（点击 Live2D 区域或上方标题栏）
- ✅ 持久化窗口位置
- ✅ 自动连接本地 FastAPI (127.0.0.1:8787)
- ✅ 调试窗口自动分离

### 切片 2（v0.60）
- ✅ **冷场主动搭话**：无互动一段时间后主动说话
- ✅ **勿扰模式**：托盘菜单切换，暂停主动搭话
- ✅ **冷却机制**：避免频繁打扰
- ✅ **系统托盘**：右键菜单控制勿扰、显示/退出

## 运行要求

1. **FastAPI 后端必须先启动**：
   ```bash
   cd /workspace
   python -m src.main
   ```
   确保 http://127.0.0.1:8787 可访问。

2. Node.js 16+

## 安装

```bash
cd desktop
npm install
```

## 运行

```bash
npm start
```

## 使用

### 基本操作
- **拖动窗口**：点击 Live2D 区域或顶部标题栏拖动
- **调整大小**：拖动窗口边缘（Windows 原生支持）
- **关闭**：关闭按钮或任务栏右键退出

### 主动搭话（切片 2 新增）
- **自动触发**：默认 5 分钟无互动后主动说话
- **冷却时间**：主动搭话后 10 分钟内不会再次主动
- **勿扰模式**：右键托盘图标，勾选「勿扰模式」暂停主动搭话
- **配置调整**：编辑 `config.yaml` 中的 `proactive` 部分

### 配置选项（config.yaml）

```yaml
proactive:
  enabled: true              # 是否启用主动搭话
  idle_timeout_s: 300        # 冷场多久后主动（秒，默认 5 分钟）
  random_talk_prob: 0.1      # 随机碎碎念概率（0-1，暂未实现）
  cooldown_s: 600            # 主动搭话最小间隔（秒，默认 10 分钟）
  do_not_disturb: false      # 初始勿扰状态（可通过托盘菜单切换）
```

## 窗口位置

窗口位置和勿扰状态自动保存在：
- Windows: `%APPDATA%\shiki-natsume-desktop\config.json`
- macOS: `~/Library/Application Support/shiki-natsume-desktop/config.json`
- Linux: `~/.config/shiki-natsume-desktop/config.json`

## 注意事项

- 透明窗口在不同 Windows 版本上表现可能略有差异
- 确保 FastAPI 已启动并监听 8787 端口
- 窗口会自动加载完整的 web UI（包括 Live2D、聊天、语音）
- Live2D 模型需要按 [web/live2d/README.md](../web/live2d/README.md) 配置
- 主动搭话依赖 FastAPI 后端的 `/api/proactive/trigger` 端点

## P5 切片进度

**切片 1**（v0.59）：
- ✅ 最小 Electron shell
- ✅ 无边框、透明、置顶
- ✅ 可拖拽
- ✅ 持久化窗口位置
- ✅ 加载现有 web UI

**切片 2**（v0.60）：
- ✅ 冷场主动搭话
- ✅ 勿扰模式（托盘菜单）
- ✅ 冷却机制
- ✅ 配置持久化

**不在此切片**（后续迭代）：
- ❌ 屏幕截图/CV
- ❌ 语音打断
- ❌ 点击动作（除拖拽外）
- ❌ P6/P7 QQ/微信

## 开发

### 环境变量
- `NODE_ENV=production`：关闭 DevTools 自动打开

### 调试
- 开发模式下自动打开独立 DevTools
- 查看主进程日志：终端输出
- 查看渲染进程日志：DevTools Console

### 主动搭话工作流程
1. Electron 每 60 秒调用 `/api/proactive/trigger`
2. FastAPI 检查空闲时间、冷却时间、勿扰状态
3. 符合条件时生成主动消息，调用 Agent
4. 返回消息和 TTS，渲染进程显示和播放

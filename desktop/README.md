# 四季夏目桌宠窗口

P5 第一切片：Electron 透明桌宠窗口，加载现有 web UI。

## 功能

- ✅ 无边框透明窗口
- ✅ 始终置顶
- ✅ 可拖拽（点击 Live2D 区域或上方标题栏）
- ✅ 持久化窗口位置
- ✅ 自动连接本地 FastAPI (127.0.0.1:8787)
- ✅ 调试窗口自动分离

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

- **拖动窗口**：点击 Live2D 区域或顶部标题栏拖动
- **调整大小**：拖动窗口边缘（Windows 原生支持）
- **关闭**：关闭按钮或任务栏右键退出
- **调试**：自动打开独立 DevTools 窗口

## 窗口位置

窗口位置自动保存在：
- Windows: `%APPDATA%\shiki-natsume-desktop\config.json`
- macOS: `~/Library/Application Support/shiki-natsume-desktop/config.json`
- Linux: `~/.config/shiki-natsume-desktop/config.json`

## 注意事项

- 透明窗口在不同 Windows 版本上表现可能略有差异
- 确保 FastAPI 已启动并监听 8787 端口
- 窗口会自动加载完整的 web UI（包括 Live2D、聊天、语音）
- Live2D 模型需要按 [web/live2d/README.md](../web/live2d/README.md) 配置

## P5 切片 1 范围

当前实现：
- ✅ 最小 Electron shell
- ✅ 无边框、透明、置顶
- ✅ 可拖拽
- ✅ 持久化窗口位置
- ✅ 加载现有 web UI

**不在此切片**（后续迭代）：
- ❌ 主动搭话 tick
- ❌ 屏幕截图/CV
- ❌ 勿扰模式
- ❌ 语音打断
- ❌ 点击动作（除拖拽外）
- ❌ P6/P7 QQ/微信

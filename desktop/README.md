# 四季夏目桌宠窗口

Electron 透明窗口，加载本机 `http://127.0.0.1:8787`。主动搭话由后端判定，气泡和语音仍走网页 WebSocket。

## 功能

- 无边框、透明、置顶、可拖拽
- 记住窗口位置；若上次偏出屏幕，启动时拉回可见工作区
- 冷场后主动开口（复用同一套 Agent / TTS / Live2D）
- 托盘菜单切换勿扰

## 运行

先开后端：

```text
python -m src.main
```

确认浏览器能打开 `http://127.0.0.1:8787`，再开桌宠：

```text
cd desktop
npm install
npm start
```

- 拖动：点标题栏或 Live2D 区域
- 勿扰：右键托盘图标
- 开发时会弹出独立 DevTools；`NODE_ENV=production` 时不弹

## 配置

`config.yaml` 的 `proactive`：

```yaml
proactive:
  enabled: true
  idle_timeout_s: 300
  cooldown_s: 600
  do_not_disturb: false
```

窗口位置和托盘勿扰在用户配置目录，不进仓库。

## 本切片不做

看屏 / 截屏、语音打断、点击动作、QQ / 微信。

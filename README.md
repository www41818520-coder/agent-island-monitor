# Agent Island Monitor

Windows 顶部悬浮的 AI 状态迷你胶囊，灵感来自 Apple Dynamic Island。它用于在后台运行 Codex、Cursor/CC 时，用最小遮挡查看状态，并在需要时展开为极简控制入口。

![Agent Island Monitor screenshot](assets/screenshot.png)

## 功能亮点

- **默认迷你胶囊**：平时只显示两个极小状态点，减少遮挡浏览器标签栏、按钮和文字。
- **事件展开**：Codex 开始运行、完成或需要你处理时，小岛会短暂或持续舒展开。
- **Codex 状态监控**：读取本机 Codex 日志和状态文件，显示 `Running`、`Needs You`、`Done`、`Idle`、`Offline`。
- **Cursor/CC 诚实状态**：Cursor 开着但没有证据表明 AI 在生成时显示 `Open`，不误报 `Running`。
- **一键召唤窗口**：展开态点击 `Codex` 或 `Cursor/CC` 胶囊，自动把对应窗口切到前台并最大化。
- **极简展开态**：展开后只显示 Codex 与 Cursor/CC 两个胶囊，不显示日志、线程列表或冗余文字。
- **托盘菜单**：支持显示/隐藏、安静模式、静音提醒、开机自启、退出。
- **无需第三方依赖**：使用 Python 标准库 + Tkinter + Win32 `ctypes` 实现。

## 状态含义

### Codex

- `Running`：检测到真实 Codex runner 或明确活跃任务。
- `Needs You`：检测到授权、确认、用户输入等明确等待用户处理的信号。
- `Done`：最近任务已完成，当前没有活跃 runner。
- `Idle`：Codex 程序存在，但没有明显任务活动。
- `Offline`：没有检测到 Codex 相关活动。

### Cursor/CC

- `Active`：Cursor 是当前前台窗口。
- `Open`：Cursor 开着但不在前台；这不代表 DeepSeek/Claude 正在生成。
- `Offline`：没有检测到 Cursor 进程。

> `Cursor/CC` 指 Cursor + CC/Claude Code 转接工作环境。本工具当前只做窗口和进程级轻量检测，不读取 DeepSeek/Claude 的内部生成状态。

## 展开逻辑

- `Idle` / `Open` / `Offline`：保持迷你胶囊。
- `Running`：状态变化时展开约 4 秒，然后自动回到迷你胶囊。
- `Done`：完成时展开约 4 秒，显示完成反馈，然后自动回到迷你胶囊。
- `Needs You`：持续展开，直到状态解除。
- 手动点击迷你胶囊：展开双状态胶囊。
- 展开态点击空白区域：收回迷你胶囊。

## 使用方法

### 手动启动

双击：

```powershell
start_agent_island.bat
```

### 开机自启

安装开机自启：

```powershell
powershell -ExecutionPolicy Bypass -File .\install_startup.ps1
```

取消开机自启：

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall_startup.ps1
```

### 交互

- 点击迷你胶囊：展开双状态胶囊。
- 展开态点击 `Codex` 胶囊：召唤 Codex 到前台并最大化。
- 展开态点击 `Cursor/CC` 胶囊：召唤 Cursor 到前台并最大化。
- 展开态点击空白区域：收回迷你胶囊。
- 右键托盘图标：打开功能菜单。
- 按 `Esc`：关闭小岛。

## 配置

编辑 `config.json` 可调整：

- 刷新间隔
- 迷你胶囊尺寸
- 动画开关
- 鼠标靠近自动上收备用功能
- 静音提醒
- 小岛颜色
- Codex 活跃/Needs You 判断阈值

## 当前限制

- 暂不监控 Gemini 网页端。
- Cursor/CC 不读取 DeepSeek 或 Claude 的内部生成状态。
- Codex 状态基于本地 sqlite/log 推断，如果 Codex 后续改变本地日志结构，需要更新监控逻辑。
- Windows 有时会限制程序强制切换前台窗口；如果点击不能切过去，通常是系统前台窗口策略限制。

## 项目文件

- `agent_island.py`：主程序。
- `config.json`：配置文件。
- `start_agent_island.bat`：手动启动脚本。
- `install_startup.ps1`：安装开机自启。
- `uninstall_startup.ps1`：取消开机自启。
- `功能说明.txt`：中文功能说明。


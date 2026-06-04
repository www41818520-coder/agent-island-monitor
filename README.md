# Agent Island Monitor

Windows 顶部悬浮的 AI 状态小岛，灵感来自 Apple Dynamic Island。它用于在后台运行 Codex、Cursor/CC 时，快速查看任务状态，并一键最大化召唤对应 AI 工作窗口。

![Agent Island Monitor screenshot](assets/screenshot.png)

## 功能亮点

- **Codex 状态监控**：读取本机 Codex 日志和状态文件，显示 `Running`、`Needs You`、`Done`、`Idle`、`Offline`。
- **Cursor/CC 轻量监控**：检测 Cursor 是否运行、是否处于前台窗口。
- **Needs You 提醒**：当 Codex 需要授权、确认、放行或用户输入时，以琥珀色状态提示。
- **一键召唤窗口**：点击 `Codex` 或 `Cursor/CC` 胶囊，自动把对应窗口切到前台并最大化。
- **苹果风格小岛 UI**：深黑胶囊、细环状态点、微弱动效、顶部高光和玻璃质感。
- **展开详情**：点击空白区域展开，查看最近多个 Codex 线程和状态摘要。
- **托盘菜单**：支持显示/隐藏、安静模式、静音提醒、开机自启、退出。
- **无需第三方依赖**：使用 Python 标准库 + Tkinter + Win32 `ctypes` 实现。

## 界面状态

### Codex

- `Running`：检测到真实 Codex runner 或明确活跃任务。
- `Needs You`：检测到授权、确认、用户输入等明确等待用户处理的信号。
- `Done`：最近任务已完成，当前没有活跃 runner。
- `Idle`：Codex 程序存在，但没有明显任务活动。
- `Offline`：没有检测到 Codex 相关活动。

### Cursor/CC

- `Active`：Cursor 正在运行，并且是当前前台窗口。
- `Running`：Cursor 正在运行，但不在前台。
- `Idle`：检测到 Cursor 进程，但没有可靠窗口标题。
- `Offline`：没有检测到 Cursor 进程。

> `Cursor/CC` 指 Cursor + CC/Claude Code 转接工作环境。本工具当前只做窗口和进程级轻量检测，不读取 DeepSeek/Claude 的内部生成状态。

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

- 点击 `Codex` 胶囊：召唤 Codex 到前台并最大化。
- 点击 `Cursor/CC` 胶囊：召唤 Cursor 到前台并最大化。
- 点击小岛空白区域：展开或收起详情。
- 右键托盘图标：打开功能菜单。
- 按 `Esc`：关闭小岛。

## 配置

编辑 `config.json` 可调整：

- 刷新间隔
- 安静模式
- 静音提醒
- 动画开关
- 小岛尺寸
- 颜色
- Codex 活跃/Needs You 判断阈值
- 展开态显示的线程数量

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


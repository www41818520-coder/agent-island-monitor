import ctypes
import json
import math
import os
import sqlite3
import subprocess
import time
import tkinter as tk
import winsound
from ctypes import wintypes
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "config.json"
CODEX_DIR = Path(os.environ.get("USERPROFILE", "")) / ".codex"
TRANSPARENT_COLOR = "#ff00ff"
STARTUP_LINK = (
    Path(os.environ.get("APPDATA", ""))
    / "Microsoft"
    / "Windows"
    / "Start Menu"
    / "Programs"
    / "Startup"
    / "Agent Island.lnk"
)


DEFAULT_CONFIG = {
    "refresh_seconds": 2,
    "codex_active_seconds": 20,
    "codex_waiting_seconds": 60,
    "completion_flash_seconds": 4,
    "manual_expand_seconds": 2,
    "transition_ms": 150,
    "transition_steps": 8,
    "animation_enabled": True,
    "auto_tuck_on_hover": False,
    "tucked_visible_pixels": 6,
    "quiet_mode": True,
    "muted": False,
    "max_threads": 4,
    "width": 424,
    "quiet_width": 118,
    "collapsed_height": 50,
    "quiet_height": 34,
    "expanded_height": 50,
    "top_offset": 8,
    "position_mode": "center",
    "custom_x": None,
    "custom_y": None,
    "colors": {
        "background": "#050505",
        "background_done": "#07160d",
        "surface": "#111111",
        "surface_soft": "#1b1b1d",
        "shine": "#5a5a5f",
        "rim": "#2f3035",
        "border": "#24252a",
        "shadow": "#020202",
        "text": "#f4f4f4",
        "muted": "#a4a4a4",
        "running": "#74b9ff",
        "needs_you": "#ffb02e",
        "done": "#6ee7a8",
        "idle": "#8b949e",
        "offline": "#666666",
        "cursor": "#c084fc",
    },
}


user32 = ctypes.windll.user32
shell32 = ctypes.windll.shell32
user32.SetWindowLongPtrW.restype = ctypes.c_longlong
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
user32.CallWindowProcW.restype = ctypes.c_longlong
user32.CallWindowProcW.argtypes = [
    ctypes.c_longlong,
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
]

SW_RESTORE = 9
SW_MAXIMIZE = 3
WM_USER = 0x0400
WM_TRAY = WM_USER + 20
WM_LBUTTONUP = 0x0202
WM_RBUTTONUP = 0x0205
WM_DESTROY = 0x0002
GWL_WNDPROC = -4

NIM_ADD = 0
NIM_MODIFY = 1
NIM_DELETE = 2
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
IDI_APPLICATION = 32512

MF_STRING = 0x00000000
TPM_RETURNCMD = 0x0100
TPM_RIGHTBUTTON = 0x0002


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class NOTIFYICONDATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uTimeoutOrVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", ctypes.c_byte * 16),
        ("hBalloonIcon", wintypes.HICON),
    ]


WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_longlong, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
)


def load_config():
    if CONFIG_PATH.exists():
        try:
            with CONFIG_PATH.open("r", encoding="utf-8-sig") as handle:
                loaded = json.load(handle)
            config = DEFAULT_CONFIG.copy()
            config.update(loaded)
            config["colors"] = {**DEFAULT_CONFIG["colors"], **loaded.get("colors", {})}
            return config
        except Exception:
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()


def save_config(config):
    with CONFIG_PATH.open("w", encoding="utf-8") as handle:
        json.dump(config, handle, ensure_ascii=False, indent=2)


def now_seconds():
    return int(time.time())


def run_powershell(command, timeout=2):
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def process_snapshot():
    output = run_powershell("Get-Process | ForEach-Object { \"$($_.Id)|$($_.ProcessName)\" }")
    names = set()
    pid_to_name = {}
    for line in output.splitlines():
        if "|" not in line:
            continue
        pid_text, name = line.split("|", 1)
        try:
            pid = int(pid_text.strip())
        except ValueError:
            continue
        clean_name = name.strip().lower()
        if clean_name:
            names.add(clean_name)
            pid_to_name[pid] = clean_name
    return names, pid_to_name


def has_codex_runner(names):
    return any(name.startswith("codex-command-runner") for name in names)


def has_codex_shell(names):
    return "codex" in names


def get_window_text(hwnd):
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value.strip()


def enum_windows(pid_to_name=None):
    pid_to_name = pid_to_name or {}
    windows = []
    enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        title = get_window_text(hwnd)
        if not title:
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        windows.append(
            {
                "hwnd": hwnd,
                "title": title,
                "pid": pid.value,
                "process": pid_to_name.get(pid.value, ""),
            }
        )
        return True

    user32.EnumWindows(enum_proc(callback), 0)
    return windows


def get_foreground_hwnd():
    return user32.GetForegroundWindow()


def activate_matching_window(kind, windows, maximize=True):
    kind = kind.lower()
    candidates = []
    for info in windows:
        title = info["title"].lower()
        process = info["process"].lower()
        if kind == "codex" and ("codex" in title or "codex" in process):
            candidates.append(info)
        if kind == "cursor" and ("cursor" in title or process == "cursor"):
            candidates.append(info)
    if not candidates:
        return False
    hwnd = candidates[0]["hwnd"]
    try:
        user32.ShowWindow(hwnd, SW_RESTORE)
        if maximize:
            user32.ShowWindow(hwnd, SW_MAXIMIZE)
        user32.SetForegroundWindow(hwnd)
        return True
    except Exception:
        return False


def read_recent_threads(limit):
    path = CODEX_DIR / "state_5.sqlite"
    if not path.exists():
        return []
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=1)
        cur = con.cursor()
        cur.execute(
            "select id, title, cwd, updated_at, source from threads order by updated_at desc limit ?",
            (limit,),
        )
        rows = cur.fetchall()
        con.close()
    except Exception:
        return []
    return [
        {
            "id": row[0],
            "title": row[1] or "Untitled Codex thread",
            "cwd": row[2] or "",
            "updated_at": int(row[3] or 0),
            "source": row[4] or "",
        }
        for row in rows
    ]


def read_latest_logs(limit=120):
    path = CODEX_DIR / "logs_2.sqlite"
    if not path.exists():
        return []
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=1)
        cur = con.cursor()
        cur.execute(
            "select ts, level, target, thread_id, coalesce(feedback_log_body,'') "
            "from logs order by id desc limit ?",
            (limit,),
        )
        rows = cur.fetchall()
        con.close()
        return rows
    except Exception:
        return []


def contains_needs_you_signal(text):
    exact_signals = (
        "sandbox_permissions\":\"require_escalated",
        "requires approval",
        "approval request",
        "requesting approval",
        "request_user_input",
        "waiting for user",
        "waiting for approval",
        "user approval",
        "needs user input",
        "need user input",
        "requires user input",
        "do you want to allow",
        "是否允许",
        "需要你授权",
        "需要授权",
        "请求授权",
        "等待授权",
        "等待确认",
        "等待你",
    )
    lowered = text.lower()
    return any(signal in lowered for signal in exact_signals)


def latest_codex_completion_ts(logs):
    latest = 0
    for ts, _level, target, _thread_id, body in logs:
        text = f"{target or ''} {body or ''}".lower()
        if "response.completed" in text:
            latest = max(latest, int(ts or 0))
    return latest


def classify_thread(thread, logs_by_thread, global_logs, codex_process, config):
    current = now_seconds()
    active_seconds = int(config["codex_active_seconds"])
    waiting_seconds = int(config["codex_waiting_seconds"])
    logs = logs_by_thread.get(thread["id"], []) or global_logs[:3]
    latest_ts = thread.get("updated_at", 0)
    latest_body = ""
    needs_ts = 0

    for ts, _level, target, _thread_id, body in logs:
        log_ts = int(ts or 0)
        if log_ts > latest_ts:
            latest_ts = log_ts
            latest_body = f"{target or ''} {body or ''}".strip()
        if str(target or "").startswith("codex_api::sse"):
            continue
        text = f"{target or ''} {body or ''}"
        if contains_needs_you_signal(text):
            needs_ts = max(needs_ts, log_ts)

    latest_completion_ts = latest_codex_completion_ts(global_logs)

    if needs_ts and current - needs_ts <= waiting_seconds:
        status = "Needs You"
        since_ts = needs_ts
    elif codex_process and latest_ts and current - latest_ts <= active_seconds and latest_ts > latest_completion_ts:
        status = "Running"
        since_ts = latest_ts
    elif latest_ts:
        status = "Done"
        since_ts = latest_ts
    else:
        status = "Idle"
        since_ts = current

    return {
        **thread,
        "status": status,
        "since_ts": since_ts or current,
        "latest_log_ts": latest_ts,
        "latest_body": latest_body[:220],
    }


def classify_codex(names, config):
    runner_process = has_codex_runner(names)
    codex_shell = has_codex_shell(names)
    threads = read_recent_threads(int(config["max_threads"]))
    logs = read_latest_logs()
    logs_by_thread = {}
    global_logs = []

    for row in logs:
        thread_id = row[3]
        if thread_id:
            logs_by_thread.setdefault(thread_id, []).append(row)
        else:
            global_logs.append(row)

    items = [
        classify_thread(thread, logs_by_thread, global_logs, runner_process, config)
        for thread in threads
    ]

    priority = {"Needs You": 0, "Running": 1, "Done": 2, "Idle": 3, "Offline": 4}
    items.sort(key=lambda item: (priority.get(item["status"], 9), -item.get("latest_log_ts", 0)))

    if not items and not (runner_process or codex_shell):
        status = "Offline"
        since_ts = now_seconds()
    elif not items:
        status = "Idle"
        since_ts = now_seconds()
    else:
        status = items[0]["status"]
        since_ts = items[0]["since_ts"]

    counts = {}
    for item in items:
        counts[item["status"]] = counts.get(item["status"], 0) + 1

    return {
        "status": status,
        "since_ts": since_ts,
        "items": items,
        "counts": counts,
        "process": runner_process or codex_shell,
        "runner_process": runner_process,
    }


def classify_cursor(names, windows):
    is_running = "cursor" in names
    foreground = get_foreground_hwnd()
    cursor_windows = [
        info for info in windows if info["process"] == "cursor" or "cursor" in info["title"].lower()
    ]
    active = any(info["hwnd"] == foreground for info in cursor_windows)
    current = now_seconds()

    if not is_running:
        status = "Offline"
    elif active:
        status = "Active"
    else:
        status = "Open"

    return {
        "status": status,
        "since_ts": current,
        "title": cursor_windows[0]["title"] if cursor_windows else "",
        "windows": cursor_windows,
        "process": is_running,
    }


def truncate_text(text, limit):
    text = str(text or "")
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


def age_text(ts):
    if not ts:
        return "now"
    delta = max(0, now_seconds() - int(ts))
    if delta < 5:
        return "now"
    if delta < 60:
        return f"{delta}s"
    minutes = delta // 60
    if minutes < 60:
        return f"{minutes}m"
    return f"{minutes // 60}h"


class TrayIcon:
    def __init__(self, app):
        self.app = app
        self.hwnd = None
        self.icon_data = None
        self.old_proc = None
        self.new_proc = None

    def install(self):
        self.hwnd = self.app.winfo_id()
        self.new_proc = WNDPROC(self.window_proc)
        self.old_proc = user32.SetWindowLongPtrW(self.hwnd, GWL_WNDPROC, self.new_proc)
        icon = user32.LoadIconW(None, IDI_APPLICATION)
        data = NOTIFYICONDATA()
        data.cbSize = ctypes.sizeof(NOTIFYICONDATA)
        data.hWnd = self.hwnd
        data.uID = 1
        data.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        data.uCallbackMessage = WM_TRAY
        data.hIcon = icon
        data.szTip = "Agent Island"
        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(data))
        self.icon_data = data

    def remove(self):
        if self.icon_data:
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self.icon_data))
            self.icon_data = None
        if self.hwnd and self.old_proc:
            user32.SetWindowLongPtrW(self.hwnd, GWL_WNDPROC, self.old_proc)

    def window_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_TRAY:
            if lparam == WM_LBUTTONUP:
                self.app.after(0, self.app.toggle_visibility)
                return 0
            if lparam == WM_RBUTTONUP:
                self.app.after(0, self.show_menu)
                return 0
        if msg == WM_DESTROY:
            self.remove()
        return user32.CallWindowProcW(self.old_proc, hwnd, msg, wparam, lparam)

    def show_menu(self):
        menu = user32.CreatePopupMenu()
        visible_text = "隐藏小岛" if self.app.visible else "显示小岛"
        quiet_text = "✓ 安静模式" if self.app.config_data.get("quiet_mode") else "安静模式"
        muted_text = "✓ 静音提醒" if self.app.config_data.get("muted") else "静音提醒"
        startup_text = "✓ 开机自启" if STARTUP_LINK.exists() else "开机自启"
        for item_id, text in (
            (1001, visible_text),
            (1002, quiet_text),
            (1003, muted_text),
            (1004, startup_text),
            (1005, "退出"),
        ):
            user32.AppendMenuW(menu, MF_STRING, item_id, text)
        point = POINT()
        user32.GetCursorPos(ctypes.byref(point))
        user32.SetForegroundWindow(self.hwnd)
        command = user32.TrackPopupMenu(
            menu,
            TPM_RETURNCMD | TPM_RIGHTBUTTON,
            point.x,
            point.y,
            0,
            self.hwnd,
            None,
        )
        user32.DestroyMenu(menu)
        if command:
            self.app.handle_tray_command(command)


class AgentIsland(tk.Tk):
    def __init__(self):
        super().__init__()
        self.config_data = load_config()
        self.colors = self.config_data["colors"]
        self.expanded = False
        self.visible = True
        self.codex = None
        self.cursor = None
        self.windows = []
        self.status_since = {}
        self.last_main_status = "Offline"
        self.has_seen_status = False
        self.flash_until = 0
        self.peek_until = 0
        self.expanded_until = 0
        self.tucked = False
        self.last_geometry = (0, 0, 0, 0)
        self.geometry_target = None
        self.displayed_geometry = None
        self.geometry_anim_job = None
        self.drag_start = None
        self.click_after_id = None
        self.suppress_single_until = 0
        self.phase = 0
        self.codex_region = None
        self.cursor_region = None

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.985)
        self.attributes("-transparentcolor", TRANSPARENT_COLOR)
        self.configure(bg=TRANSPARENT_COLOR)

        self.canvas = tk.Canvas(self, highlightthickness=0, bd=0, bg=TRANSPARENT_COLOR)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self.on_drag_start)
        self.canvas.bind("<B1-Motion>", self.on_drag_motion)
        self.canvas.bind("<ButtonRelease-1>", self.on_pointer_release)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
        self.canvas.bind("<Button-3>", self.show_window_menu)
        self.canvas.bind("<Enter>", self.on_mouse_enter)
        self.bind("<Escape>", lambda _event: self.shutdown())

        self.update_idletasks()
        self.tray = TrayIcon(self)
        self.tray.install()
        self.geometry_for_state()
        self.refresh_state()
        self.watch_pointer()
        self.animate()

    def is_quiet_compact(self):
        if self.expanded or not self.config_data.get("quiet_mode"):
            return False
        if now_seconds() < self.peek_until or now_seconds() < self.flash_until:
            return False
        if self.codex and self.codex["status"] == "Needs You":
            return False
        return True

    def geometry_for_state(self):
        quiet = self.is_quiet_compact()
        base_width = int(self.config_data["quiet_width"] if quiet else self.config_data["width"])
        height = int(
            self.config_data["quiet_height"]
            if quiet
            else self.config_data["expanded_height"]
            if self.expanded
            else self.config_data["collapsed_height"]
        )
        extra = 12 if now_seconds() < self.flash_until and not quiet else 0
        width = base_width + extra
        if self.config_data.get("position_mode") == "custom":
            x = int(self.config_data.get("custom_x") or 0)
        else:
            x = int((self.winfo_screenwidth() - width) / 2)
        normal_y = int(self.config_data["top_offset"])
        if self.config_data.get("position_mode") == "custom":
            normal_y = int(self.config_data.get("custom_y") or normal_y)
        y = normal_y
        if self.tucked:
            y = -height + int(self.config_data.get("tucked_visible_pixels", 6))
        self.last_geometry = (x, normal_y, width, height)
        self.current_width = width
        self.current_height = height
        self.set_geometry_target(x, y, width, height)

    def set_geometry_target(self, x, y, width, height):
        target = (int(x), int(y), int(width), int(height))
        if self.geometry_target == target:
            return
        self.geometry_target = target
        if not self.displayed_geometry or not self.config_data.get("animation_enabled"):
            self.apply_geometry(target)
            self.displayed_geometry = target
            return
        if self.geometry_anim_job:
            self.after_cancel(self.geometry_anim_job)
            self.geometry_anim_job = None
        self.animate_geometry(self.displayed_geometry, target, 1)

    def apply_geometry(self, geometry):
        x, y, width, height = geometry
        self.geometry(f"{width}x{height}+{x}+{y}")

    def animate_geometry(self, start, target, step):
        total = max(1, int(self.config_data.get("transition_steps", 8)))
        t = min(1.0, step / total)
        eased = 1 - (1 - t) ** 3
        current = tuple(
            int(start[index] + (target[index] - start[index]) * eased)
            for index in range(4)
        )
        self.apply_geometry(current)
        self.displayed_geometry = current
        if step >= total:
            self.apply_geometry(target)
            self.displayed_geometry = target
            self.geometry_anim_job = None
            return
        delay = max(10, int(self.config_data.get("transition_ms", 150)) // total)
        self.geometry_anim_job = self.after(delay, lambda: self.animate_geometry(start, target, step + 1))

    def draw_rounded_rect(self, x1, y1, x2, y2, radius, fill, outline="", width=1):
        radius = max(1, min(radius, int((x2 - x1) / 2), int((y2 - y1) / 2)))
        points = []
        for start in (180, 270, 0, 90):
            cx = x1 + radius if start in (180, 90) else x2 - radius
            cy = y1 + radius if start in (180, 270) else y2 - radius
            for i in range(16):
                angle = math.radians(start + i * 6)
                points.append((cx + math.cos(angle) * radius, cy + math.sin(angle) * radius))
        flat = [coord for point in points for coord in point]
        self.canvas.create_polygon(flat, smooth=True, fill=fill, outline=outline, width=width)

    def draw_shell(self, background):
        width = self.current_width
        height = self.current_height
        self.canvas.delete("all")
        self.canvas.configure(width=width, height=height, bg=TRANSPARENT_COLOR)
        radius = max(1, height // 2)
        self.draw_rounded_rect(6, 8, width - 6, height - 1, radius, self.colors["shadow"], "")
        self.draw_rounded_rect(2, 2, width - 2, height - 4, radius, "#000000", self.colors["border"], 1)
        self.draw_rounded_rect(4, 4, width - 4, height - 6, radius, background, self.colors["rim"], 1)
        self.draw_rounded_rect(11, 7, width - 11, max(27, height // 2 + 6), radius - 7, self.colors["surface"], "")
        self.draw_rounded_rect(24, 8, width - 24, 18, 8, "#6d6e76", "")
        self.draw_rounded_rect(38, 10, width - 38, 14, 3, "#b8bbc4", "")
        self.canvas.create_line(30, height - 10, width - 30, height - 10, fill="#18191d", width=1)

    def status_color(self, status, fallback):
        return {
            "Running": self.colors["running"],
            "Needs You": self.colors["needs_you"],
            "Done": self.colors["done"],
            "Idle": self.colors["idle"],
            "Offline": self.colors["offline"],
            "Active": fallback,
            "Open": fallback,
        }.get(status, fallback)

    def status_label(self, status, since_ts):
        if status == "Offline":
            return "Offline"
        return f"{status} · {age_text(since_ts)}"

    def draw_status_chip(self, x1, y1, x2, y2, label, status, since_ts, color):
        pulse_on = False
        if self.config_data.get("animation_enabled"):
            if status == "Running":
                pulse_on = math.sin(self.phase) > 0.2
            elif status == "Needs You":
                pulse_on = math.sin(self.phase * 1.6) > -0.1

        self.draw_rounded_rect(x1, y1, x2, y2, 17, self.colors["surface_soft"], "#292a30", 1)
        self.draw_rounded_rect(x1 + 4, y1 + 3, x2 - 4, y1 + 12, 7, "#2f3035", "")
        ring = color if pulse_on else "#34363d"
        self.canvas.create_oval(x1 + 11, y1 + 10, x1 + 27, y1 + 26, fill="", outline="#15161a", width=1)
        self.canvas.create_oval(x1 + 12, y1 + 11, x1 + 26, y1 + 25, fill="", outline=ring, width=1)
        self.canvas.create_oval(x1 + 15, y1 + 14, x1 + 23, y1 + 22, fill=color, outline="")
        self.canvas.create_oval(x1 + 17, y1 + 15, x1 + 20, y1 + 18, fill="#ffffff", outline="")
        self.canvas.create_text(
            x1 + 34,
            y1 + 18,
            text=label,
            fill=self.colors["muted"],
            anchor="w",
            font=("Segoe UI", 9),
        )
        self.canvas.create_text(
            x2 - 14,
            y1 + 18,
            text=self.status_label(status, since_ts),
            fill=self.colors["text"],
            anchor="e",
            font=("Segoe UI Semibold", 9),
        )

    def render(self):
        if not self.codex or not self.cursor:
            return
        self.geometry_for_state()
        codex_status = self.codex["status"]
        bg = self.colors["background_done"] if now_seconds() < self.flash_until else self.colors["background"]
        if codex_status == "Needs You":
            bg = "#191104"
        self.draw_shell(bg)

        codex_color = self.status_color(codex_status, self.colors["running"])
        cursor_color = self.status_color(self.cursor["status"], self.colors["cursor"])

        if self.is_quiet_compact():
            self.codex_region = None
            self.cursor_region = None
            mid = self.current_width // 2
            self.canvas.create_oval(mid - 28, 11, mid - 14, 25, fill="", outline="#34363d", width=1)
            self.canvas.create_oval(mid - 24, 15, mid - 18, 21, fill=codex_color, outline="")
            self.canvas.create_line(mid - 2, 15, mid - 2, 21, fill="#2a2b30", width=1)
            self.canvas.create_oval(mid + 12, 11, mid + 26, 25, fill="", outline="#34363d", width=1)
            self.canvas.create_oval(mid + 16, 15, mid + 22, 21, fill=cursor_color, outline="")
            return

        self.codex_region = (16, 9, 204, 41)
        self.cursor_region = (220, 9, 408, 41)
        self.draw_status_chip(16, 9, 204, 41, "Codex", codex_status, self.codex["since_ts"], codex_color)
        self.draw_status_chip(
            220,
            9,
            408,
            41,
            "Cursor/CC",
            self.cursor["status"],
            self.cursor["since_ts"],
            cursor_color,
        )

        if now_seconds() < self.flash_until:
            progress = 1 - max(0, self.flash_until - time.time()) / float(self.config_data["completion_flash_seconds"])
            sweep_x = 26 + int(progress * 360)
            self.draw_rounded_rect(max(26, sweep_x - 70), 44, min(398, sweep_x), 47, 3, self.colors["done"], "")

        return

    def refresh_state(self):
        names, pid_to_name = process_snapshot()
        self.windows = enum_windows(pid_to_name)
        codex = classify_codex(names, self.config_data)
        cursor = classify_cursor(names, self.windows)
        codex["since_ts"] = self.stabilize_since("codex", codex["status"], codex["since_ts"])
        cursor["since_ts"] = self.stabilize_since("cursor", cursor["status"], cursor["since_ts"])

        previous = self.last_main_status
        current = codex["status"]
        if self.has_seen_status and previous != current:
            self.peek_until = now_seconds() + 4
        if self.has_seen_status and previous in ("Running", "Needs You") and current in ("Done", "Idle"):
            self.flash_until = time.time() + float(self.config_data["completion_flash_seconds"])
            if not self.config_data.get("muted"):
                try:
                    winsound.MessageBeep(winsound.MB_ICONASTERISK)
                except Exception:
                    pass

        self.last_main_status = current
        self.has_seen_status = True
        self.codex = codex
        self.cursor = cursor
        self.render()
        delay = int(float(self.config_data["refresh_seconds"]) * 1000)
        self.after(max(500, delay), self.refresh_state)

    def stabilize_since(self, key, status, fallback):
        old = self.status_since.get(key)
        if not old or old[0] != status:
            self.status_since[key] = (status, fallback or now_seconds())
        return self.status_since[key][1]

    def animate(self):
        self.phase += 0.22
        if (
            self.expanded
            and self.expanded_until
            and time.time() >= self.expanded_until
            and not (self.codex and self.codex["status"] == "Needs You")
        ):
            self.expanded = False
            self.expanded_until = 0
            self.peek_until = 0
            self.render()
        if self.config_data.get("animation_enabled") and self.codex and self.cursor:
            if self.codex["status"] in ("Running", "Needs You") or now_seconds() < self.flash_until:
                self.render()
        self.after(120, self.animate)

    def on_click(self, event):
        if self.is_quiet_compact():
            self.expanded = True
            self.expanded_until = time.time() + float(self.config_data.get("manual_expand_seconds", 2))
            self.peek_until = 0
            self.render()
            return
        self.expanded = not self.expanded
        self.expanded_until = (
            time.time() + float(self.config_data.get("manual_expand_seconds", 2))
            if self.expanded
            else 0
        )
        self.peek_until = 0
        self.render()

    def on_double_click(self, event):
        if self.click_after_id:
            self.after_cancel(self.click_after_id)
            self.click_after_id = None
        self.suppress_single_until = time.time() + 0.35
        if self.is_quiet_compact():
            if not activate_matching_window("codex", self.windows):
                self.peek_until = now_seconds() + 2
            return
        if self.region_contains(self.codex_region, event.x, event.y):
            if not activate_matching_window("codex", self.windows):
                self.peek_until = now_seconds() + 2
            return
        if self.region_contains(self.cursor_region, event.x, event.y):
            if not activate_matching_window("cursor", self.windows):
                self.peek_until = now_seconds() + 2
            return
        if not activate_matching_window("codex", self.windows):
            self.peek_until = now_seconds() + 2

    def on_drag_start(self, event):
        self.drag_start = {
            "pointer_x": event.x_root,
            "pointer_y": event.y_root,
            "window_x": self.winfo_x(),
            "window_y": self.winfo_y(),
            "moved": False,
        }

    def on_drag_motion(self, event):
        if not self.drag_start:
            return
        dx = event.x_root - self.drag_start["pointer_x"]
        dy = event.y_root - self.drag_start["pointer_y"]
        if abs(dx) < 4 and abs(dy) < 4:
            return
        self.drag_start["moved"] = True
        x = self.drag_start["window_x"] + dx
        y = self.drag_start["window_y"] + dy
        x = max(0, min(x, self.winfo_screenwidth() - self.current_width))
        y = max(0, min(y, self.winfo_screenheight() - self.current_height))
        self.config_data["position_mode"] = "custom"
        self.config_data["custom_x"] = int(x)
        self.config_data["custom_y"] = int(y)
        self.displayed_geometry = (int(x), int(y), self.current_width, self.current_height)
        self.geometry_target = self.displayed_geometry
        self.apply_geometry(self.displayed_geometry)

    def on_pointer_release(self, event):
        if self.drag_start and self.drag_start.get("moved"):
            save_config(self.config_data)
            self.after(80, lambda: setattr(self, "drag_start", None))
            return
        self.after(80, lambda: setattr(self, "drag_start", None))
        if time.time() < self.suppress_single_until:
            return
        if self.click_after_id:
            self.after_cancel(self.click_after_id)
        self.click_after_id = self.after(180, lambda: self.run_single_click(event))

    def run_single_click(self, event):
        self.click_after_id = None
        self.on_click(event)

    def show_window_menu(self, _event=None):
        menu = user32.CreatePopupMenu()
        user32.AppendMenuW(menu, MF_STRING, 2001, "恢复默认位置")
        user32.AppendMenuW(menu, MF_STRING, 2002, "关闭")
        point = POINT()
        user32.GetCursorPos(ctypes.byref(point))
        user32.SetForegroundWindow(self.winfo_id())
        command = user32.TrackPopupMenu(
            menu,
            TPM_RETURNCMD | TPM_RIGHTBUTTON,
            point.x,
            point.y,
            0,
            self.winfo_id(),
            None,
        )
        user32.DestroyMenu(menu)
        if command == 2001:
            self.reset_position()
        elif command == 2002:
            self.shutdown()

    def reset_position(self):
        self.config_data["position_mode"] = "center"
        self.config_data["custom_x"] = None
        self.config_data["custom_y"] = None
        save_config(self.config_data)
        self.tucked = False
        self.render()

    def on_mouse_enter(self, _event):
        if not self.config_data.get("auto_tuck_on_hover"):
            return
        if self.expanded or self.codex and self.codex["status"] == "Needs You":
            return
        self.tucked = True
        self.geometry_for_state()

    def watch_pointer(self):
        if self.tucked:
            point = POINT()
            user32.GetCursorPos(ctypes.byref(point))
            x, y, width, height = self.last_geometry
            margin = 18
            inside_original = (
                x - margin <= point.x <= x + width + margin
                and y - margin <= point.y <= y + height + margin
            )
            if not inside_original:
                self.tucked = False
                self.render()
        self.after(150, self.watch_pointer)

    @staticmethod
    def region_contains(region, x, y):
        if not region:
            return False
        x1, y1, x2, y2 = region
        return x1 <= x <= x2 and y1 <= y <= y2

    def toggle_visibility(self):
        if self.visible:
            self.withdraw()
            self.visible = False
        else:
            self.deiconify()
            self.attributes("-topmost", True)
            self.visible = True
            self.render()

    def handle_tray_command(self, command):
        if command == 1001:
            self.toggle_visibility()
        elif command == 1002:
            self.config_data["quiet_mode"] = not self.config_data.get("quiet_mode")
            save_config(self.config_data)
            self.peek_until = now_seconds() + 4
            self.render()
        elif command == 1003:
            self.config_data["muted"] = not self.config_data.get("muted")
            save_config(self.config_data)
        elif command == 1004:
            self.toggle_startup()
        elif command == 1005:
            self.shutdown()

    def toggle_startup(self):
        script = "uninstall_startup.ps1" if STARTUP_LINK.exists() else "install_startup.ps1"
        subprocess.Popen(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(APP_DIR / script)],
            cwd=str(APP_DIR),
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

    def shutdown(self):
        try:
            self.tray.remove()
        except Exception:
            pass
        self.destroy()


if __name__ == "__main__":
    AgentIsland().mainloop()

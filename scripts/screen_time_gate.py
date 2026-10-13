"""Native intention/one-minute dialog. The caller owns suspension and cleanup.

The window mirrors the browser extension's blocked page: same palette, hourglass
icon, copy and pill buttons, and it follows the system light/dark setting.
"""
from __future__ import annotations

import ctypes
import json
import subprocess
import sys
import tkinter as tk
import tkinter.font as tkfont
import urllib.request
import webbrowser
from pathlib import Path

LIGHT = {"bg": "#f2f2f7", "text": "#1c1c1e", "sub": "#636366", "mute": "#8e8e93", "btn": "#e5e5ea",
         "blue": "#007aff", "card": "#ffffff", "line": "#d1d1d6", "red": "#ff375f"}
DARK = {"bg": "#1b1b1d", "text": "#f2f2f7", "sub": "#98989d", "mute": "#8e8e93", "btn": "#3a3a3c",
        "blue": "#0a84ff", "card": "#2c2c2e", "line": "#48484a", "red": "#ff453a"}
# Same outline as the hourglass in the web console (24x24 viewBox).
HOURGLASS = [(6, 3), (18, 3), (18, 6.2), (17.1, 8.6), (15.6, 10.2), (14.8, 11.2), (15.6, 12.2), (17.1, 13.8),
             (18, 16.2), (18, 21), (6, 21), (6, 16.2), (6.9, 13.8), (8.4, 12.2), (9.2, 11.2), (8.4, 10.2),
             (6.9, 8.6), (6, 6.2)]
FONT = "Microsoft YaHei UI"


class RemoteStore:
    def __init__(self, port):
        self.base = f"http://127.0.0.1:{port}/api/"
        self.panel_url = f"http://127.0.0.1:{port}/"
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def call(self, route, body=None):
        request = urllib.request.Request(self.base + route, data=json.dumps(body).encode("utf-8") if body is not None else None,
                                         headers={"Content-Type": "application/json"})
        try:
            return json.load(self.opener.open(request, timeout=3))
        except urllib.error.HTTPError as exc:
            raise ValueError(json.load(exc).get("error", "本地服务请求失败")) from exc

    def snapshot(self):
        return self.call("status")

    def claim_minute(self, group_id):
        return self.call("bonus", {"group": group_id})

    def submit_intent(self, client, group_id, purpose):
        return self.call("intent", {"client": client, "group": group_id, "purpose": purpose})


def request_native_gate(store, group_id, client, stop):
    # Tk must live on the main thread of a dedicated helper process on Windows.
    command = [sys.executable]
    if not getattr(sys, "frozen", False):
        command.append(str(Path(__file__).with_name("screen_time_server.py")))
    command.extend(["--gate-client", client, "--gate-group", group_id, "--port", str(getattr(store, "port", 18765))])
    helper = subprocess.Popen(command, creationflags=0x08000000)
    try:
        while helper.poll() is None:
            if stop.wait(0.2) or store.snapshot()["paused"]:
                helper.terminate()
                return True
        return helper.returncode == 0
    finally:
        if helper.poll() is None:
            helper.terminate()


def system_palette():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
            return LIGHT if winreg.QueryValueEx(key, "AppsUseLightTheme")[0] else DARK
    except (ImportError, OSError):
        return LIGHT


def block_reason(group):
    if group.get("curfew_active"):
        return "当前处于禁用时段，稍后再来。"
    if group.get("mode") == "block":
        return "这个分类默认禁用，可领取当天唯一的一分钟。"
    return "今日额度已用完，先停在这里。"


def blend(front, back, amount):
    f = [int(front[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(back[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(x * amount + y * (1 - amount)) for x, y in zip(f, b))


def rounded(canvas, x1, y1, x2, y2, r, **kw):
    points = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2,
              x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(points, smooth=True, **kw)


class Pill(tk.Canvas):
    """Fully rounded button matching the web page's pill buttons."""

    def __init__(self, parent, text, command, colors, scale, primary=True, width=300, height=48, size=15):
        super().__init__(parent, width=int(width * scale), height=int(height * scale), bg=colors["bg"],
                         highlightthickness=0, bd=0, takefocus=1, cursor="hand2")
        self.command, self.enabled = command, True
        self.fill = colors["blue"] if primary else colors["btn"]
        self.ink = "#ffffff" if primary else colors["text"]
        self.colors = colors
        w, h = int(width * scale), int(height * scale)
        self.shape = [self.create_oval(0, 0, h, h, fill=self.fill, width=0),
                      self.create_oval(w - h, 0, w, h, fill=self.fill, width=0),
                      self.create_rectangle(h // 2, 0, w - h // 2, h, fill=self.fill, width=0)]
        self.label = self.create_text(w // 2, h // 2, text=text, fill=self.ink,
                                      font=(FONT, -int(size * scale)))
        self.bind("<Button-1>", lambda _e: self.enabled and self.command())
        self.bind("<Return>", lambda _e: self.enabled and self.command())
        self.bind("<space>", lambda _e: self.enabled and self.command())
        self.bind("<FocusIn>", lambda _e: self.configure(highlightthickness=2, highlightbackground=colors["text"]))
        self.bind("<FocusOut>", lambda _e: self.configure(highlightthickness=0))
        self.set_enabled(True)

    def set_text(self, text):
        self.itemconfigure(self.label, text=text)

    def set_enabled(self, enabled):
        self.enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow")
        amount = 1 if enabled else 0.4
        self.itemconfigure(self.label, fill=blend(self.ink, self.colors["bg"], amount))
        for item in self.shape:
            self.itemconfigure(item, fill=blend(self.fill, self.colors["bg"], amount))


def ask_intention(store, group_id, client, stop):
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    approved = False
    colors = system_palette()
    root = tk.Tk()
    scale = max(1.0, root.winfo_fpixels("1i") / 96)

    def px(value):
        return int(value * scale)

    root.title("屏幕使用时间")
    root.configure(bg=colors["bg"])
    root.resizable(False, False)
    width, height = px(460), px(500)
    root.geometry(f"{width}x{height}+{(root.winfo_screenwidth() - width) // 2}+{(root.winfo_screenheight() - height) // 3}")
    root.attributes("-topmost", True)
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    frame = tk.Frame(root, bg=colors["bg"])
    frame.pack(fill="both", expand=True, padx=px(40), pady=px(28))
    error = tk.StringVar()
    shown = {"key": None}

    def label(text, size, ink, bold=False, wrap=360, pady=0):
        font = tkfont.Font(family=FONT, size=-px(size), weight="bold" if bold else "normal")
        tk.Label(frame, text=text, font=font, fg=colors[ink], bg=colors["bg"], wraplength=px(wrap),
                 justify="center").pack(pady=pady)

    def icon():
        canvas = tk.Canvas(frame, width=px(64), height=px(64), bg=colors["bg"], highlightthickness=0, bd=0)
        k = px(64) / 24
        canvas.create_polygon([c * k for point in HOURGLASS for c in point], fill=colors["blue"], outline=colors["blue"],
                              width=1, joinstyle="round")
        canvas.pack(pady=(px(8), px(4)))

    def state_key(group):
        return (group["blocked"], group["bonus_available"], group.get("curfew_active"), group.get("mode"))

    def render(force=False):
        group = next((g for g in store.snapshot()["groups"] if g["id"] == group_id), None)
        if not group:
            root.destroy()
            return
        key = state_key(group)
        if key == shown["key"] and not force:
            return
        shown["key"] = key
        for child in frame.winfo_children():
            child.destroy()
        error.set("")
        icon()
        if group["blocked"]:
            blocked_view(group)
        else:
            intent_view()
        tk.Label(frame, textvariable=error, wraplength=px(360), bg=colors["bg"], fg=colors["red"],
                 font=(FONT, -px(13))).pack(side="bottom", pady=px(4))

    def blocked_view(group):
        label("时间额度", 26, "text", bold=True, pady=(px(14), px(6)))
        label(block_reason(group), 16, "sub", pady=(0, px(8)))
        actions = tk.Frame(frame, bg=colors["bg"])
        actions.pack(pady=(px(34), 0))
        Pill(actions, "好", root.destroy, colors, scale).pack(pady=px(6))
        if group["bonus_available"]:
            def bonus():
                try:
                    store.claim_minute(group_id)
                    render(force=True)
                except ValueError as exc:
                    error.set(str(exc))
            Pill(actions, "再使用 1 分钟", bonus, colors, scale, primary=False).pack(pady=px(6))
        panel = getattr(store, "panel_url", None)
        if panel:
            Pill(actions, "打开屏幕使用时间", lambda: webbrowser.open(panel), colors, scale, primary=False,
                 height=42, size=13).pack(pady=px(6))
        label("关闭本窗口会关闭这个 App。", 12, "mute", pady=(px(14), 0))
        if group["bonus_available"]:
            label("每天全体分类合计仅一次，网站与 App 共享。", 12, "mute")

    def intent_view():
        label("这次打开，要做什么？", 22, "text", bold=True, pady=(px(14), px(4)))
        label("写下具体用途，再开始使用。", 14, "sub", pady=(0, px(14)))
        box = tk.Canvas(frame, width=px(380), height=px(112), bg=colors["bg"], highlightthickness=0, bd=0)
        rounded(box, 1, 1, px(380) - 1, px(112) - 1, px(16), fill=colors["card"], outline=colors["line"])
        entry = tk.Text(box, height=3, font=(FONT, -px(15)), relief="flat", bd=0, wrap="word", bg=colors["card"],
                        fg=colors["text"], insertbackground=colors["text"], highlightthickness=0, padx=0, pady=0)
        box.create_window(px(380) // 2, px(112) // 2, window=entry, width=px(380) - 2 * px(16), height=px(112) - 2 * px(14))
        placeholder = tk.Label(box, text="例如：查这道题的解法，找到后就关闭", bg=colors["card"], fg=colors["mute"],
                               font=(FONT, -px(14)), anchor="w", cursor="xterm")
        hint = box.create_window(px(16), px(14), window=placeholder, anchor="nw")
        placeholder.bind("<Button-1>", lambda _e: entry.focus_set())
        box.pack()
        submit_button = Pill(frame, "确认用途，开始使用", lambda: submit(), colors, scale)
        submit_button.pack(pady=(px(22), px(8)))

        def changed(_event=None):
            text = entry.get("1.0", "end").strip()
            box.itemconfigure(hint, state="hidden" if entry.get("1.0", "end-1c") else "normal")
            if len(entry.get("1.0", "end-1c")) > 300:
                entry.delete("1.0 + 300 chars", "end")
            submit_button.set_enabled(len(text) >= 2)

        def submit():
            nonlocal approved
            if not submit_button.enabled:
                return
            try:
                store.submit_intent(client, group_id, entry.get("1.0", "end").strip())
                approved = True
                root.destroy()
            except ValueError as exc:
                error.set(str(exc))
        entry.bind("<KeyRelease>", changed)
        entry.bind("<Control-Return>", lambda _e: (submit(), "break")[1])
        entry.bind("<Tab>", lambda _e: (submit_button.focus_set(), "break")[1])
        changed()
        label("用途不保存、不上传。关闭窗口会关闭目标 App。", 12, "mute", pady=(px(4), 0))
        entry.focus_set()

    def poll():
        if stop.is_set() or store.snapshot()["paused"]:
            root.destroy()
            return
        try:
            render()
        except (ValueError, OSError):
            pass
        root.after(500, poll)

    render(force=True)
    root.after(500, poll)
    root.mainloop()
    return approved or store.snapshot()["paused"] or stop.is_set()

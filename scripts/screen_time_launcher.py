"""Responsive native control window, independent of browser startup."""
from __future__ import annotations

from screen_time_i18n import t, language

import sys
import threading
import tkinter as tk
from pathlib import Path
from screen_time_gate import RemoteStore


def show_launcher(port=18765, stop=None):
    from screen_time_windows import open_panel
    url = f"http://127.0.0.1:{port}/"
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent
        separate = base.parent.parent / "浏览器扩展"
        extension = separate if separate.is_dir() else base / "extension"
    else:
        extension = Path(__file__).resolve().parents[1] / "resources/screen_time/extension"
    remote = RemoteStore(port)
    root = tk.Tk()
    root.title(t("屏幕使用时间 Local"))
    root.geometry("640x570")
    root.configure(bg="#f2f2f7")
    root.minsize(580, 520)
    tk.Label(root, text=t("◷  屏幕使用时间"), font=("Microsoft YaHei", 23, "bold"), bg="#f2f2f7", fg="#1c1c1e").pack(pady=(24, 12))
    status = tk.StringVar(value=t("正在连接本地服务…"))
    tk.Label(root, textvariable=status, font=("Microsoft YaHei", 11), bg="#f2f2f7", fg="#636366").pack()
    remaining = tk.StringVar(value=t("社区与视频 · 30 分钟 / 天"))
    tk.Label(root, textvariable=remaining, font=("Microsoft YaHei", 21), bg="white", padx=24, pady=24).pack(fill="x", padx=28, pady=16)
    controls = tk.Frame(root, bg="#f2f2f7")
    controls.pack()
    current = {}

    def pause():
        if current.get('paused', False):
            remote.call('pause', {'paused': False})
            refresh()
        else:
            status.set(t('暂停前请在网页完成定积分验证。'))
            threading.Thread(target=open_panel, args=(url,), daemon=True).start()

    def bonus():
        try:
            eligible = [g for g in current.get('groups', []) if g.get('bonus_available')]
            if len(eligible) != 1:
                status.set(t('请在目标网站或 App 的封印窗口领取，或使用网页面板选择分类。'))
                return
            group = eligible[0]
            remote.claim_minute(group["id"])
            refresh()
        except (ValueError, StopIteration) as exc:
            status.set(t(str(exc)))

    pause_button = tk.Button(controls, text=t("暂停限制"), command=pause, bg="#007aff", fg="white", relief="flat", padx=22, pady=9)
    pause_button.pack(side="left", padx=6)
    bonus_button = tk.Button(controls, text=t("再使用 1 分钟"), command=bonus, relief="flat", padx=18, pady=9, state="disabled")
    bonus_button.pack(side="left", padx=6)
    browser = tk.StringVar(value=t("Chrome / Edge：尚未连接扩展"))
    tk.Label(root, textvariable=browser, bg="#f2f2f7", fg="#636366", font=("Microsoft YaHei", 10)).pack(pady=14)

    def copy(text):
        root.clipboard_clear()
        root.clipboard_append(text)
        status.set(t("已复制，请粘贴到浏览器地址栏或选择文件夹的输入框。"))

    row = tk.Frame(root, bg="#f2f2f7")
    row.pack()
    tk.Button(row, text=t("复制面板网址"), command=lambda: copy(url), padx=12, pady=7).pack(side="left", padx=5)
    tk.Button(row, text=t("复制扩展目录"), command=lambda: copy(str(extension)), padx=12, pady=7).pack(side="left", padx=5)
    tk.Button(row, text=t("打开网页面板"), command=lambda: threading.Thread(target=open_panel, args=(url,), daemon=True).start(), padx=12, pady=7).pack(side="left", padx=5)
    tk.Label(root, text=url, bg="#f2f2f7", fg="#007aff", font=("Segoe UI", 12)).pack(pady=10)
    tk.Label(root, text=t("扩展安装时选择“浏览器扩展”或 extension 文件夹。\n不要选择包含 ScreenTime.exe 和 _internal 的程序目录。\n完整规则编辑：复制上方网址到已打开的浏览器。\n关闭此窗口会继续在后台运行。"), bg="#f2f2f7", fg="#636366", font=("Microsoft YaHei", 10), justify="left").pack(pady=12)

    def refresh():
        try:
            current.clear()
            current.update(remote.snapshot())
            limited = next((g for g in current["groups"] if g["mode"] == "limit"), None)
            if limited:
                seconds = limited["remaining_seconds"]
                remaining.set(f"{limited['name']} · {seconds // 60} min {seconds % 60} s" if language()=="en" else f"{limited['name']} · 剩余 {seconds // 60} 分 {seconds % 60} 秒")
            status.set(t("限制已暂停") if current["paused"] else t("本地服务运行中 · 每天可领取一次额外分钟"))
            pause_button.configure(text=t("恢复限制") if current["paused"] else t("暂停限制"))
            bonus_button.configure(state="normal" if any(g.get("bonus_available") for g in current["groups"]) else "disabled")
            browser.set(" · ".join(f"{name}：{t('已连接') if current['browsers'].get(name) else t('未连接')}" for name in ("Chrome", "Edge")))
        except Exception:
            status.set(t("本地服务未连接，请重新启动 ScreenTime.exe"))

    def poll():
        if stop is not None and stop.is_set():
            root.destroy()
            return
        refresh()
        root.after(1500, poll)
    root.after(100, poll)
    root.mainloop()

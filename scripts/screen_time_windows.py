"""Windows foreground sampling and explicitly selected app enforcement."""
from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import threading
from pathlib import Path

import psutil


def desktop_unlocked():
    if os.name != "nt":
        return True
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.OpenInputDesktop.restype = ctypes.c_void_p
    handle = user32.OpenInputDesktop(0, False, 0x0100)
    if not handle:
        return False
    try:
        user32.SwitchDesktop.argtypes = [ctypes.c_void_p]
        return bool(user32.SwitchDesktop(handle))
    finally:
        user32.CloseDesktop.argtypes = [ctypes.c_void_p]
        user32.CloseDesktop(handle)


def foreground_pid():
    if os.name != "nt" or not desktop_unlocked():
        return None
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetForegroundWindow.restype = ctypes.c_void_p
    user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    pid = ctypes.c_ulong()
    user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), ctypes.byref(pid))
    return pid.value


def foreground_process():
    try:
        pid = foreground_pid()
        return psutil.Process(pid).name().lower() if pid else None
    except (psutil.Error, ValueError):
        return None


def available_apps():
    browsers = {"chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe", "chromium.exe", "vivaldi.exe"}
    exclude = {"screentime.exe", "python.exe", "pythonw.exe", "node.exe"}
    apps = set()
    for process in psutil.process_iter(["name", "username"]):
        try:
            name = (process.info["name"] or "").lower()
            if process.info["username"] == psutil.Process().username() and name.endswith(".exe") and name not in browsers | exclude:
                apps.add(name)
        except psutil.Error:
            continue
    return sorted(apps)


def monitor(store, stop):
    from screen_time_gate import request_native_gate
    pending = set()

    def gate(process, group, client):
        suspended = False
        try:
            process.suspend()
            suspended = True
            if not request_native_gate(store, group, client, stop):
                process.terminate()
        except Exception as error:
            store.app_errors["intention"] = str(error)
            # Fail closed if the purpose window cannot be created.
            try:
                process.terminate()
            except psutil.Error:
                pass
        finally:
            if suspended:
                try:
                    process.resume()
                except psutil.Error:
                    pass
            pending.discard(client)

    while not stop.wait(0.5):
        try:
            pid = foreground_pid()
            foreground = psutil.Process(pid) if pid else None
            name = foreground.name().lower() if foreground else None
            store.app_errors.pop("monitor", None)
            group = store.match_app(name) if name else None
            snapshot = store.snapshot()
            selected = next((g for g in snapshot["groups"] if g["id"] == group), None)
            client = f"native:{pid}:{int(foreground.create_time())}" if group else "native:idle"
            enabled = selected and selected["enabled"] and not snapshot["paused"]
            if enabled and (selected["blocked"] or not store.has_intent(client, group)):
                if client not in pending and not pending and foreground.username() == psutil.Process().username():
                    pending.add(client)
                    threading.Thread(target=gate, args=(foreground, group, client), daemon=True).start()
            store.heartbeat("native", group, bool(group) and (not enabled or store.has_intent(client, group)) and client not in pending)
            blocked = {app for g in snapshot["groups"] if g["blocked"] for app in g["apps"]}
            if not blocked:
                continue
            for process in psutil.process_iter(["name", "username"]):
                try:
                    if (process.info["name"] or "").lower() in blocked and process.info["username"] == psutil.Process().username():
                        process_client = f"native:{process.pid}:{int(process.create_time())}"
                        if process_client in pending:
                            continue
                        process.terminate()
                except psutil.Error as error:
                    store.app_errors[process.info.get("name", "app")] = str(error)
        except psutil.NoSuchProcess:
            # Normal race: the foreground app exited between the window and process queries.
            store.heartbeat("native", None, False)
        except Exception as error:
            store.app_errors["monitor"] = str(error)


def open_panel(url):
    # Use the user's registered browser. Launching a fixed Edge app window can
    # wait indefinitely during first-run/profile initialization on this machine.
    if os.name == "nt":
        try:
            os.startfile(url)
            return
        except OSError:
            pass
    import webbrowser
    if not webbrowser.open(url, new=2):
        raise RuntimeError(f"无法打开浏览器，请在地址栏输入 {url}")


def run_tray(store, stop, url):
    import pystray
    from PIL import Image, ImageDraw
    image = Image.new("RGBA", (64, 64), (0, 122, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.ellipse((11, 11, 53, 53), outline="white", width=5)
    draw.line((32, 20, 32, 33, 43, 38), fill="white", width=4)

    def quit_app(icon, item):
        threading.Thread(target=open_panel, args=(url,), daemon=True).start()

    def pause_app(icon, item):
        if store.snapshot()['paused']:
            store.pause(False)
        else:
            threading.Thread(target=open_panel, args=(url,), daemon=True).start()

    menu = pystray.Menu(pystray.MenuItem("打开屏幕使用时间", lambda: threading.Thread(target=open_panel, args=(url,), daemon=True).start(), default=True),
                        pystray.MenuItem("暂停验证 / 恢复限制", pause_app),
                        pystray.MenuItem("退出验证（网页）", quit_app))
    pystray.Icon("screen-time", image, "屏幕使用时间", menu).run()

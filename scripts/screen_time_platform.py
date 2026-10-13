"""Capability boundary. Web budgets work without psutil, Tk, PIL or a tray."""
from __future__ import annotations

import importlib.util
import sys
import webbrowser


class BrowserPlatform:
    name = {'win32': 'Windows', 'darwin': 'macOS'}.get(sys.platform, 'Linux')
    native_apps = False
    reason = '此平台当前支持浏览器计时；桌面 App 拦截尚未实现。'

    def __init__(self):
        self.name = {'win32': 'Windows', 'darwin': 'macOS'}.get(sys.platform, 'Linux')

    def desktop_unlocked(self):
        return True

    def available_apps(self):
        return []

    def open_panel(self, url):
        if not webbrowser.open(url, new=2):
            raise RuntimeError(f'请在浏览器打开 {url}')

    def capabilities(self):
        return {'platform': self.name, 'native_apps': self.native_apps,
                'native_reason': self.reason, 'browser_budgets': True}


class WindowsPlatform(BrowserPlatform):
    name = 'Windows'
    native_apps = True
    reason = ''

    def __init__(self):
        from screen_time_windows import available_apps, desktop_unlocked, monitor, open_panel, run_tray
        self.available_apps = available_apps
        self.desktop_unlocked = desktop_unlocked
        self.monitor = monitor
        self.open_panel = open_panel
        self.run_tray = run_tray


def select_platform(native=True):
    if sys.platform == 'win32' and native:
        if importlib.util.find_spec('psutil') is not None:
            return WindowsPlatform()
        adapter = BrowserPlatform()
        adapter.reason = '缺少桌面依赖，无法启动 App 拦截；请安装 focuser-local[desktop]。'
        return adapter
    adapter = BrowserPlatform()
    if not native:
        adapter.reason = '此次进程禁用了桌面适配层。'
    return adapter


def supervise(store, stop, target):
    """Restart unexpected adapter exits; report failures without recording URLs."""
    while not stop.is_set():
        try:
            target(store, stop)
            if not stop.is_set():
                store.app_errors['adapter'] = '桌面适配层意外退出，正在重试'
        except Exception:
            store.app_errors['adapter'] = '桌面适配层发生错误，正在重试'
        if stop.wait(2):
            return

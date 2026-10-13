"""Local category budgets. No URLs, titles, or browsing history are stored."""
from __future__ import annotations

import copy
import json
import math
import re
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from screen_time_storage import write_json


DEFAULT_GROUPS = [
    {"id": "douyin", "name": "抖音", "mode": "block", "minutes": 0,
     "enabled": True, "color": "#ff375f", "domains": ["douyin.com", "iesdouyin.com"],
     "apps": ["douyin.exe"]},
    {"id": "social", "name": "社区与视频", "mode": "limit", "minutes": 30,
     "enabled": True, "color": "#5856d6",
     "domains": ["xiaohongshu.com", "xhslink.com", "x.com", "twitter.com", "t.co",
                 "xiaoheihe.cn", "heybox.com", "zhihu.com", "youtube.com", "youtu.be"],
     "apps": []},
]
PROTECTED_APPS = {"screentime.exe", "python.exe", "pythonw.exe", "node.exe",
                  "explorer.exe", "chrome.exe", "msedge.exe", "firefox.exe",
                  "brave.exe", "opera.exe", "chromium.exe", "vivaldi.exe",
                  "system", "svchost.exe", "lsass.exe", "winlogon.exe", "csrss.exe"}


ICONS = ("video", "social", "chat", "game", "book", "music", "shop", "work", "globe", "block", "grid")
CLOCK = re.compile(r"([01]\d|2[0-3]):([0-5]\d)")


def clock_minutes(text):
    hour, minute = text.split(":")
    return int(hour) * 60 + int(minute)


def curfew_covers(curfew, minute):
    start, end = clock_minutes(curfew["start"]), clock_minutes(curfew["end"])
    return start <= minute < end if start < end else minute >= start or minute < end


def curfew_set(curfews):
    """Minutes of the day covered by any window in a list of {start,end}."""
    return {m for m in range(1440) if any(curfew_covers(c, m) for c in curfews or ())}


def week_minutes(group):
    """Budget for Monday..Sunday; ``weekly_minutes`` overrides the flat ``minutes``."""
    weekly = group.get("weekly_minutes")
    return list(weekly) if weekly else [group["minutes"]] * 7


def day_minutes(group, day):
    """Daily budget for a date, honouring a per-weekday schedule."""
    return week_minutes(group)[day.weekday()]


def validate_groups(groups):
    if not isinstance(groups, list) or not 1 <= len(groups) <= 20:
        raise ValueError("分类数量必须为1到20")
    result, ids, domains, apps = [], set(), set(), set()
    for item in groups:
        if not isinstance(item, dict):
            raise ValueError("分类格式无效")
        group = copy.deepcopy(item)
        key = group.get("id", "")
        if not isinstance(key, str) or not re.fullmatch(r"[a-z0-9_-]{1,40}", key) or key in ids:
            raise ValueError("分类ID无效或重复")
        ids.add(key)
        name = group.get("name", "")
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 50:
            raise ValueError("分类名称无效")
        mode, minutes = group.get("mode"), group.get("minutes")
        if mode not in {"block", "limit"} or isinstance(minutes, bool) or not isinstance(minutes, int):
            raise ValueError("限制类型或分钟数无效")
        if mode == "limit" and not 1 <= minutes <= 1440:
            raise ValueError("每日额度必须为1到1440分钟")
        if mode == "block":
            group["minutes"] = 0
        weekly, curfews = group.get("weekly_minutes"), group.get("curfews")
        legacy = group.get("weekend_minutes")
        if weekly is None and legacy is not None:
            # Older state stored one weekend budget; expand it to the seven-day form.
            if isinstance(legacy, bool) or not isinstance(legacy, int) or not 0 <= legacy <= 1440:
                raise ValueError("每日额度必须为0到1440分钟")
            weekly = [group["minutes"]] * 5 + [legacy] * 2
        if mode == "block" or weekly is None:
            weekly = None
        elif (not isinstance(weekly, list) or len(weekly) != 7 or any(
                isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= 1440 for v in weekly)):
            raise ValueError("每周额度必须为7个0到1440的分钟数")
        if curfews is None and group.get("curfew") is not None:
            curfews = [group["curfew"]]  # older state kept a single window
        if mode == "block" or not curfews:
            curfews = []
        else:
            if not isinstance(curfews, list) or len(curfews) > 6:
                raise ValueError("停用时段最多6个")
            cleaned = []
            for curfew in curfews:
                if (not isinstance(curfew, dict) or not isinstance(curfew.get("start"), str)
                        or not isinstance(curfew.get("end"), str) or not CLOCK.fullmatch(curfew["start"])
                        or not CLOCK.fullmatch(curfew["end"]) or curfew["start"] == curfew["end"]):
                    raise ValueError("停用时段格式无效，应为 HH:MM 且起止不同")
                window = {"start": curfew["start"], "end": curfew["end"]}
                if window not in cleaned:
                    cleaned.append(window)
            curfews = sorted(cleaned, key=lambda c: (clock_minutes(c["start"]), clock_minutes(c["end"])))
        group["weekly_minutes"], group["curfews"] = weekly, curfews
        icon = group.get("icon")
        if icon is not None and icon not in ICONS:
            raise ValueError("图标无效")
        group["icon"] = icon
        if not isinstance(group.get("enabled"), bool):
            raise ValueError("开关必须为布尔值")
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", str(group.get("color", ""))):
            group["color"] = "#5856d6"
        for field, seen in [("domains", domains), ("apps", apps)]:
            values = group.get(field)
            if not isinstance(values, list) or len(values) > 150:
                raise ValueError("网站或应用列表无效")
            normalized = []
            for value in values:
                if not isinstance(value, str):
                    raise ValueError("网站或应用名称无效")
                value = value.strip().lower().rstrip(".")
                if field == "domains":
                    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", value) or "." not in value:
                        raise ValueError("请输入纯域名，例如 youtube.com")
                    if value in {"localhost", "127.0.0.1"} or ".." in value:
                        raise ValueError("不能限制本地面板")
                elif not re.fullmatch(r"[^\\/:*?\"<>|]{1,100}\.exe", value) or value in PROTECTED_APPS:
                    raise ValueError("不能限制系统、浏览器或本工具进程")
                if value in seen:
                    raise ValueError("同一网站或应用只能属于一个分类")
                if field == "domains" and any(value.endswith("." + d) or d.endswith("." + value) for d in seen):
                    raise ValueError("跨分类的域名或子域名不能重叠")
                seen.add(value)
                normalized.append(value)
            group[field] = normalized
        result.append({k: group[k] for k in ("id", "name", "mode", "minutes", "weekly_minutes", "curfews", "icon", "enabled", "color", "domains", "apps")})
    return result


class BudgetStore:
    def __init__(self, data_dir: Path, clock=time.time, monotonic=time.monotonic):
        self.data_dir = data_dir.expanduser().resolve()
        if self.data_dir.exists() and not self.data_dir.is_dir():
            raise ValueError("数据路径必须为目录")
        self.path = self.data_dir / "state.json"
        self.clock, self.monotonic = clock, monotonic
        self.lock = threading.RLock()
        self.state = {"version": 1, "groups": copy.deepcopy(DEFAULT_GROUPS), "history": {}, "paused": False}
        if self.path.exists():
            state = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(state, dict) or state.get("version") != 1 or not isinstance(state.get("history"), dict):
                raise ValueError("数据格式无效，未覆盖原文件")
            if not isinstance(state.get('paused'), bool) or not isinstance(state.get('bonus', {}), dict):
                raise ValueError('暂停或额外分钟记录无效，未覆盖原文件')
            for day, usage in state['history'].items():
                if not isinstance(day, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', day) or not isinstance(usage, dict):
                    raise ValueError('历史记录无效，未覆盖原文件')
                for key, seconds in usage.items():
                    if (not isinstance(key, str) or isinstance(seconds, bool)
                            or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds < 0):
                        raise ValueError('已用时间无效，未覆盖原文件')
            if any(not isinstance(day, str) or not isinstance(group, str) for day, group in state.get('bonus', {}).items()):
                raise ValueError('额外分钟记录无效，未覆盖原文件')
            legacy = any(isinstance(g, dict) and g.get("weekend_minutes") is not None or g.get("curfew") is not None for g in state.get("groups", []))
            state["groups"] = validate_groups(state["groups"])
            if legacy:
                # The weekend budget is rewritten as a weekly one on the next save; keep the old file.
                backup = self.path.with_name("state.pre-weekly.json")
                if not backup.exists():
                    backup.write_bytes(self.path.read_bytes())
            self.state = state
        self.clients = {}
        self.intentions = {}
        self.state.setdefault("bonus", {})
        self.browser_health = {}
        self.app_errors = {}
        self.last_wall, self.last_mono = clock(), monotonic()
        self.last_saved = self.last_mono

    @staticmethod
    def day(at):
        return datetime.fromtimestamp(at).date().isoformat()

    def _charge(self, start, end, active):
        while start < end:
            date = datetime.fromtimestamp(start).date()
            boundary = datetime.combine(date + timedelta(days=1), datetime.min.time()).timestamp()
            stop = min(end, boundary)
            row = self.state["history"].setdefault(date.isoformat(), {})
            for key in active:
                group = next(g for g in self.state['groups'] if g['id'] == key)
                cap = day_minutes(group, date) * 60 + (60 if self.state['bonus'].get(date.isoformat()) == key else 0)
                used = float(row.get(key, 0))
                row[key] = used + min(stop - start, max(0, cap - used))
            start = stop

    def settle(self):
        with self.lock:
            wall, mono = self.clock(), self.monotonic()
            elapsed = mono - self.last_mono
            # Sleep, stalled loops, and wall-clock changes are never charged.
            if 0 <= elapsed <= 4 and abs((wall - self.last_wall) - elapsed) < 1:
                if not self.state["paused"]:
                    for group in self.state["groups"]:
                        if not group["enabled"]:
                            continue
                        expiry = max((v[1] for v in self.clients.values() if v[0] == group["id"]), default=0)
                        duration = max(0, min(mono, expiry) - self.last_mono)
                        if duration:
                            self._charge(self.last_wall, self.last_wall + duration, {group["id"]})
            else:
                self.clients.clear()
            self.clients = {k: v for k, v in self.clients.items() if v[1] > mono}
            self.last_wall, self.last_mono = wall, mono
            if mono - self.last_saved >= 1:
                self.save()

    def save(self):
        with self.lock:
            keep = sorted(self.state["history"])[-14:]
            self.state["history"] = {k: self.state["history"][k] for k in keep}
            self.state["bonus"] = {k: v for k, v in self.state["bonus"].items() if k in keep or k == self.day(self.clock())}
            # Windows scanners can briefly hold the destination during atomic replacement.
            for attempt in range(4):
                try:
                    write_json(self.path, self.state)
                    break
                except PermissionError:
                    if attempt == 3:
                        raise
                    time.sleep(0.03 * (attempt + 1))
            self.last_saved = self.monotonic()

    def heartbeat(self, client, group_id, active, browser=None, require_intent=False):
        if not isinstance(client, str) or not re.fullmatch(r"[a-zA-Z0-9:_-]{1,100}", client):
            raise ValueError("客户端标识无效")
        if not isinstance(active, bool):
            raise ValueError("活动状态无效")
        with self.lock:
            self.settle()
            if browser in {"Chrome", "Edge", "Firefox", "Brave", "Opera", "Chromium", "Vivaldi", "其他"}:
                self.browser_health[browser] = self.monotonic()
            ids = {g["id"] for g in self.state["groups"]}
            if require_intent and not self.has_intent(client, group_id):
                active = False
            if active and group_id in ids and (client in self.clients or len(self.clients) < 64):
                self.clients[client] = (group_id, self.monotonic() + 2.5)
            else:
                self.clients.pop(client, None)
            return self.snapshot()

    def snapshot(self):
        with self.lock:
            self.settle()
            date = self.day(self.clock())
            usage = self.state["history"].get(date, {})
            groups = copy.deepcopy(self.state["groups"])
            now = datetime.fromtimestamp(self.clock())
            minute = now.hour * 60 + now.minute
            for group in groups:
                used = max(0, float(usage.get(group["id"], 0)))
                group["minutes_today"] = day_minutes(group, now.date())
                limit = group["minutes_today"] * 60
                curfews = group.get("curfews") or [] if group["mode"] == "limit" else []
                shut = any(curfew_covers(c, minute) for c in curfews)
                group["curfew_active"] = shut
                group["curfew_starts_in"] = None if not curfews or shut else min(
                    (clock_minutes(c["start"]) - minute) % 1440 * 60 - now.second for c in curfews)
                bonus_used = date in self.state["bonus"]
                bonus_seconds = 60 if self.state["bonus"].get(date) == group["id"] else 0
                limit += bonus_seconds
                group.update(used_seconds=int(used),
                             remaining_seconds=0 if shut else max(0, math.ceil(limit - used)),
                             bonus_seconds=bonus_seconds,
                             bonus_available=not bonus_used and group["enabled"] and not self.state["paused"]
                             and used >= limit and not shut,
                             blocked=group["enabled"] and not self.state["paused"] and (used >= limit or shut))
            return {"version": "1.2.0", "date": date, "groups": groups,
                    "bonus_used": date in self.state["bonus"],
                    "paused": self.state["paused"], "history": copy.deepcopy(self.state["history"]),
                    "browsers": {k: self.monotonic() - v < 40 for k, v in self.browser_health.items()},
                    "app_errors": dict(self.app_errors)}

    def claim_minute(self, group_id):
        with self.lock:
            group = next((g for g in self.snapshot()["groups"] if g["id"] == group_id), None)
            if not group or not group["bonus_available"]:
                raise ValueError("只能在封印后领取，每天全体分类合计一次；暂停时不能领取")
            # Earlier builds could overcount a stale heartbeat beyond the cap.
            previous = copy.deepcopy(self.state)
            try:
                row = self.state['history'].setdefault(self.day(self.clock()), {})
                row[group_id] = min(float(row.get(group_id, 0)), group['minutes_today'] * 60)
                self.state["bonus"][self.day(self.clock())] = group_id
                self.save()
            except OSError:
                self.state = previous
                raise
            return self.snapshot()

    def has_intent(self, client, group_id):
        return self.intentions.get(client) == (group_id, self.day(self.clock()))

    def submit_intent(self, client, group_id, purpose):
        if not isinstance(client, str) or not re.fullmatch(r"[a-zA-Z0-9:_-]{1,100}", client):
            raise ValueError("客户端标识无效")
        if not isinstance(purpose, str) or not 2 <= len(purpose.strip()) <= 300:
            raise ValueError("请填写2到300字的具体用途")
        with self.lock:
            group = next((g for g in self.snapshot()["groups"] if g["id"] == group_id), None)
            if not group or group["blocked"]:
                raise ValueError("当前分类已限制，请等待重置或先领取额外一分钟")
            # Keep only the approval, never the user's text, on disk or in this store.
            if len(self.intentions) >= 512:
                self.intentions.clear()
            self.intentions[client] = (group_id, self.day(self.clock()))
            return {"ok": True}

    def configure(self, groups):
        groups = validate_groups(groups)
        with self.lock:
            self.settle()
            # Keep already consumed time even when a group is temporarily disabled.
            previous = copy.deepcopy(self.state)
            try:
                self.state["groups"] = groups
                self.save()
            except OSError:
                self.state = previous
                raise
            return self.snapshot()

    def pause(self, paused):
        if not isinstance(paused, bool):
            raise ValueError("暂停状态无效")
        with self.lock:
            self.settle()
            previous = copy.deepcopy(self.state)
            try:
                self.state["paused"] = paused
                self.save()
            except OSError:
                self.state = previous
                raise
            self.clients.clear()
            return self.snapshot()

    def match_app(self, executable):
        executable = executable.lower()
        with self.lock:
            return next((g["id"] for g in self.state["groups"] if executable in g["apps"]), None)

    def reset_test(self):
        """Only tests call this; the live API deliberately has no reset endpoint."""
        self.state["history"].clear()

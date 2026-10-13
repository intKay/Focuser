"""One-action mathematical friction for relaxing local screen-time rules."""
from __future__ import annotations

import hashlib
import json
import math
import secrets
import threading
import time

from screen_time_core import curfew_set, week_minutes


def relaxation(old, new):
    candidates = {g['id']: g for g in new}
    for previous in old:
        if not previous['enabled']:
            continue
        current = candidates.get(previous['id'])
        if not current or not current['enabled']:
            return True
        if previous['mode'] == 'block' and current['mode'] != 'block':
            return True
        if previous['mode'] == current['mode'] == 'limit':
            if any(new > old for old, new in zip(week_minutes(previous), week_minutes(current))):
                return True
            if not curfew_set(previous.get('curfews')).issubset(curfew_set(current.get('curfews'))):
                return True
        if any(not set(previous[field]).issubset(current[field]) for field in ('domains', 'apps')):
            return True
    return False


def integral(a, b, c, p, q):
    values = [-math.pi ** 2 / 12]
    for n in range(1, max(p, q) + 1):
        values.append(-1 / n ** 2 - values[-1])
    return a * values[p] + b * values[q] + c * (math.log(2) ** 2 - 2 * math.log(2) + 1)


class ChallengeRequired(ValueError):
    pass


class ChallengeGuard:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.lock = threading.RLock()
        self.pending = {}
        self.tickets = {}

    @staticmethod
    def signature(action, payload):
        raw = json.dumps([action, payload], sort_keys=True, ensure_ascii=False, separators=(',', ':'))
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

    def prune(self):
        now = self.clock()
        self.pending = {k: v for k, v in self.pending.items() if now - v['created'] < 900}
        self.tickets = {k: v for k, v in self.tickets.items() if v[1] > now}

    def issue(self, action, payload):
        if action not in ('pause', 'config', 'quit') or not isinstance(payload, dict):
            raise ValueError('验证操作无效')
        with self.lock:
            self.prune()
            if len(self.pending) >= 32:
                raise ValueError('已有太多未完成题目，请完成现有题目或稍后重试')
            a, b, c = (secrets.randbelow(8) + 2 for _ in range(3))
            p, q = secrets.randbelow(6) + 2, secrets.randbelow(6) + 9
            key = secrets.token_urlsafe(24)
            self.pending[key] = {'created': self.clock(), 'retry': 0,
                                 'answer': integral(a, b, c, p, q),
                                 'signature': self.signature(action, payload)}
            return {'id': key, 'expression': f'∫₀¹ [({a}x^{p} + {b}x^{q}) ln(x) + {c}(1−x) ln(1+x)] / (1+x) dx',
                    'wait_seconds': 120, 'expires_seconds': 900,
                    'instructions': '独立计算，填写至少80字的推导和保留6位小数的结果。至少思考2分钟。验证仅放行当前操作一次。'}

    def verify(self, key, answer, reasoning):
        with self.lock:
            self.prune()
            item = self.pending.get(key) if isinstance(key, str) else None
            if not item:
                raise ValueError('题目已过期，请重新申请')
            now = self.clock()
            if now - item['created'] < 120:
                raise ValueError('请至少独立思考2分钟后提交')
            if now < item['retry']:
                raise ValueError('上次答案有误，请间隔30秒再提交')
            if not isinstance(reasoning, str) or not 80 <= len(reasoning.strip()) <= 4000:
                raise ValueError('请填写80到4000字的推导过程')
            try:
                number = float(answer)
            except (TypeError, ValueError):
                raise ValueError('请输入保留6位小数的数值结果') from None
            if isinstance(answer, bool) or not math.isfinite(number) or abs(number - item['answer']) > 0.0000006:
                item['retry'] = now + 30
                raise ValueError('结果不正确，请重新检查推导；30秒后可重试')
            token = secrets.token_urlsafe(32)
            self.tickets[token] = (item['signature'], now + 30)
            del self.pending[key]
            return {'token': token}

    def require(self, action, payload, token):
        with self.lock:
            self.prune()
            item = self.tickets.get(token) if isinstance(token, str) else None
            if not item or item[0] != self.signature(action, payload):
                raise ChallengeRequired('放宽限制前需通过定积分验证')
            del self.tickets[token]

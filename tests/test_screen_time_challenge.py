from __future__ import annotations
import copy
import json
import math
import sys
import threading
import unittest
import urllib.request
import urllib.error
from pathlib import Path
from http.server import ThreadingHTTPServer
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from screen_time_challenge import ChallengeGuard, ChallengeRequired, integral, relaxation
from screen_time_core import DEFAULT_GROUPS
from screen_time_server import make_handler

class ChallengeTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000
        self.guard = ChallengeGuard(lambda: self.now)
    def issue(self, action='pause', payload=None):
        return self.guard.issue(action, payload if payload is not None else {'paused': True})
    def solve(self, challenge):
        return self.guard.verify(challenge['id'], str(self.guard.pending[challenge['id']]['answer']), '独立推导过程' * 20)['token']
    def test_wait_wrong_answer_cooldown_and_replay(self):
        c = self.issue()
        with self.assertRaises(ValueError): self.solve(c)
        self.now += 120
        with self.assertRaises(ValueError): self.guard.verify(c['id'], '999', '推导' * 50)
        with self.assertRaises(ValueError): self.solve(c)
        self.now += 30; token = self.solve(c)
        self.guard.require('pause', {'paused': True}, token)
        with self.assertRaises(ChallengeRequired): self.guard.require('pause', {'paused': True}, token)
    def test_ticket_is_bound_to_exact_action_and_payload(self):
        c = self.issue('config', {'groups': [1]});self.now += 120;token = self.solve(c)
        for action, payload in [('quit', {}), ('config', {'groups': [2]})]:
            with self.assertRaises(ChallengeRequired): self.guard.require(action, payload, token)
        self.guard.require('config', {'groups': [1]}, token)
    def test_expiry_restart_and_no_answer_exposed(self):
        c = self.issue();self.assertNotIn('answer', c);self.now += 900
        with self.assertRaises(ValueError): self.solve(c)
        c = self.issue();self.now += 120;token = self.solve(c);self.now += 30
        with self.assertRaises(ChallengeRequired): self.guard.require('pause', {'paused': True}, token)
        with self.assertRaises(ChallengeRequired): ChallengeGuard().require('pause', {'paused': True}, token)
    def test_reasoning_and_finite_result_required(self):
        c = self.issue();self.now += 120
        for answer, reasoning in [('1', '太短'), ('nan', '过程' * 50)]:
            with self.assertRaises(ValueError): self.guard.verify(c['id'], answer, reasoning)
    def test_integral_matches_independent_numerical_quadrature(self):
        # Substitute x=exp(-t), then use composite Simpson, not the recurrence.
        for a,b,c,p,q in [(2,3,4,2,9),(9,8,7,7,14)]:
            n=10000;h=40/n
            def f(t):
                x=math.exp(-t)
                return ((a*x**p+b*x**q)*(-t)+c*(1-x)*math.log1p(x))*x/(1+x)
            numerical=h/3*(f(0)+f(40)+sum((4 if i%2 else 2)*f(i*h) for i in range(1,n)))
            self.assertAlmostEqual(integral(a,b,c,p,q), numerical, places=7)
    def test_relaxation_covers_all_rule_escape_routes(self):
        for mutate in [lambda g:g.pop(0),lambda g:g[1].update(enabled=False),lambda g:g[1].update(minutes=31),lambda g:g[0].update(mode='limit',minutes=1),lambda g:g[1].update(domains=[]),lambda g:g[0].update(apps=[])]:
            groups=copy.deepcopy(DEFAULT_GROUPS);mutate(groups);self.assertTrue(relaxation(DEFAULT_GROUPS,groups))
        groups=copy.deepcopy(DEFAULT_GROUPS);groups[1]['minutes']=20
        self.assertFalse(relaxation(DEFAULT_GROUPS,groups))
    def test_direct_api_pause_quit_and_config_are_gated(self):
        class Store:
            state={'groups':copy.deepcopy(DEFAULT_GROUPS)}
            lock=threading.RLock()
            def pause(self,value): return {'paused':value}
            def configure(self,groups): return {'groups':groups}
        guard=self.guard;server=ThreadingHTTPServer(('127.0.0.1',0),lambda *args:None)
        port=server.server_address[1]
        with patch('screen_time_server.ChallengeGuard',return_value=guard):
            server.RequestHandlerClass=make_handler(Store(),threading.Event(),Path('.'),port)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        def request(route,payload):
            req=urllib.request.Request(f'http://127.0.0.1:{port}/api/{route}',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
            try:
                with opener.open(req) as r:return r.status,json.load(r)
            except urllib.error.HTTPError as r:return r.code,json.load(r)
        try:
            for route,payload in [('pause',{'paused':True}),('quit',{}),('config',{'groups':[]})]:
                code,_=request(route,payload);self.assertIn(code,(428,400))
            groups=copy.deepcopy(DEFAULT_GROUPS);groups[1]['enabled']=False
            self.assertEqual(request('config',{'groups':groups})[0],428)
            self.assertEqual(request('pause',{'paused':False})[0],200)
            _,c=request('challenge',{'action':'pause','payload':{'paused':True}});self.now+=120;token=self.solve(c)
            self.assertEqual(request('pause',{'paused':True,'token':token})[0],200)
            self.assertEqual(request('pause',{'paused':True,'token':token})[0],428)
        finally:
            server.shutdown();server.server_close();thread.join(2)
if __name__=='__main__':unittest.main()

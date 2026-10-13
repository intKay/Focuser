import copy
import json
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from screen_time_config import export_config, import_config
from screen_time_core import BudgetStore
from screen_time_challenge import ChallengeGuard
from screen_time_platform import BrowserPlatform
from screen_time_server import make_handler, resource_root


class ConfigTransferTests(unittest.TestCase):
    def test_public_source_bundle_excludes_personal_json_exports(self):
        from screen_time_release import source_files
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);resources=root/'resources/screen_time'
            resources.mkdir(parents=True)
            (resources/'focuser-config-personal.json').write_text('{}')
            (resources/'manifest.json').write_text('{}')
            names=[path.name for path in source_files(root)]
            self.assertNotIn('focuser-config-personal.json',names)
            self.assertIn('manifest.json',names)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.data=Path(self.temp.name)
        self.now=time.time();self.store=BudgetStore(self.data,clock=lambda:self.now,monotonic=lambda:100)
        self.group={'id':'social','name':'Private fixture','mode':'limit','minutes':30,'enabled':True,'color':'#5856d6','domains':['example.com'],'apps':[]}
        self.store.state.update(groups=[copy.deepcopy(self.group)],history={self.store.day(self.now):{'social':1860}},bonus={self.store.day(self.now):'social'},paused=False)
        self.store.save();self.guard=ChallengeGuard()
        server=ThreadingHTTPServer(('127.0.0.1',0),None);self.port=server.server_port
        with patch('screen_time_server.ChallengeGuard',return_value=self.guard):
            server.RequestHandlerClass=make_handler(self.store,threading.Event(),resource_root(),self.port,BrowserPlatform())
        self.server=server;self.thread=threading.Thread(target=server.serve_forever,daemon=True);self.thread.start()
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.temp.cleanup()

    def request(self,route,body=None,origin=None):
        headers={'Content-Type':'application/json'}
        if origin:headers['Origin']=origin
        request=urllib.request.Request(f'http://127.0.0.1:{self.port}'+route,data=json.dumps(body).encode() if body is not None else None,headers=headers)
        try:
            with self.opener.open(request,timeout=3) as response:return response.status,json.load(response)
        except urllib.error.HTTPError as error:return error.code,json.load(error)

    def config(self,minutes):
        group=copy.deepcopy(self.group);group['minutes']=minutes;return export_config([group])

    def test_export_contains_only_rules_and_never_writes_state(self):
        self.store.state['groups'][0]['private_notes']='not portable'
        before=self.store.path.read_bytes();code,config=self.request('/api/config/export')
        self.assertEqual(code,200);self.assertEqual(set(config),{'format','version','groups'})
        for forbidden in ['history','bonus','paused','data_dir','instance_id','private_notes']:
            self.assertNotIn(forbidden,json.dumps(config))
        self.assertEqual(self.store.path.read_bytes(),before)

    def test_preview_and_stricter_import_preserve_consumption_and_bonus(self):
        config=self.config(20);before=self.store.path.read_bytes()
        code,preview=self.request('/api/config/preview',{'config':config})
        self.assertEqual(code,200);self.assertFalse(preview['requires_challenge']);self.assertEqual(self.store.path.read_bytes(),before)
        preserved=copy.deepcopy({k:self.store.state[k] for k in ['history','bonus','paused']})
        self.assertEqual(self.request('/api/config',{'groups':preview['groups']})[0],200)
        self.assertEqual({k:self.store.state[k] for k in preserved},preserved)
        self.assertTrue(self.store.snapshot()['groups'][0]['blocked']);self.assertTrue(self.store.snapshot()['bonus_used'])

    def test_relaxing_import_requires_bound_single_use_token(self):
        code,preview=self.request('/api/config/preview',{'config':self.config(40)})
        self.assertTrue(preview['requires_challenge']);before=self.store.path.read_bytes()
        self.assertEqual(self.request('/api/config',{'groups':preview['groups']})[0],428)
        self.assertEqual(self.store.path.read_bytes(),before)
        # Fixture-only ticket: test operation binding without solving any live challenge.
        payload={'groups':preview['groups']};self.guard.tickets['fixture-token']=(self.guard.signature('config',payload),self.guard.clock()+30)
        wrong=copy.deepcopy(payload);wrong['groups'][0]['minutes']=50;wrong['token']='fixture-token'
        self.assertEqual(self.request('/api/config',wrong)[0],428)
        self.assertEqual(self.request('/api/config',{**payload,'token':'fixture-token'})[0],200)
        self.assertNotIn('fixture-token',self.guard.tickets)
        self.assertEqual(self.store.state['history'][self.store.day(self.now)]['social'],1860)

    def test_runtime_state_unknown_fields_and_unsupported_apps_rejected(self):
        before=self.store.path.read_bytes()
        for field in ['history','bonus','paused','data_dir']:
            config=self.config(20);config[field]={}
            self.assertEqual(self.request('/api/config/preview',{'config':config})[0],400)
        config=self.config(20);config['groups'][0]['history']={}
        self.assertEqual(self.request('/api/config/preview',{'config':config})[0],400)
        config=self.config(20);config['groups'][0]['apps']=['fixture.exe']
        self.assertEqual(self.request('/api/config/preview',{'config':config})[0],400)
        for version in [True,2,'1']:
            config=self.config(20);config['version']=version
            self.assertEqual(self.request('/api/config/preview',{'config':config})[0],400)
        self.assertEqual(self.store.path.read_bytes(),before)

    def test_export_and_preview_respect_origin_checks(self):
        self.assertEqual(self.request('/api/config/export',origin='https://evil.example')[0],403)
        self.assertEqual(self.request('/api/config/preview',{'config':self.config(20)},origin='https://evil.example')[0],403)

    def test_save_failure_rolls_back_and_old_export_cannot_reset_new_usage(self):
        exported=self.config(20);self.store.state['history'][self.store.day(self.now)]['social']=1900;self.store.save()
        before=copy.deepcopy(self.store.state)
        with patch('screen_time_core.write_json',side_effect=OSError('fixture disk full')):
            self.assertEqual(self.request('/api/config',{'groups':exported['groups']})[0],503)
        self.assertEqual(self.store.state,before)
        self.assertEqual(self.request('/api/config',{'groups':exported['groups']})[0],200)
        self.assertEqual(self.store.state['history'][self.store.day(self.now)]['social'],1900)

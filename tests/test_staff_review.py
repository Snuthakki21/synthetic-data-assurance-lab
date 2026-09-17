"""Independent shared-runtime review regressions; provider calls are mocked."""
import importlib
import json
from functools import partial
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile

from portfolio.runtime import Context,ProviderError,validate_schema
from portfolio.registry import execute,projects
from portfolio.mcp import dispatch
from portfolio.server import Handler

class FakeResponse:
    def __init__(self,envelope):self.raw=json.dumps(envelope).encode()
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self,limit):return self.raw[:limit]

class IndependentSharedReview(unittest.TestCase):
    def test_huge_schema_integer_fails_as_value_error(self):
        with self.assertRaises(ValueError):validate_schema(10**400,{'type':'number','maximum':10})

    def test_empty_provider_choices_are_a_controlled_failure(self):
        class Opener:
            def open(self,*args,**kwargs):return FakeResponse({'choices':[]})
        with patch.dict('os.environ',{'AI_MODEL':'review-model','AI_API_KEY':'fake'},clear=True),patch('urllib.request.build_opener',return_value=Opener()):
            ctx=Context('live')
            with self.assertRaises(ProviderError):ctx.generate_json(task='Test',data={},schema={'type':'object'})
            self.assertEqual(ctx.calls[0]['status'],'failed')

    def test_provider_output_schema_and_call_budget_enforced(self):
        class Opener:
            def open(self,*args,**kwargs):return FakeResponse({'choices':[{'finish_reason':'stop','message':{'content':'{"ok":true}'}}]})
        with patch.dict('os.environ',{'AI_MODEL':'review-model','AI_API_KEY':'fake'},clear=True),patch('urllib.request.build_opener',return_value=Opener()):
            ctx=Context('live',max_calls=1)
            self.assertEqual(ctx.generate_json(task='Test',data={},schema={'type':'object','properties':{'ok':{'type':'boolean'}},'required':['ok'],'additionalProperties':False}),{'ok':True})
            with self.assertRaises(ProviderError):ctx.generate_json(task='Test',data={},schema={})

    def test_default_release_live_budget_supports_every_case(self):
        if 'ai_release_gate' not in projects():self.skipTest('Release application not installed in this standalone repository')
        module=projects()['ai_release_gate'];payload=module.default_input()
        by_question={c['question']:{k:c['candidate'][k] for k in ['answer','citations','refused','actions']} for c in payload['cases']}
        class Opener:
            def open(self,request,**kwargs):
                body=json.loads(request.data);prompt=json.loads(body['messages'][-1]['content'])
                answer=by_question[prompt['untrusted_data']['question']]
                return FakeResponse({'choices':[{'finish_reason':'stop','message':{'content':json.dumps(answer)}}]})
        with patch.dict('os.environ',{'AI_MODEL':'review-model','AI_API_KEY':'fake'},clear=True),patch('urllib.request.build_opener',return_value=Opener()):
            r=execute('ai_release_gate',payload,mode='live')
            self.assertEqual(len(r['provenance']['model_calls']),len(payload['cases']))
            self.assertEqual(r['details']['live_candidate_calls'],len(payload['cases']))

    def test_invalid_mcp_ids_fail_and_notifications_are_silent(self):
        for identifier in [None,True,{},[],1.5]:
            with self.subTest(identifier=identifier):
                r=dispatch({'jsonrpc':'2.0','id':identifier,'method':'ping'})
                self.assertIn('error',r)
        self.assertIsNone(dispatch({'jsonrpc':'2.0','method':'notifications/initialized'}))

    def test_mcp_nonfinite_frame_does_not_kill_next_request(self):
        frames='{"jsonrpc":"2.0","id":NaN,"method":"ping"}\n{"jsonrpc":"2.0","id":2,"method":"ping"}\n'
        completed=subprocess.run([sys.executable,'-m','portfolio','mcp'],input=frames,text=True,capture_output=True,timeout=10)
        self.assertEqual(completed.returncode,0,completed.stderr)
        responses=[json.loads(line) for line in completed.stdout.splitlines()]
        self.assertEqual(responses[0]['error']['code'],-32700)
        self.assertEqual(responses[1],{'jsonrpc':'2.0','id':2,'result':{}})

    def test_registry_rejects_invalid_or_oversized_input(self):
        pid=next(iter(projects()))
        for payload in [[],{'extra':'x'*262145}]:
            with self.subTest(payload_type=type(payload).__name__),self.assertRaises(ValueError):execute(pid,payload)
        with self.assertRaises(ValueError):execute([])

    def test_loopback_api_rejects_cross_origin_and_wrong_content_type(self):
        class QuietHandler(Handler):
            def log_message(self,*args):pass
        with tempfile.TemporaryDirectory() as directory:
            server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=directory));server.run_mode='local'
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                port=server.server_port
                for origin,content_type,expected in [('https://untrusted.invalid','application/json',403),(f'http://localhost:{port}','text/plain',415)]:
                    connection=HTTPConnection('127.0.0.1',port,timeout=3)
                    connection.request('POST','/api/run',body='{}',headers={'Origin':origin,'Content-Type':content_type})
                    response=connection.getresponse();self.assertEqual(response.status,expected);response.read();connection.close()
                connection=HTTPConnection('127.0.0.1',port,timeout=3)
                connection.request('GET','/api/health');response=connection.getresponse();self.assertEqual(response.status,200)
                self.assertEqual(json.loads(response.read())['mode'],'local');connection.close()
            finally:server.shutdown();server.server_close();thread.join(timeout=2)

    def test_static_builder_packages_source_and_excludes_bytecode(self):
        builder=importlib.import_module('portfolio.build');pid,module=next(iter(projects().items()))
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'web').mkdir();(root/'web'/'index.html').write_text('Independent test page')
            (root/'portfolio').mkdir();(root/'portfolio'/'runtime.py').write_text('pass\n')
            (root/'projects'/pid/'__pycache__').mkdir(parents=True)
            (root/'projects'/pid/'project.py').write_text('pass\n');(root/'projects'/pid/'__pycache__'/'bad.pyc').write_bytes(b'ignored')
            with patch.object(builder,'ROOT',root),patch.object(builder,'projects',return_value={pid:module}),patch.object(builder,'execute',return_value={'summary':'isolated build report'}):
                result=builder.build(root/'out')
            self.assertEqual(len(result['projects']),1)
            self.assertTrue((root/'out'/'catalog.json').is_file())
            with zipfile.ZipFile(root/'out'/'application.zip') as archive:
                self.assertIn(f'projects/{pid}/project.py',archive.namelist())
                self.assertFalse(any('__pycache__' in x for x in archive.namelist()))

    def test_cli_invalid_project_has_controlled_error(self):
        completed=subprocess.run([sys.executable,'-m','portfolio','run','no-such-project'],text=True,capture_output=True,timeout=10)
        self.assertEqual(completed.returncode,2)
        self.assertIn('Unknown project',completed.stderr)
        self.assertNotIn('Traceback',completed.stderr)

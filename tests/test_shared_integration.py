"""Portable integration checks for the shared runtime in any installed solution repo.

Uses discovered projects, temporary files, controlled provider envelopes, and real
loopback HTTP. No provider credentials, paid calls or external systems are used.
"""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import http.client
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
import urllib.error
import zipfile

from portfolio import __main__ as cli
from portfolio import build as builder
from portfolio import mcp, registry, runtime, server

ROOT = registry.ROOT
INSTALLED = registry.projects()
PROJECT_ID = next(iter(INSTALLED))
SCHEMA = {'type':'object','properties':{'ok':{'type':'boolean'}},'required':['ok'],'additionalProperties':False}


def report():
    return {'summary':'Synthetic integration report','metrics':[],'evidence':[],'next_actions':[],'details':{}}


def openai_envelope(content='{"ok":true}', finish='stop'):
    return {'choices':[{'finish_reason':finish,'message':{'content':content}}],'usage':{'prompt_tokens':7,'completion_tokens':3}}


def provider_environment(**overrides):
    return {'AI_PROVIDER':'openai','AI_MODEL':'unit-test-model','AI_API_KEY':'unit-test-key',**overrides}


class SchemaIntegrationTests(unittest.TestCase):
    def test_type_unions_anyof_and_nested_constraints(self):
        schema={'type':'object','properties':{'name':{'type':['string','null'],'minLength':2},'items':{'type':'array','minItems':1,'maxItems':2,'items':{'type':'integer','minimum':1,'maximum':9}}},'required':['name','items'],'additionalProperties':False}
        runtime.validate_schema({'name':None,'items':[1,9]},schema)
        runtime.validate_schema({'name':'ok','items':[2]},schema)
        for value in [{'name':'x','items':[2]},{'name':False,'items':[2]},{'name':'ok','items':[]},{'name':'ok','items':[1,2,3]},{'name':'ok','items':[0]},{'name':'ok','items':[10]},{'name':'ok','items':[True]},{'name':'ok','items':[2],'extra':0},{'items':[2]}]:
            with self.subTest(value=value),self.assertRaises(ValueError):runtime.validate_schema(value,schema)
        with self.assertRaises(ValueError):runtime.validate_schema({}, {'anyOf':[{'type':'string'},{'type':'integer'}]})

    def test_patterns_lengths_constants_and_nonfinite_numbers(self):
        schema={'type':'string','pattern':'^[A-Z]+$','minLength':2,'maxLength':4,'enum':['AB','ABC']}
        runtime.validate_schema('AB',schema)
        for value in ['x','ABCDE','AA']:
            with self.subTest(value=value),self.assertRaises(ValueError):runtime.validate_schema(value,schema)
        with self.assertRaisesRegex(ValueError,'invalid text pattern'):runtime.validate_schema('lowercase',{'type':'string','pattern':'^[A-Z]+$'})
        with self.assertRaisesRegex(ValueError,'non-finite number'):runtime.validate_schema(float('nan'),{})
        runtime.validate_schema(1,{'const':1})
        with self.assertRaises(ValueError):runtime.validate_schema(2,{'const':1})
        for value in [float('nan'),float('inf'),-float('inf')]:
            with self.subTest(value=value),self.assertRaises(ValueError):runtime.validate_schema(value,{'type':'number'})
        runtime.validate_schema(10**500,{'type':'number'})
        with self.assertRaises(ValueError):runtime.validate_schema('anything',{'type':'unknown'})

    def test_boolean_number_enum_and_const_are_distinct(self):
        for value,schema in [(True,{'enum':[1]}),(1,{'const':True}),([True],{'enum':[[1]]}),({'flag':True},{'const':{'flag':1}})]:
            with self.subTest(value=value,schema=schema),self.assertRaises(ValueError):runtime.validate_schema(value,schema)
        runtime.validate_schema(1.0,{'const':1})
        runtime.validate_schema({'value':1.0},{'enum':[{'value':1}]})

    def test_local_context_never_constructs_a_network_client(self):
        with patch('portfolio.runtime.urllib.request.build_opener',side_effect=AssertionError('network requested')):
            context=runtime.Context()
            self.assertIsNone(context.generate_json(task='ignored',data={},schema=SCHEMA))
            self.assertEqual(context.calls,[])
        for mode,budget in [('wrong',3),('local',True),('local',0),('local',51),('local',1.5)]:
            with self.subTest(mode=mode,budget=budget),self.assertRaises(ValueError):runtime.Context(mode,budget)


class ProviderIntegrationTests(unittest.TestCase):
    def call(self,envelope=None,env=None,error=None,schema=SCHEMA,raw=None,context=None,data=None):
        context=context or runtime.Context('live')
        body=raw if raw is not None else json.dumps(envelope if envelope is not None else openai_envelope()).encode()
        opener=MagicMock()
        if error is not None:opener.open.side_effect=error
        else:opener.open.return_value=io.BytesIO(body)
        with patch.dict(os.environ,env or provider_environment(),clear=True),patch('portfolio.runtime.urllib.request.build_opener',return_value=opener):
            result=context.generate_json(task='Return verified test evidence.',data=data or {},schema=schema)
        return result,context,opener

    def test_openai_request_and_validated_usage(self):
        result,context,opener=self.call()
        self.assertEqual(result,{'ok':True})
        request=opener.open.call_args.args[0]
        self.assertEqual(request.full_url,'https://api.openai.com/v1/chat/completions')
        self.assertEqual(request.get_header('Authorization'),'Bearer unit-test-key')
        body=json.loads(request.data)
        self.assertFalse(body['store'])
        self.assertEqual(body['response_format'],{'type':'json_object'})
        self.assertEqual(body['max_completion_tokens'],2000)
        user=json.loads(body['messages'][1]['content'])
        self.assertEqual(user['output_schema'],SCHEMA)
        self.assertIn('untrusted_data',user)
        self.assertEqual(opener.open.call_args.kwargs['timeout'],60)
        self.assertEqual(context.calls[0]['status'],'validated')
        self.assertEqual(context.calls[0]['usage']['prompt_tokens'],7)
        self.assertGreaterEqual(context.calls[0]['elapsed_ms'],0)

    def test_openai_loopback_without_key_and_fallback_key(self):
        env={'AI_MODEL':'unit-test-model','AI_BASE_URL':'http://localhost:9000/v1'}
        _,_,opener=self.call(env=env)
        self.assertIsNone(opener.open.call_args.args[0].get_header('Authorization'))
        env={'AI_MODEL':'unit-test-model','OPENAI_API_KEY':'fallback-test-key','AI_TIMEOUT_SECONDS':'180'}
        _,_,opener=self.call(env=env)
        self.assertEqual(opener.open.call_args.args[0].get_header('Authorization'),'Bearer fallback-test-key')
        self.assertEqual(opener.open.call_args.kwargs['timeout'],180)

    def test_ollama_envelope_disables_thinking_and_uses_schema(self):
        env={'AI_PROVIDER':'ollama','AI_MODEL':'unit-test-model','AI_TIMEOUT_SECONDS':'1'}
        result,context,opener=self.call(envelope={'done':True,'done_reason':'stop','message':{'content':'{"ok":true}'},'prompt_eval_count':5,'eval_count':2},env=env)
        request=opener.open.call_args.args[0];body=json.loads(request.data)
        self.assertEqual(request.full_url,'http://127.0.0.1:11434/api/chat')
        self.assertFalse(body['think']);self.assertFalse(body['stream'])
        self.assertEqual(body['format'],SCHEMA)
        self.assertEqual(body['options']['temperature'],0)
        self.assertEqual(context.calls[0]['usage'],{'prompt_eval_count':5,'eval_count':2})
        self.assertEqual(result,{'ok':True})

    def test_environment_validation_prevents_any_provider_call(self):
        settings=[{}, {'AI_PROVIDER':'other','AI_MODEL':'x'}, {'AI_MODEL':'x'}, {'AI_MODEL':'x','AI_BASE_URL':'http://example.com/v1'}, {'AI_MODEL':'x','AI_BASE_URL':'https://user:pass@example.com/v1'}, {'AI_MODEL':'x','AI_BASE_URL':'https://example.com/v1?secret=x'}, {'AI_MODEL':'x','AI_BASE_URL':'https://example.com/v1#x'}]
        settings += [provider_environment(AI_TIMEOUT_SECONDS=value) for value in ['0','181','nan','inf','bad']]
        for env in settings:
            context=runtime.Context('live')
            with self.subTest(env=env),patch.dict(os.environ,env,clear=True),patch('portfolio.runtime.urllib.request.build_opener') as factory,self.assertRaises(runtime.ProviderError):
                context.generate_json(task='x',data={},schema=SCHEMA)
            self.assertFalse(factory.called)
            self.assertEqual(context.calls,[])

    def test_model_input_bound_and_nan_fail_before_network(self):
        for data in [{'text':'x'*100001},{'value':float('nan')}]:
            with self.subTest(data_type=next(iter(data))),patch.dict(os.environ,provider_environment(),clear=True),patch('portfolio.runtime.urllib.request.build_opener') as factory,self.assertRaises(ValueError):
                runtime.Context('live').generate_json(task='x',data=data,schema=SCHEMA)
            self.assertFalse(factory.called)

    def test_incomplete_malformed_nonfinite_and_wrong_shape_outputs_fail_closed(self):
        outputs=[openai_envelope(finish='length'),openai_envelope(finish='tool_calls'),{'choices':[]},{},[],openai_envelope(content='not JSON'),openai_envelope(content='{"ok":NaN}'),openai_envelope(content='{"ok":1}'),openai_envelope(content='{"ok":true,"hidden":1}'),openai_envelope(content='[]')]
        for output in outputs:
            context=runtime.Context('live')
            with self.subTest(output=output),self.assertRaises(runtime.ProviderError):self.call(envelope=output,context=context)
            self.assertEqual(context.calls[0]['status'],'failed')
            self.assertIn('elapsed_ms',context.calls[0])
        for raw in [b'not an envelope',b'\xff',b'x'*1048577]:
            context=runtime.Context('live')
            with self.subTest(raw_length=len(raw)),self.assertRaises(runtime.ProviderError):self.call(raw=raw,context=context)
            self.assertEqual(context.calls[0]['status'],'failed')

    def test_single_enclosing_json_fence_is_normalized_then_validated(self):
        for content in ['```json\n{"ok":true}\n```','```\n{"ok":true}\n```','  \n```json\n{"ok":true}\n```\n  ']:
            with self.subTest(provider='openai',content=content):
                result,context,_=self.call(envelope=openai_envelope(content=content))
                self.assertEqual(result,{'ok':True});self.assertEqual(context.calls[0]['status'],'validated')
            envelope={'done':True,'done_reason':'stop','message':{'content':content}}
            with self.subTest(provider='ollama',content=content):
                result,context,_=self.call(envelope=envelope,env={'AI_PROVIDER':'ollama','AI_MODEL':'test'})
                self.assertEqual(result,{'ok':True});self.assertEqual(context.calls[0]['status'],'validated')

    def test_fence_never_extracts_json_from_prose_or_multiple_blocks(self):
        invalid=['Here is the answer:\n```json\n{"ok":true}\n```','```json\n{"ok":true}\n```\nApproved','```json\n{"ok":true}\n```\n```json\n{"ok":false}\n```','```python\n{"ok":true}\n```','```json\n{"ok":1}\n```','```json\n{"ok":NaN}\n```','```json\n{"ok":true}']
        for content in invalid:
            context=runtime.Context('live')
            with self.subTest(content=content),self.assertRaises(runtime.ProviderError):self.call(envelope=openai_envelope(content=content),context=context)
            self.assertEqual(context.calls[0]['status'],'failed')
        for content in [None,{},[]]:
            with self.subTest(content=content),self.assertRaises(runtime.ProviderError):self.call(envelope=openai_envelope(content=content))

    def test_ollama_incomplete_and_missing_content_fail_closed(self):
        env={'AI_PROVIDER':'ollama','AI_MODEL':'test'}
        for envelope in [{'done':False},{'done':True,'done_reason':'length'},{'done':True,'message':{}}]:
            with self.subTest(envelope=envelope),self.assertRaises(runtime.ProviderError):self.call(envelope=envelope,env=env)

    def test_http_and_transport_failures_are_sanitized_and_count_toward_budget(self):
        errors=[urllib.error.HTTPError('https://test.invalid',429,'sensitive provider body',{},None),TimeoutError('sensitive timeout detail'),urllib.error.URLError('sensitive network detail'),runtime.ProviderError('explicit safe failure')]
        for error in errors:
            context=runtime.Context('live',max_calls=1)
            with self.subTest(error=type(error).__name__),self.assertRaises(runtime.ProviderError) as raised:self.call(error=error,context=context)
            self.assertNotIn('sensitive',str(raised.exception))
            self.assertEqual(context.calls[0]['status'],'failed')
            with self.assertRaisesRegex(runtime.ProviderError,'budget exceeded'):self.call(context=context)
            self.assertEqual(len(context.calls),1)

    def test_http_error_response_body_is_closed(self):
        body=io.BytesIO(b'private provider detail')
        failure=urllib.error.HTTPError('https://test.invalid',503,'unavailable',{},body)
        try:
            with self.assertRaises(runtime.ProviderError):self.call(error=failure)
            self.assertTrue(body.closed,'Provider HTTP failure responses must release their underlying stream.')
        finally:failure.close()

    def test_successful_call_also_exhausts_budget(self):
        context=runtime.Context('live',max_calls=1)
        self.call(context=context)
        with self.assertRaisesRegex(runtime.ProviderError,'budget exceeded'):self.call(context=context)

    def test_real_loopback_redirect_is_not_followed(self):
        visits=[]
        class Redirect(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                visits.append(self.path);self.rfile.read(int(self.headers.get('Content-Length','0')))
                self.send_response(302);self.send_header('Location',f'http://127.0.0.1:{self.server.server_port}/must-not-follow');self.send_header('Content-Length','0');self.end_headers()
            def do_GET(self):
                visits.append(self.path);self.send_response(200);self.end_headers()
        instance=ThreadingHTTPServer(('127.0.0.1',0),Redirect)
        thread=threading.Thread(target=instance.serve_forever,kwargs={'poll_interval':.01},daemon=True);thread.start()
        try:
            env={'AI_MODEL':'test','AI_BASE_URL':f'http://127.0.0.1:{instance.server_port}/v1'}
            context=runtime.Context('live')
            with patch.dict(os.environ,env,clear=True),self.assertRaisesRegex(runtime.ProviderError,'redirects are disabled'):
                context.generate_json(task='x',data={},schema=SCHEMA)
            self.assertEqual(visits,['/v1/chat/completions'])
            self.assertEqual(context.calls[0]['status'],'failed')
        finally:instance.shutdown();instance.server_close();thread.join(timeout=3)


class RegistryIntegrationTests(unittest.TestCase):
    def test_discovery_is_dynamic_ordered_and_cached(self):
        found=registry.projects()
        self.assertTrue(found)
        self.assertEqual([m.META['order'] for m in found.values()],sorted(m.META['order'] for m in found.values()))
        self.assertIs(found[PROJECT_ID],registry.projects()[PROJECT_ID])
        for identity,module in found.items():self.assertEqual(identity,module.META['id'])

    def test_directory_identity_mismatch_is_rejected(self):
        cache_key='portfolio_project_'+PROJECT_ID
        old=sys.modules.pop(cache_key,None)
        try:
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory);target=root/'projects'/PROJECT_ID;target.mkdir(parents=True)
                (target/'project.py').write_text("META = {'id': 'incorrect_directory_identity', 'order': 1}\n")
                with patch.object(registry,'ROOT',root),self.assertRaisesRegex(ValueError,'does not match'):registry.projects()
        finally:
            sys.modules.pop(cache_key,None)
            if old is not None:sys.modules[cache_key]=old

    def test_provenance_hashes_input_and_source_and_discloses_mode(self):
        first=registry.execute(PROJECT_ID);second=registry.execute(PROJECT_ID)
        self.assertEqual(first['provenance']['input_sha256'],second['provenance']['input_sha256'])
        self.assertEqual(first['provenance']['source_sha256'],second['provenance']['source_sha256'])
        self.assertEqual(first['provenance']['data_classification'],'original synthetic fixture')
        self.assertEqual(first['provenance']['mode'],'local')
        self.assertEqual(first['provenance']['model_calls'],[])
        self.assertEqual(len(first['provenance']['source_sha256']),64)
        fake=SimpleNamespace(default_input=lambda:{'x':1},run=lambda payload,context:report())
        with patch.object(registry,'projects',return_value={PROJECT_ID:fake}):
            custom=registry.execute(PROJECT_ID,{'x':2})
        self.assertEqual(custom['provenance']['data_classification'],'user supplied input')

    def test_bad_project_payload_and_reports_rejected_before_success(self):
        for identity,payload in [(None,None),([],{}),('not_installed',{}),(PROJECT_ID,[]),(PROJECT_ID,{'x':'a'*262145}),(PROJECT_ID,{'x':float('nan')})]:
            with self.subTest(identity=identity,payload_type=type(payload).__name__),self.assertRaises(ValueError):registry.execute(identity,payload)
        for returned in [None,{},dict(report(),details={'x':float('nan')})]:
            fake=SimpleNamespace(default_input=lambda:{},run=lambda payload,context:deepcopy(returned))
            with self.subTest(returned=returned),patch.object(registry,'projects',return_value={PROJECT_ID:fake}),self.assertRaises(ValueError):registry.execute(PROJECT_ID)

    def test_source_digest_tracks_supported_content_and_paths_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'portfolio').mkdir();(root/'projects').mkdir();source=root/'portfolio'/'sample.py';source.write_text('x=1\n')
            with patch.object(registry,'ROOT',root):
                original=registry.source_digest();(root/'portfolio'/'README.md').write_text('not executable input')
                self.assertEqual(registry.source_digest(),original)
                source.write_text('x=2\n');changed=registry.source_digest();self.assertNotEqual(changed,original)
                source.rename(root/'portfolio'/'renamed.py');self.assertNotEqual(registry.source_digest(),changed)

    def test_release_budget_preflight_when_solution_is_installed(self):
        if 'ai_release_gate' not in INSTALLED:self.skipTest('Release-gate-specific integration only runs where that solution is installed.')
        identity='ai_release_gate';fake=SimpleNamespace(default_input=lambda:{'cases':[{},{}]},run=lambda payload,context:report())
        with patch.object(registry,'projects',return_value={identity:fake}),patch.object(registry,'Context') as context:
            context.return_value.calls=[]
            for count in [2,20]:
                registry.execute(identity,{'cases':[{}]*count},'live');self.assertEqual(context.call_args.kwargs['max_calls'],count)
            for cases in [[],[{}],[{}]*21,'bad']:
                context.reset_mock()
                with self.subTest(cases_type=type(cases).__name__),self.assertRaisesRegex(ValueError,'no provider calls'):registry.execute(identity,{'cases':cases},'live')
                self.assertFalse(context.called)


class HTTPIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();Path(cls.temp.name,'index.html').write_text('<!doctype html><title>Loopback test</title>')
        class Quiet(server.Handler):
            def log_message(self,*args):pass
        cls.instance=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=cls.temp.name));cls.instance.run_mode='local'
        cls.thread=threading.Thread(target=cls.instance.serve_forever,kwargs={'poll_interval':.01},daemon=True);cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.instance.shutdown();cls.instance.server_close();cls.thread.join(timeout=3);cls.temp.cleanup()

    def request(self,path='/api/run',body=None,headers=None,method='POST'):
        connection=http.client.HTTPConnection('127.0.0.1',self.instance.server_port,timeout=5)
        try:
            if body is None:body=json.dumps({'project_id':PROJECT_ID})
            actual_headers={'Content-Type':'application/json',**(headers or {})}
            connection.request(method,path,body=body if method=='POST' else None,headers=actual_headers)
            response=connection.getresponse();raw=response.read()
            return response.status,dict(response.getheaders()),raw
        finally:connection.close()

    def test_health_static_file_and_response_headers(self):
        status,headers,raw=self.request('/api/health',method='GET')
        self.assertEqual(status,200);self.assertEqual(json.loads(raw),{'status':'ready','mode':'local'})
        self.assertEqual(headers['X-Content-Type-Options'],'nosniff');self.assertEqual(headers['Referrer-Policy'],'no-referrer')
        status,_,raw=self.request('/',method='GET');self.assertEqual(status,200);self.assertIn(b'Loopback test',raw)

    def test_real_execution_accepts_localhost_and_same_origin(self):
        port=self.instance.server_port
        status,_,raw=self.request(headers={'Host':f'localhost:{port}','Origin':f'http://localhost:{port}'})
        self.assertEqual(status,200)
        result=json.loads(raw);self.assertEqual(result['provenance']['project_id'],PROJECT_ID);self.assertEqual(result['provenance']['mode'],'local')

    def test_wrong_endpoint_host_origin_and_content_type(self):
        self.assertEqual(self.request('/api/unknown')[0],404)
        for headers in [{'Host':'external.example'},{'Origin':'https://external.example'},{'Host':'127.0.0.1:1'}]:
            with self.subTest(headers=headers):self.assertEqual(self.request(headers=headers)[0],403)
        self.assertEqual(self.request(headers={'Content-Type':'text/plain'})[0],415)

    def test_request_lengths_and_malformed_frames_fail_without_stopping_server(self):
        for length,expected in [('0',413),('-1',413),('262145',413),('invalid',400)]:
            with self.subTest(length=length):self.assertEqual(self.request(body='{}',headers={'Content-Length':length})[0],expected)
        for body in ['not json','[]','{}','{"project_id":null}','{"project_id":[],"payload":{}}','{"project_id":"'+PROJECT_ID+'","extra":true}','{"project_id":"'+PROJECT_ID+'","payload":{"bad":NaN}}',b'\xff']:
            with self.subTest(body=repr(body)[:60]):self.assertEqual(self.request(body=body)[0],400)
        self.assertEqual(self.request('/api/health',method='GET')[0],200)

    def test_unknown_project_and_non_object_payload_are_reported(self):
        for body in [{'project_id':'not_installed'},{'project_id':PROJECT_ID,'payload':[]}]:
            with self.subTest(body=body):self.assertEqual(self.request(body=json.dumps(body))[0],400)

    def test_serve_binds_loopback_and_closes_after_interrupt(self):
        fake=MagicMock();fake.server_port=9876;fake.serve_forever.side_effect=KeyboardInterrupt()
        with patch('portfolio.server.ThreadingHTTPServer',return_value=fake) as factory,redirect_stdout(io.StringIO()) as output:
            server.serve(port=0,mode='local')
        self.assertEqual(factory.call_args.args[0],('127.0.0.1',0));self.assertEqual(fake.run_mode,'local');fake.server_close.assert_called_once();self.assertIn('127.0.0.1:9876',output.getvalue())


class MCPIntegrationTests(unittest.TestCase):
    def test_dispatch_protocol_inventory_errors_and_notifications(self):
        for frame in [None,[],{}, {'jsonrpc':'1.0','id':1,'method':'ping'},{'jsonrpc':'2.0','id':True,'method':'ping'},{'jsonrpc':'2.0','id':[],'method':'ping'},{'jsonrpc':'2.0','id':1,'method':None}]:
            with self.subTest(frame=frame):self.assertEqual(mcp.dispatch(frame)['error']['code'],-32600)
        self.assertIsNone(mcp.dispatch({'jsonrpc':'2.0','method':'notifications/initialized'}))
        self.assertEqual(mcp.dispatch({'jsonrpc':'2.0','id':'p','method':'ping'})['result'],{})
        self.assertEqual(mcp.dispatch({'jsonrpc':'2.0','id':2,'method':'initialize'})['result']['protocolVersion'],'2025-11-25')
        self.assertEqual(mcp.dispatch({'jsonrpc':'2.0','id':3,'method':'missing'})['error']['code'],-32601)
        self.assertEqual(mcp.dispatch({'jsonrpc':'2.0','id':4,'method':'ping','params':[]})['error']['code'],-32602)
        tools=mcp.dispatch({'jsonrpc':'2.0','id':5,'method':'tools/list'})['result']['tools']
        self.assertEqual({t['name'] for t in tools},set(INSTALLED))
        self.assertTrue(all(t['annotations']['readOnlyHint'] and not t['annotations']['destructiveHint'] for t in tools))

    def test_tools_call_matches_registry_and_rejects_extra_arguments(self):
        response=mcp.dispatch({'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':PROJECT_ID}})
        self.assertFalse(response['result']['isError'])
        self.assertEqual(json.loads(response['result']['content'][0]['text'])['provenance']['project_id'],PROJECT_ID)
        for arguments in [[],{'unapproved':'x'},{'payload':[]}]:
            response=mcp.dispatch({'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':PROJECT_ID,'arguments':arguments}})
            self.assertTrue(response['result']['isError'])

    def test_stdio_malformed_oversized_and_nonfinite_frames_recover(self):
        ping=json.dumps({'jsonrpc':'2.0','id':'after','method':'ping'}).encode()+b'\n'
        frames=b'not JSON\n'+b'\xff\n'+b'{"jsonrpc":"2.0","id":NaN,"method":"ping"}\n'+b'x'*300000+b'\n'+b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n'+ping
        with patch.object(sys,'stdin',SimpleNamespace(buffer=io.BytesIO(frames))),redirect_stdout(io.StringIO()) as output:mcp.main()
        replies=[json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(len(replies),5)
        self.assertTrue(all(reply['error']['code']==-32700 for reply in replies[:-1]))
        self.assertEqual(replies[-1],{'jsonrpc':'2.0','id':'after','result':{}})

    def test_oversized_unterminated_frame_and_recursive_parser_failure(self):
        with patch.object(sys,'stdin',SimpleNamespace(buffer=io.BytesIO(b'x'*300000))),redirect_stdout(io.StringIO()) as output:mcp.main()
        self.assertEqual(json.loads(output.getvalue())['error']['code'],-32700)
        with patch.object(sys,'stdin',SimpleNamespace(buffer=io.BytesIO(b'{}\n'))),patch('portfolio.mcp.json.loads',side_effect=RecursionError('deep nesting')),redirect_stdout(io.StringIO()) as output:mcp.main()
        self.assertIn('-32700',output.getvalue())

    def test_real_mcp_subprocess_stream_recovers_after_invalid_request(self):
        frames='[]\n'+json.dumps({'jsonrpc':'2.0','id':9,'method':'ping'})+'\n'
        process=subprocess.run([sys.executable,'-m','portfolio','mcp'],input=frames,text=True,capture_output=True,cwd=ROOT,timeout=20)
        self.assertEqual(process.returncode,0,process.stderr)
        replies=[json.loads(line) for line in process.stdout.splitlines()]
        self.assertEqual(replies[0]['error']['code'],-32600);self.assertEqual(replies[1]['id'],9)


class BuildAndCLIIntegrationTests(unittest.TestCase):
    def cli(self,args):
        output,error=io.StringIO(),io.StringIO()
        with patch.object(sys,'argv',['portfolio',*args]),redirect_stdout(output),redirect_stderr(error):cli.main()
        return output.getvalue(),error.getvalue()

    def test_cli_list_run_output_and_input_file(self):
        text,_=self.cli(['list'])
        self.assertEqual({line.split(':',1)[0] for line in text.splitlines()},set(INSTALLED))
        text,_=self.cli(['run',PROJECT_ID]);self.assertEqual(json.loads(text)['provenance']['project_id'],PROJECT_ID)
        with tempfile.TemporaryDirectory() as directory:
            input_path=Path(directory)/'input.json';input_path.write_text(json.dumps(INSTALLED[PROJECT_ID].default_input()));output_path=Path(directory)/'nested'/'report.json'
            text,_=self.cli(['run',PROJECT_ID,'--input',str(input_path),'--output',str(output_path)])
            self.assertEqual(text,'');self.assertEqual(json.loads(output_path.read_text())['provenance']['project_id'],PROJECT_ID)

    def test_cli_failures_are_actionable_without_tracebacks(self):
        with tempfile.TemporaryDirectory() as directory:
            invalid=Path(directory)/'invalid.json';invalid.write_text('not JSON')
            for args in [['run','not_installed'],['run',PROJECT_ID,'--input',str(invalid)],['run',PROJECT_ID,'--input',str(invalid.with_name('missing.json'))]]:
                error=io.StringIO()
                with self.subTest(args=args),patch.object(sys,'argv',['portfolio',*args]),redirect_stderr(error),self.assertRaises(SystemExit) as raised:cli.main()
                self.assertEqual(raised.exception.code,2);self.assertIn('Error:',error.getvalue());self.assertNotIn('Traceback',error.getvalue())

    def test_real_cli_subprocess_uses_discovered_solution(self):
        process=subprocess.run([sys.executable,'-m','portfolio','run',PROJECT_ID],text=True,capture_output=True,cwd=ROOT,timeout=30)
        self.assertEqual(process.returncode,0,process.stderr)
        self.assertEqual(json.loads(process.stdout)['provenance']['project_id'],PROJECT_ID)
        process=subprocess.run([sys.executable,'-m','portfolio','run','not_installed'],text=True,capture_output=True,cwd=ROOT,timeout=20)
        self.assertEqual(process.returncode,2);self.assertIn('Unknown project',process.stderr);self.assertNotIn('Traceback',process.stderr)

    def test_build_tempdir_executes_examples_and_produces_self_contained_sourcezip(self):
        with tempfile.TemporaryDirectory() as directory:
            destination=Path(directory)/'site';text,_=self.cli(['build','--output',str(destination)])
            self.assertIn(f"Built {len(INSTALLED)} runnable project(s)",text)
            catalog=json.loads((destination/'catalog.json').read_text())
            self.assertEqual({entry['id'] for entry in catalog['projects']},set(INSTALLED))
            self.assertTrue((destination/'.nojekyll').exists());self.assertTrue((destination/'index.html').exists())
            for item in catalog['projects']:
                self.assertTrue(item['examples'])
                for example in item['examples']:
                    self.assertEqual(example['report']['provenance']['mode'],'local')
                    self.assertEqual(example['report']['provenance']['project_id'],item['id'])
                    self.assertIsInstance(example['payload'],dict)
            with zipfile.ZipFile(destination/'application.zip') as archive:
                names=archive.namelist();self.assertIn('portfolio/runtime.py',names)
                self.assertFalse(any('__pycache__' in name or name.endswith(('.pyc','.pyo')) for name in names))
                for identity in INSTALLED:self.assertIn(f'projects/{identity}/project.py',names)
                self.assertTrue(all(not name.startswith('/') and '..' not in Path(name).parts for name in names))
                unpacked=Path(directory)/'unpacked';archive.extractall(unpacked)
            env=dict(os.environ);env.pop('PYTHONPATH',None)
            process=subprocess.run([sys.executable,'-m','portfolio','run',PROJECT_ID],cwd=unpacked,env=env,text=True,capture_output=True,timeout=30)
            self.assertEqual(process.returncode,0,process.stderr);self.assertEqual(json.loads(process.stdout)['provenance']['project_id'],PROJECT_ID)

    def test_builder_default_scenario_and_directory_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'web'/'assets').mkdir(parents=True);(root/'web'/'index.html').write_text('test');(root/'web'/'assets'/'asset.txt').write_text('copied');(root/'portfolio').mkdir();(root/'projects').mkdir();(root/'portfolio'/'runtime.py').write_text('x=1');(root/'portfolio'/'skip.pyc').write_bytes(b'compiled');(root/'portfolio'/'__pycache__').mkdir();(root/'portfolio'/'__pycache__'/'hidden.py').write_text('excluded')
            fake=SimpleNamespace(META={'id':PROJECT_ID,'title':'Synthetic temporary build','order':1},default_input=lambda:{'sample':True})
            with patch.object(builder,'ROOT',root),patch.object(builder,'projects',return_value={PROJECT_ID:fake}),patch.object(builder,'execute',return_value=report()):data=builder.build()
            self.assertEqual(data['projects'][0]['examples'][0]['label'],'Sample scenario')
            self.assertEqual(data['projects'][0]['examples'][0]['payload'],{'sample':True})
            self.assertEqual((root/'dist'/'assets'/'asset.txt').read_text(),'copied')
            with zipfile.ZipFile(root/'dist'/'application.zip') as archive:self.assertEqual(archive.namelist(),['portfolio/runtime.py'])

    def test_cli_serve_and_mcp_dispatch_without_blocking(self):
        with patch('portfolio.build.build',return_value={'projects':[]}) as build,patch('portfolio.server.serve') as serve:self.cli(['serve','--port','0','--mode','local'])
        build.assert_called_once_with(None);serve.assert_called_once_with(0,'local')
        with patch('portfolio.mcp.main') as run:self.cli(['mcp'])
        run.assert_called_once_with()


if __name__=='__main__':unittest.main()

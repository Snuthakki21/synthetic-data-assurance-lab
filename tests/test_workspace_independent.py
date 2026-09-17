"""Independent Staff Engineer review: transactional and API boundary regressions."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
import threading

from app.platform.api import WorkspaceAPI
from app.platform.errors import Conflict
from app.platform.repository import SQLiteWorkspaceRepository
from app.platform.service import WorkspaceService
from app.platform.models import digest


def _report(payload):
    return {'summary':'Original review fixture','metrics':[{'label':'Value','value':payload.get('n',1),'unit':'items'}], 'details':{}, 'evidence':[], 'next_actions':[]}


class IndependentWorkspaceReview(TestCase):
    def setUp(self):
        self.directory=TemporaryDirectory()
        self.repository=SQLiteWorkspaceRepository(Path(self.directory.name)/'review.sqlite')
        self.calls=[]
        def execute(project_id,payload,mode):
            self.calls.append(payload)
            return _report(payload)
        self.service=WorkspaceService(self.repository,execute,lambda:{'product':SimpleNamespace(default_input=lambda:{'n':1})})
        self.api=WorkspaceAPI(self.service)

    def tearDown(self):
        self.directory.cleanup()

    def test_archive_between_service_read_and_reservation_prevents_execution(self):
        scenario=self.service.save_scenario('product','Scenario',{'n':1})
        reserve=self.repository.reserve_execution
        def archive_before_reserve(*args,**kwargs):
            self.repository.archive_scenario(scenario.scenario_id,1,True)
            return reserve(*args,**kwargs)
        with patch.object(self.repository,'reserve_execution',archive_before_reserve):
            with self.assertRaises(Conflict):
                self.service.execute('product',scenario_id=scenario.scenario_id,scenario_version=1)
        self.assertEqual(self.calls,[])
        self.assertEqual(self.repository.diagnostics()['executions'],0)

    def test_malformed_scenario_identity_is_a_client_error(self):
        for invalid in [[],{},True,42]:
            with self.subTest(identity=invalid):
                status,_=self.api.dispatch('POST','/api/v1/executions',{'project_id':'product','scenario_id':invalid,'scenario_version':1})
                self.assertEqual(status,400)
        self.assertEqual(self.calls,[])

    def test_parallel_review_has_one_cas_winner_and_preserves_report_hash(self):
        run=self.service.execute('product',{'n':5})
        barrier=threading.Barrier(2)
        def decide(decision):
            barrier.wait()
            try:
                self.repository.review_execution(run.run_id,decision,'Reviewer','Reviewed exact execution evidence',0)
                return 'success'
            except Conflict:
                return 'conflict'
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(decide,['approved','rejected']))
        self.assertEqual(sorted(outcomes),['conflict','success'])
        reviews=[event for event in self.repository.audit_events() if event['kind']=='execution.reviewed']
        self.assertEqual(len(reviews),1)
        self.assertEqual(reviews[0]['details']['report_sha256'],digest(run.report))
        self.assertTrue(self.repository.verify_audit()['valid'])

    def test_idempotency_key_pins_payload_mode_and_scenario_revision(self):
        scenario=self.service.save_scenario('product','Scenario',{'n':1})
        first=self.service.execute('product',scenario_id=scenario.scenario_id,scenario_version=1,idempotency_key='review-idempotency')
        self.repository.save_scenario('product','Scenario',{'n':2},scenario.scenario_id,1)
        with self.assertRaises(Conflict):
            self.service.execute('product',scenario_id=scenario.scenario_id,scenario_version=2,idempotency_key='review-idempotency')
        again=self.service.execute('product',scenario_id=scenario.scenario_id,scenario_version=1,idempotency_key='review-idempotency')
        self.assertEqual(again.run_id,first.run_id)
        self.assertEqual(len(self.calls),1)

    def test_failed_review_does_not_write_audit_or_state(self):
        run=self.service.execute('product',{'n':1})
        count=self.repository.diagnostics()['audit_events']
        with self.assertRaises(Conflict):
            self.repository.review_execution(run.run_id,'not_a_decision','Reviewer','Must not be accepted',0)
        current=self.repository.get_execution(run.run_id)
        self.assertEqual(current.review_version,0)
        self.assertEqual(current.review_status,'unreviewed')
        self.assertEqual(self.repository.diagnostics()['audit_events'],count)

    def test_archived_scenario_history_is_retained_and_reproducible_after_restore(self):
        scenario=self.service.save_scenario('product','Scenario',{'n':1})
        self.repository.archive_scenario(scenario.scenario_id,1)
        self.assertEqual(self.repository.get_scenario(scenario.scenario_id,1).payload,{'n':1})
        self.repository.archive_scenario(scenario.scenario_id,1,False)
        run=self.service.execute('product',scenario_id=scenario.scenario_id,scenario_version=1)
        self.assertEqual(run.payload,{'n':1})


class IndependentHTTPReview(TestCase):
    def setUp(self):
        import threading
        from app.platform.config import WorkspaceSettings
        from app.platform.http_server import create_server
        self.directory=TemporaryDirectory()
        root=Path(self.directory.name);self.static=root/'static';self.static.mkdir()
        (self.static/'index.html').write_text('<!doctype html><title>Review fixture</title>')
        (root/'private.txt').write_text('Private fixture must remain outside static boundary')
        (self.static/'outside.txt').symlink_to(root/'private.txt')
        repository=SQLiteWorkspaceRepository(root/'db.sqlite')
        service=WorkspaceService(repository,lambda pid,payload,mode:_report(payload),lambda:{'product':SimpleNamespace(default_input=lambda:{})})
        self.token='review-token-'+'x'*40
        self.server=create_server(self.static,service,WorkspaceSettings(port=0,access_token=self.token))
        self.thread=threading.Thread(target=self.server.serve_forever,kwargs={'poll_interval':.01},daemon=True);self.thread.start()

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(3);self.directory.cleanup()

    def request(self,path,method='GET',body=None,headers=None):
        import http.client,json
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
        fields={'Authorization':'Bearer '+self.token,'Content-Type':'application/json'};fields.update(headers or {})
        connection.request(method,path,body=json.dumps(body) if body is not None else None,headers=fields)
        response=connection.getresponse();data=response.read();status=response.status;response_headers=dict(response.getheaders());connection.close()
        return status,data,response_headers

    def test_head_cannot_reveal_out_of_root_symlink_metadata(self):
        self.assertEqual(self.request('/outside.txt','HEAD')[0],404)

    def test_http_invalid_identity_is_bounded_and_server_remains_usable(self):
        status,body,_=self.request('/api/v1/executions','POST',{'project_id':'product','scenario_id':[],'scenario_version':1})
        self.assertEqual(status,400)
        self.assertNotIn(b'Traceback',body)
        self.assertEqual(self.request('/api/v1/diagnostics')[0],200)

    def test_get_api_rejects_cross_origin_and_wrong_token(self):
        self.assertEqual(self.request('/api/v1/audit',headers={'Origin':'https://untrusted.invalid'})[0],403)
        self.assertEqual(self.request('/api/v1/audit',headers={'Authorization':'Bearer wrong'})[0],401)
        self.assertEqual(self.request('/api/v1/audit',headers={'Host':'untrusted.invalid'})[0],403)


class IndependentComparisonReview(TestCase):
    def test_duplicate_metric_suffix_does_not_overwrite_a_real_label(self):
        from app.platform.comparison import RunComparisonService
        from app.platform.models import ExecutionRecord
        metrics=[{'label':'Amount','value':'1','unit':'USD'},{'label':'Amount [3]','value':'2','unit':'USD'},{'label':'Amount','value':'3','unit':'USD'}]
        report={'summary':'Result','metrics':metrics}
        def record(identifier):
            return ExecutionRecord(identifier,'product','succeeded',{},'2026-01-01','2026-01-01',report,None,None,None,'local','unreviewed',0)
        self.assertEqual(len(RunComparisonService().compare(record('a'),record('b'))['metrics']),3)


class IndependentBackupReview(TestCase):
    def test_backup_preserves_revisions_runs_and_audit_without_overwrite(self):
        from app.platform.cli import workspace_command
        with TemporaryDirectory() as directory:
            source=Path(directory)/'source.sqlite';target=Path(directory)/'backups'/'snapshot.sqlite'
            repository=SQLiteWorkspaceRepository(source)
            scenario=repository.save_scenario('product','Baseline',{'n':1})
            repository.save_scenario('product','Candidate',{'n':2},scenario.scenario_id,1)
            execution,_=repository.reserve_execution('product',{'n':2},scenario_id=scenario.scenario_id,scenario_version=2)
            repository.finish_execution(execution.run_id,_report({'n':2}))
            before=repository.verify_audit()
            workspace_command(source,'backup',output=target)
            copied=SQLiteWorkspaceRepository(target)
            self.assertEqual(copied.get_scenario(scenario.scenario_id,1).payload,{'n':1})
            self.assertEqual(copied.get_execution(execution.run_id).status,'succeeded')
            self.assertEqual(copied.verify_audit(),before)
            with self.assertRaises(FileExistsError):workspace_command(source,'backup',output=target)
            self.assertEqual(copied.verify_audit(),before)

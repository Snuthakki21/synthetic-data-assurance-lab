import test from 'node:test';
import assert from 'node:assert/strict';
import {BrowserWorkspaceRepository} from '../web/workspace/repository.js';
import {MemoryStateStorage} from '../web/workspace/storage.js';
import {NativeWorkspaceClient} from '../web/workspace/client.js';
import {canonical,compareRuns,numericDelta,validateInput} from '../web/workspace/contracts.js';
import {applyField} from '../web/ui.js';
function setup(){let seq=0;const store=new MemoryStateStorage();return {store,repo:new BrowserWorkspaceRepository('product',store,()=>new Date(1700000000000+seq++).toISOString(),()=>`id-${seq++}`)};}
const report=(value='0.20')=>({summary:'Computed',metrics:[{label:'Cash',value,unit:'USD'}],details:{},evidence:[],next_actions:[]});
test('scenario revision is immutable, detached, optimistic and preserved by archive',async()=>{
 const {repo}=setup(),input={n:1};const first=await repo.saveScenario('Case',input);input.n=9;first.payload.n=10;
 assert.equal((await repo.getScenario(first.scenario_id)).payload.n,1);
 const second=await repo.saveScenario('Case 2',{n:2},first.scenario_id,1);
 await assert.rejects(repo.saveScenario('Stale',{n:3},first.scenario_id,1),/changed/);
 assert.equal((await repo.getScenario(first.scenario_id,1)).payload.n,1);
 await repo.archiveScenario(first.scenario_id,2);assert.equal((await repo.listScenarios()).length,0);
 await assert.rejects(repo.saveScenario('New',{n:3},first.scenario_id,2),/archived/);
 await repo.archiveScenario(first.scenario_id,2,false);assert.equal((await repo.listScenarios()).length,1);assert.equal(second.version,2);
});
test('failed transaction leaves revision and audit unchanged',async()=>{
 const {repo,store}=setup();await repo.saveScenario('Initial',{n:1});const prior=await store.read();
 await assert.rejects(store.update(state=>{state.audit.push({wrong:true});throw new Error('abort');}),/abort/);
 assert.deepEqual(await store.read(),prior);
 for(const id of ['__proto__','constructor','missing']){await assert.rejects(repo.getScenario(id),/not found/);await assert.rejects(repo.getRun(id),/not found/);}
 await assert.rejects(repo.saveScenario('New',{},null,1));
});
test('concurrent revisions have exactly one winner and no lost update',async()=>{
 const {repo}=setup(),first=await repo.saveScenario('First',{n:1});
 const results=await Promise.allSettled([repo.saveScenario('A',{n:2},first.scenario_id,1),repo.saveScenario('B',{n:3},first.scenario_id,1)]);
 assert.equal(results.filter(r=>r.status==='fulfilled').length,1);assert.equal((await repo.getScenario(first.scenario_id)).version,2);
});
test('run review is revisioned and evidence remains exact',async()=>{
 const {repo}=setup();const run=await repo.recordRun({n:1},report());run.report.summary='mutated';
 assert.equal((await repo.getRun(run.run_id)).report.summary,'Computed');
 const approved=await repo.reviewRun(run.run_id,'approved','Operator','Evidence checked',0);assert.equal(approved.review_version,1);
 await assert.rejects(repo.reviewRun(run.run_id,'rejected','Other','Stale review',0),/changed/);
 await assert.rejects(repo.reviewRun(run.run_id,'rejected','Other','Invalid transition',1),/transition/);
 await repo.reviewRun(run.run_id,'needs_changes','Operator','Assumption requires review',1);
 const failed=await repo.recordRun({n:0},null,'Invalid domain value');await assert.rejects(repo.reviewRun(failed.run_id,'approved','Operator','Invalid',0),/successful/);
 assert.equal((await repo.listRuns()).length,2);assert.equal((await repo.diagnostics()).executions,2);assert.equal((await repo.audit()).filter(e=>e.kind==='execution.reviewed').length,2);
});
test('saved revision binding rejects changed or archived evidence',async()=>{
 const {repo}=setup(),scenario=await repo.saveScenario('Bound',{n:1});
 const run=await repo.recordRun({n:1},report(),null,scenario);assert.equal(run.scenario_version,1);
 await assert.rejects(repo.recordRun({n:2},report(),null,scenario),/does not match/);
 await repo.archiveScenario(scenario.scenario_id,1);await assert.rejects(repo.recordRun({n:1},report(),null,scenario),/does not match/);
});
test('comparison preserves decimal precision, changed types, missing metrics and unit boundaries',async()=>{
 const {repo}=setup();const a=await repo.recordRun({n:true,removed:1},report('0.10')),b=await repo.recordRun({n:1,added:2},report('0.30'));
 const result=await repo.compare(a.run_id,b.run_id);assert.equal(result.metrics[0].numeric_delta,'0.2');assert.equal(result.input_changes.length,3);
 assert.equal(numericDelta('999999999999999999.01','999999999999999999.03'),'0.02');assert.equal(numericDelta('1e-8','3e-8'),'0.00000002');assert.equal(numericDelta(true,1),null);
 b.report.metrics[0].unit='EUR';assert.equal(compareRuns(a,b).metrics[0].numeric_delta,null);
 b.project_id='different';assert.throws(()=>compareRuns(a,b),/same application/);
});
test('complete browser export includes prior revisions, failed runs and audit',async()=>{
 const {repo}=setup();const first=await repo.saveScenario('Before',{});await repo.saveScenario('After',{n:1},first.scenario_id,1);await repo.recordRun({},null,'Failed validation');
 const result=await repo.exportWorkspace();assert.equal(result.revisions[first.scenario_id].length,2);assert.equal(Object.keys(result.executions).length,1);assert.equal(result.audit.length,3);
});
test('JSON trust boundary rejects nonfinite, oversize and malformed inputs',async()=>{
 const {repo}=setup();for(const input of [null,[],{n:Infinity},{n:undefined},{text:'x'.repeat(262144)}])assert.throws(()=>validateInput(input));
 assert.equal(canonical({z:2,a:1}),'{"a":1,"z":2}');await assert.rejects(repo.recordRun({},report(),'both'));await assert.rejects(repo.recordRun({},null,''));
 await assert.rejects(repo.saveScenario(' ',{}));await assert.rejects(repo.saveScenario('Case',{} ,'missing',0));
});
test('native API sends token only in authorization header and carries exact revision and abort signal',async()=>{
 const calls=[],client=new NativeWorkspaceClient('product',async(url,options)=>{calls.push({url,options});return {ok:true,json:async()=>({items:[],storage:'SQLite'})};});
 client.setToken('secret');const signal=new AbortController().signal;await client.execute({n:1},signal,{scenario_id:'saved',version:3});
 const call=calls.at(-1);assert.equal(call.url,'/api/v1/executions');assert.equal(call.options.headers.Authorization,'Bearer secret');assert.equal(call.options.signal,signal);const body=JSON.parse(call.options.body);assert.equal(body.scenario_version,3);assert.ok(body.idempotency_key);assert.ok(!call.options.body.includes('secret'));
 client.setToken(null);await client.getRun('a/b');assert.equal(calls.at(-1).url,'/api/v1/executions/a%2Fb');assert.equal(calls.at(-1).options.headers.Authorization,undefined);
 const failed=new NativeWorkspaceClient('product',async()=>({ok:false,status:409,json:async()=>({error:'Reload revision'})}));await assert.rejects(failed.diagnostics(),/Reload revision/);
});
test('optional controls create missing objects while preserving prototype guards and numeric validation',()=>{
 const input={};applyField(input,'experiment.iterations','20','number');assert.deepEqual(input,{experiment:{iterations:20}});
 for(const path of ['__proto__.x','experiment.constructor.x','empty..x'])assert.throws(()=>applyField(input,path,1,'number'));
 assert.throws(()=>applyField(input,'new.x','NaN','number'));assert.ok(!Object.hasOwn(input,'new'));
 assert.throws(()=>applyField({experiment:[]},'experiment.x',1,'number'));
});

test('native browser fetch transport is called without a client receiver',async()=>{
 const client=new NativeWorkspaceClient('product',function(){assert.equal(this,undefined);return Promise.resolve({ok:true,json:async()=>({storage:'SQLite'})});});
 assert.equal((await client.diagnostics()).storage,'SQLite');
});

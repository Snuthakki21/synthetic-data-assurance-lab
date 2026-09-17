// Independent Staff Engineer tests. No browser automation or production services.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import {webcrypto} from 'node:crypto';
import {applyField, esc, field, numeric, percent, table, bars} from '../web/ui.js';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const catalog = JSON.parse(fs.readFileSync(path.join(root, 'dist/catalog.json'), 'utf8'));
const views = new Map();
for (const project of catalog.projects) views.set(project.id, (await import(`../web/templates/${project.id}.js`)).default);
const copy = value => structuredClone(value);
const marker = `<img src=x onerror="alert('x')"><script>untrusted()</script>&`;
const decode = value => String(value).replace(/&quot;/g,'"').replace(/&#39;/g,"'").replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&amp;/g,'&');
function attributes(tag) { return Object.fromEntries([...tag.matchAll(/([\w-]+)="([^"]*)"/g)].map(([,key,value])=>[key,decode(value)])); }
function controls(html) { return [...html.matchAll(/<(input|textarea|select)\b[^>]*>/g)].map(match=>({tag:match[0],kind:match[1],...attributes(match[0])})).filter(item=>item['data-path']); }
function valueAt(payload, key) { return key.split('.').reduce((value,part)=>value?.[part],payload); }
function poisonStrings(value) { if(typeof value==='string')return marker; if(Array.isArray(value))return value.map(poisonStrings);if(value&&typeof value==='object')return Object.fromEntries(Object.entries(value).map(([key,item])=>[key,poisonStrings(item)]));return value; }
function maybeProject(id,t) {const project=catalog.projects.find(p=>p.id===id);if(!project)t.skip('Project is absent from this standalone build');return project;}
function runPythonInputs(cases) {
 const script=`import importlib,json,sys\nitems=json.load(sys.stdin)\nresults=[]\nfor item in items:\n try:\n  m=importlib.import_module('projects.'+item['id']+'.project')\n  m.run(item['payload'])\n  results.append({'id':item['id'],'field':item.get('field'),'ok':True})\n except Exception as e:\n  results.append({'id':item['id'],'field':item.get('field'),'ok':False,'error':type(e).__name__+': '+str(e)})\nprint(json.dumps(results))\n`;
 const result=spawnSync(process.env.PYTHON||'python3',['-c',script],{cwd:root,input:JSON.stringify(cases),encoding:'utf8',maxBuffer:4*1024*1024});
 assert.equal(result.status,0,result.stderr||String(result.error));return JSON.parse(result.stdout);
}

test('every built application has its own layout, named controls and examples',()=>{
 assert.ok(catalog.projects.length>0);assert.equal(new Set(catalog.projects.map(p=>p.id)).size,catalog.projects.length);
 const layouts=[];
 for(const p of catalog.projects){const view=views.get(p.id);layouts.push(view.layout);for(const key of ['layout','label','action','controlsTitle'])assert.ok(typeof view[key]==='string'&&view[key],`${p.id}: ${key}`);assert.ok(p.examples.length>0);}
 assert.equal(new Set(layouts).size,layouts.length,'Layouts must be distinct, not a reused aggregate dashboard');
});
for(const p of catalog.projects){
 test(`${p.id}: every executed example renders controls and results`,()=>{
  const view=views.get(p.id);
  for(const example of p.examples){for(const [section,value] of [['controls',example.payload],['result',example.report]]){
   const html=view[section](copy(value));assert.ok(typeof html==='string'&&html.length>100,example.label);assert.doesNotMatch(html,/\b(?:undefined|NaN)\b/,`${example.label}: ${section}`);
   const ids=[...html.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]);assert.equal(new Set(ids).size,ids.length,`${example.label}: duplicate element IDs`);
  }}
 });
 test(`${p.id}: untrusted report strings and text fields cannot become markup`,()=>{
  const view=views.get(p.id);const html=view.result(poisonStrings(copy(p.examples[0].report)));
  assert.ok(!html.includes('<img src=x')&&!html.includes('<script>'),'Report text must be escaped');
  for(const control of controls(view.controls(copy(p.examples[0].payload)))){
   if(['text','textarea','date'].includes(control['data-value-type'])){
    const payload=copy(p.examples[0].payload);applyField(payload,control['data-path'],marker,control['data-value-type']);
    const output=view.controls(payload);assert.ok(!output.includes('<img src=x')&&!output.includes('<script>'),control['data-path']);
   }
  }
 });
}

test('presentation helpers escape content and do not invent missing metrics',()=>{
 assert.equal(esc('<>&"\''),'&lt;&gt;&amp;&quot;&#39;');
 for(const missing of [null,undefined,'',NaN,Infinity]){assert.equal(numeric(missing),'Unavailable');assert.equal(percent(missing),'Unavailable');}
 assert.equal(numeric(0),'0');assert.equal(percent(0),'0%');assert.equal(numeric('0.10'),'0.1');
 for(const html of [field('safe',marker,marker,{type:'textarea'}),table(marker,[{value:marker}],[['value',marker]]),bars(marker,[{name:marker,value:1}],'name','value',marker)])assert.ok(!html.includes('<img src=x')&&!html.includes('<script>'));
});
test('applyField performs supported type conversions without touching unrelated data',()=>{
 const payload={amount:'0.10',count:1,enabled:true,regions:[],nested:{value:4},untouched:{tag:'keep'}};
 applyField(payload,'amount','0.20','text');applyField(payload,'count','5','number');applyField(payload,'enabled',false,'checkbox');applyField(payload,'regions','east, central, ,west','list');applyField(payload,'nested.value','7','number');
 assert.deepEqual(payload,{amount:'0.20',count:5,enabled:false,regions:['east','central','west'],nested:{value:7},untouched:{tag:'keep'}});
 for(const value of ['', 'Infinity', 'NaN', 'not a number'])assert.throws(()=>applyField(payload,'count',value,'number'));
 assert.equal(payload.count,5);applyField(payload,'missing.child',1,'number');assert.equal(payload.missing.child,1);assert.throws(()=>applyField(payload,'count.child',1,'number'));assert.throws(()=>applyField(payload,'missing..child',1,'number'));
});
test('applyField rejects prototype pollution paths before mutation',()=>{
 const payload={nested:{value:1}};
 for(const key of ['__proto__.polluted','constructor.prototype.polluted','nested.__proto__.polluted','nested.constructor.polluted','prototype.polluted'])assert.throws(()=>applyField(payload,key,'yes','text'),key);
 assert.equal(Object.prototype.polluted,undefined);assert.deepEqual(payload,{nested:{value:1}});
});
test('every rendered control binds to a project input path accepted by Python',()=>{
 const cases=[];
 for(const p of catalog.projects){
  const base=p.examples[0].payload;
  for(const control of controls(views.get(p.id).controls(copy(base)))){
   const key=control['data-path'],kind=control['data-value-type'];let value=valueAt(base,key);
   assert.ok(value!==undefined||key.startsWith('thresholds.'),`${p.id}: unmapped path ${key}`);
   if(value===undefined)value=control.value;
   if(kind==='list')value=value.join(', ');else if(kind!=='checkbox'&&kind!=='boolean')value=String(value);
   const payload=copy(base);applyField(payload,key,value,kind);cases.push({id:p.id,field:key,payload});
  }
 }
 const results=runPythonInputs(cases);assert.equal(results.length,cases.length);assert.deepEqual(results.filter(r=>!r.ok),[]);
});
test('advertised scalar control minima are valid backend values',()=>{
 const paths={fraud_investigation_workbench:['review_threshold'],governed_analytics:['minimum_group_size'],data_contract_observatory:['contract.psi_threshold'],inference_cost_lab:['budget_usd','minimum_expected_quality']};const cases=[];
 for(const p of catalog.projects){for(const control of controls(views.get(p.id).controls(copy(p.examples[0].payload))))if(paths[p.id]?.includes(control['data-path'])){assert.ok(control.min!==undefined);const payload=copy(p.examples[0].payload);applyField(payload,control['data-path'],control.min,control['data-value-type']);cases.push({id:p.id,field:control['data-path'],payload});}}
 assert.deepEqual(runPythonInputs(cases).filter(r=>!r.ok),[]);
});
test('data quality displays unavailable drift as insufficient evidence',t=>{
 const p=maybeProject('data_contract_observatory',t);if(!p)return;const report=copy(p.examples[0].report);report.details.drift={missing_field:{status:'insufficient_data',baseline_n:60,current_n:0}};
 const html=views.get(p.id).result(report);assert.match(html,/Insufficient data/i);assert.doesNotMatch(html,/Within threshold/);
});
test('liquidity displays an opening breach as day zero',t=>{
 const p=maybeProject('liquidity_stress_lab',t);if(!p)return;const report=copy(p.examples[0].report);report.details.stress.first_floor_breach_by_day=0;report.details.stress.survived_through_day=0;
 const html=views.get(p.id).result(report);assert.match(html,/By day 0|Day 0|day zero/i);assert.doesNotMatch(html,/None in horizon/);
});
test('incident ledger displays the returned revision field',t=>{
 const p=maybeProject('incident_command',t);if(!p)return;const report=copy(p.examples[0].report);report.details.action_ledger=[{action:'rollback_release',status:'simulated',revision:'review-revision-123'}];
 assert.match(views.get(p.id).result(report),/review-revision-123/);
});
test('fraud dispositions match every supported state transition',t=>{
 const p=maybeProject('fraud_investigation_workbench',t);if(!p)return;const transitions={new:['triaged'],triaged:['investigating','closed_no_issue'],investigating:['escalated','closed_no_issue'],escalated:[],closed_no_issue:[]};
 for(const [state,expected]of Object.entries(transitions)){
  const report=copy(p.examples[0].report);for(const key of Object.keys(report.details.case_states))report.details.case_states[key]=state;
  const html=views.get(p.id).result(report);const selects=[...html.matchAll(/<select\s+data-disposition="[^"]+">([\s\S]*?)<\/select>/g)];assert.ok(selects.length>0);
  for(const [,body]of selects){const options=[...body.matchAll(/<option value="([^"]*)"/g)].map(x=>x[1]).filter(Boolean);assert.deepEqual(options,expected,state);}
 }
});

function deferred(){let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return {promise,resolve,reject};}
function harness(){
 const elements=new Map();const downloads=[];let blob;
 const element=id=>{if(!elements.has(id))elements.set(id,{value:'',innerHTML:'',textContent:'',hidden:false,disabled:false,dataset:{},focus(){},getAttribute(name){return this[name];}});return elements.get(id);};
 const document={querySelector(selector){return element(selector);},querySelectorAll(){return [];},createElement(){const anchor={click(){downloads.push({href:this.href,name:this.download});}};return anchor;},documentElement:{dataset:{}},body:{dataset:{}}};
 const timers=new Map();let nextTimer=0;
 const sandbox={document,console,TextEncoder,AbortController,Blob,crypto:webcrypto,URL:{createObjectURL(value){blob=value;return 'blob:test';},revokeObjectURL(){}},setTimeout(fn){timers.set(++nextTimer,fn);return nextTimer;},clearTimeout(id){timers.delete(id);},window:{scrollTo(){},addEventListener(){}},location:{hash:'',hostname:'example.test'},matchMedia:()=>({matches:false}),fetch:()=>{throw new Error('Unexpected network call in test');},applyField};
 const source=fs.readFileSync(path.join(root,'web/app.js'),'utf8').replace(/^import[^\n]*\n/gm,'').replace(/\ninit\(\);\s*$/,'\n');
 const exposure=`\nglobalThis.appTest={renderReport,downloadReport,cancelRun,runScenario,loadInputFile,restoreExample,runOperation,setState(value){if('current'in value)current=value.current;if('currentReport'in value)currentReport=value.currentReport;if('design'in value)design=value.design;if('renderedPayload'in value)renderedPayload=value.renderedPayload;if('serverMode'in value)serverMode=value.serverMode;},getState(){return {current,currentReport,renderedPayload,runSerial};}};`;
 vm.createContext(sandbox);new vm.Script(source+exposure,{filename:'web/app.js (test harness)'}).runInContext(sandbox);
 const old={summary:'Previous accepted report',evidence:['Original evidence'],next_actions:['Review'],details:{rows:Array.from({length:25},(_,i)=>({id:i,text:'row '+i}))}},payload={marker:'original'};
 const project={id:'test_app',examples:[{payload,report:old}]};
 sandbox.appTest.setState({current:project,currentReport:old,renderedPayload:JSON.stringify(payload),serverMode:'local',design:{result:report=>`<article>${esc(report.summary)}</article>`,controls:()=>'<p>controls</p>'}});
 element('#input').value=JSON.stringify(payload);element('#report').innerHTML='Previous visible report';
 return {api:sandbox.appTest,sandbox,element,old,payload,downloads,timers,get blob(){return blob;}};
}
test('render failures preserve the accepted report and downloadable evidence',async()=>{
 const h=harness();h.api.setState({design:{result(){throw new Error('Render failed');}}});assert.throws(()=>h.api.renderReport({...h.old,summary:'Unrenderable new report'},true));
 assert.equal(h.api.getState().currentReport,h.old);assert.equal(h.element('#report').innerHTML,'Previous visible report');
 h.api.downloadReport();assert.deepEqual(JSON.parse(await h.blob.text()),h.old);assert.equal(h.downloads[0].name,'test_app-report.json');
});
test('downloads include all evidence rows, including rows omitted from the preview',async()=>{
 const h=harness();h.api.renderReport(h.old);h.api.downloadReport();const output=JSON.parse(await h.blob.text());assert.equal(output.details.rows.length,25);assert.equal(output.details.rows[24].id,24);
});
test('a cancelled server response cannot replace the accepted report',async()=>{
 const h=harness(),response=deferred();h.sandbox.fetch=()=>response.promise;const running=h.api.runScenario();h.api.cancelRun();
 response.resolve({ok:true,json:async()=>({...h.old,summary:'Late cancelled result'})});await running;
 assert.equal(h.api.getState().currentReport,h.old);assert.equal(h.element('#report').innerHTML,'Previous visible report');assert.equal(h.element('#run').disabled,false);
});
test('in-flight file import cannot overwrite a newer run input',async()=>{
 const h=harness(),fileRead=deferred(),response=deferred();h.sandbox.fetch=()=>response.promise;
 const importing=h.api.loadInputFile({target:{files:[{size:30,text:()=>fileRead.promise}]}});const running=h.api.runScenario();
 fileRead.resolve('{"marker":"stale file"}');await importing;assert.equal(h.element('#input').value,JSON.stringify(h.payload));
 response.resolve({ok:true,json:async()=>h.old});await running;assert.equal(h.api.getState().renderedPayload,JSON.stringify(h.payload));
});
test('newer file imports supersede earlier deferred reads',async()=>{
 const h=harness(),slow=deferred();const first=h.api.loadInputFile({target:{files:[{size:20,text:()=>slow.promise}]}});
 await h.api.loadInputFile({target:{files:[{size:20,text:async()=>'{"marker":"newest"}'}]}});slow.resolve('{"marker":"older"}');await first;
 assert.equal(JSON.parse(h.element('#input').value).marker,'newest');
});
test('restoring a sample supersedes an older deferred file read',async()=>{
 const h=harness(),slow=deferred();const reading=h.api.loadInputFile({target:{files:[{size:20,text:()=>slow.promise}]}});h.api.restoreExample();slow.resolve('{"marker":"older"}');await reading;
 assert.deepEqual(JSON.parse(h.element('#input').value),h.payload);
});
test('review operations reject changed input before any run',async()=>{
 const h=harness();h.element('#input').value='{"marker":"changed"}';await h.api.runOperation({dataset:{operation:'incident-approve'}});
 assert.match(h.element('#error').textContent,/Run the changed input/);assert.equal(h.api.getState().currentReport,h.old);
});
test('report provenance uses the submitted snapshot rather than a later editor value',async()=>{
 const h=harness(),response=deferred();h.sandbox.fetch=()=>response.promise;const running=h.api.runScenario();h.element('#input').value='{"marker":"later edit"}';response.resolve({ok:true,json:async()=>h.old});await running;
 assert.equal(h.api.getState().renderedPayload,JSON.stringify(h.payload));
});

function fakeWorker(h){
 const instances=[];h.sandbox.Worker=class{constructor(url,options){this.url=url;this.options=options;instances.push(this);}postMessage(request){this.request=request;}terminate(){this.terminated=true;}};
 h.api.setState({serverMode:null});return instances;
}
test('cancelling browser execution terminates the worker and retains accepted evidence',async()=>{
 const h=harness(),workers=fakeWorker(h),running=h.api.runScenario();assert.equal(workers[0].url,'worker.js');assert.deepEqual(JSON.parse(JSON.stringify(workers[0].request)),{project_id:'test_app',payload:h.payload});
 h.api.cancelRun();await running;assert.equal(workers[0].terminated,true);assert.equal(h.api.getState().currentReport,h.old);assert.equal(h.element('#run').disabled,false);assert.equal(h.timers.size,0);
});
test('browser execution timeout terminates the worker and returns an actionable error',async()=>{
 const h=harness(),workers=fakeWorker(h),running=h.api.runScenario();[...h.timers.values()][0]();await running;
 assert.equal(workers[0].terminated,true);assert.match(h.element('#error').textContent,/exceeded two minutes/);assert.equal(h.api.getState().currentReport,h.old);assert.equal(h.element('#run').disabled,false);
});
test('browser engine load failure preserves previous evidence and allows recovery',async()=>{
 const h=harness(),workers=fakeWorker(h),running=h.api.runScenario();workers[0].onerror();await running;
 assert.equal(workers[0].terminated,true);assert.match(h.element('#error').textContent,/could not start/);assert.equal(h.api.getState().currentReport,h.old);
 const retry=h.api.runScenario();assert.equal(workers.length,2);workers[1].onmessage({data:{report:{...h.old,summary:'Recovered result'}}});await retry;
 assert.equal(h.api.getState().currentReport.summary,'Recovered result');assert.equal(h.element('#run').disabled,false);
});
test('a pending file import cannot overwrite a newer manual edit',async()=>{
 const h=harness(),slow=deferred();const reading=h.api.loadInputFile({target:{files:[{size:20,text:()=>slow.promise}]}});
 h.element('#input').value='{"marker":"newer edit"}';slow.resolve('{"marker":"older file"}');await reading;
 assert.equal(JSON.parse(h.element('#input').value).marker,'newer edit');
});
test('invalid and oversized input files preserve the previous editable input',async()=>{
 for(const file of [{size:300000,text:async()=>'{"unused":true}'},{size:2,text:async()=>'[]'},{size:4,text:async()=>'null'},{size:7,text:async()=>'{broken'}]){
  const h=harness(),before=h.element('#input').value;await h.api.loadInputFile({target:{files:[file]}});
  assert.equal(h.element('#input').value,before);assert.equal(h.element('#error').hidden,false);assert.equal(h.api.getState().currentReport,h.old);
 }
});
test('rejected server results preserve downloadable evidence and re-enable controls',async()=>{
 const h=harness();h.sandbox.fetch=async()=>({ok:false,json:async()=>({error:'Scenario was rejected'})});await h.api.runScenario();
 assert.equal(h.api.getState().currentReport,h.old);assert.equal(h.element('#run').disabled,false);assert.equal(h.element('#error').textContent,'Scenario was rejected');h.api.downloadReport();assert.deepEqual(JSON.parse(await h.blob.text()),h.old);
});
test('malformed input is rejected before a server or worker is called',async()=>{
 for(const input of ['[]','null','true','{broken',JSON.stringify({text:'x'.repeat(262144)})]){
  const h=harness();h.element('#input').value=input;await h.api.runScenario();assert.equal(h.api.getState().runSerial,0);assert.equal(h.element('#error').hidden,false);assert.equal(h.api.getState().currentReport,h.old);
 }
});
test('incident review sends a backend-valid approval bound to the accepted revision',async t=>{
 const p=maybeProject('incident_command',t);if(!p)return;const h=harness(),example=p.examples[0];let request;
 h.api.setState({current:p,currentReport:example.report,design:views.get(p.id),renderedPayload:JSON.stringify(example.payload)});h.element('#input').value=JSON.stringify(example.payload);h.element('#approval-reviewer').value='Independent reviewer';
 h.sandbox.fetch=async(url,options)=>{request=JSON.parse(options.body);return {ok:true,json:async()=>example.report};};await h.api.runOperation({dataset:{operation:'incident-approve'}});
 assert.ok(request);assert.equal(request.payload.approval.incident_revision,example.report.details.incident_revision);assert.equal(request.payload.approval.action,example.report.details.proposal.action);assert.equal(request.payload.approval.reviewer,'Independent reviewer');assert.deepEqual(request.payload.action_ledger,example.report.details.action_ledger);
 assert.deepEqual(runPythonInputs([{id:p.id,payload:request.payload}]).filter(r=>!r.ok),[]);
});
test('fraud review sends only the selected entity evidence and a backend-valid transition',async t=>{
 const p=maybeProject('fraud_investigation_workbench',t);if(!p)return;const h=harness(),example=p.examples[0],entity=example.report.details.entities.find(x=>x.review_required);let request;
 h.api.setState({current:p,currentReport:example.report,design:views.get(p.id),renderedPayload:JSON.stringify(example.payload)});h.element('#input').value=JSON.stringify(example.payload);
 const values={'[data-disposition]':'triaged','[data-reviewer]':'Independent reviewer','[data-rationale]':'Review linked synthetic transaction evidence'};
 h.sandbox.document.querySelectorAll=selector=>selector in values?[{value:values[selector],getAttribute:()=>entity.entity_id}]:[];
 h.sandbox.fetch=async(url,options)=>{request=JSON.parse(options.body);return {ok:true,json:async()=>example.report};};await h.api.runOperation({dataset:{operation:'fraud-review',entity:entity.entity_id}});
 assert.ok(request);const review=request.payload.case_reviews.at(-1);assert.equal(review.entity_id,entity.entity_id);assert.equal(review.expected_revision,example.report.details.activity_revision);assert.equal(review.from_state,'new');assert.equal(review.to_state,'triaged');assert.deepEqual(review.evidence_ids,entity.indicators.map(x=>x.id));
 assert.deepEqual(runPythonInputs([{id:p.id,payload:request.payload}]).filter(r=>!r.ok),[]);
});

function workerHarness({failFirst=false}={}){
 const messages=[],calls=[],values=[];let loads=0;
 const python={unpackArchive(){},globals:{set(key,value){values.push([key,value]);}},async runPythonAsync(source){calls.push(source);if(source.startsWith('request ='))return JSON.stringify({summary:'Computed report'});}};
 const sandbox={console,URL,self:{location:{href:'https://example.test/worker.js'}},postMessage:m=>messages.push(m),loadPyodide:async()=>{if(++loads===1&&failFirst)throw new Error('Initialization failure');return python;},fetch:async()=>({ok:true,arrayBuffer:async()=>new ArrayBuffer(0)})};
 const source=fs.readFileSync(path.join(root,'web/worker.js'),'utf8').replace(/^import[^\n]*\n/gm,'');vm.createContext(sandbox);new vm.Script(source,{filename:'web/worker.js (test harness)'}).runInContext(sandbox);
 return {sandbox,messages,calls,values,get loads(){return loads;}};
}
test('worker passes scenario text as JSON data instead of interpolated Python',async()=>{
 const h=workerHarness(),request={project_id:'test_app',payload:{text:"'); __import__('os').system('not executed') #"}};await h.sandbox.onmessage({data:request});
 assert.equal(h.values[0][0],'request_json');assert.deepEqual(JSON.parse(h.values[0][1]),request);assert.ok(h.calls.every(source=>!source.includes('not executed')));assert.equal(h.messages.at(-1).report.summary,'Computed report');
});
test('worker initialization errors are reported and a later request can retry',async()=>{
 const h=workerHarness({failFirst:true});await h.sandbox.onmessage({data:{project_id:'test_app',payload:{}}});assert.match(h.messages.at(-1).error,/Initialization failure/);
 await h.sandbox.onmessage({data:{project_id:'test_app',payload:{}}});assert.equal(h.loads,2);assert.equal(h.messages.at(-1).report.summary,'Computed report');
});

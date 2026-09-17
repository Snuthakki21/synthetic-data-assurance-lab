/** Independent Staff Engineer regressions: async selection and storage contracts. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {WorkspaceController} from '../web/workspace/controller.js';
import {BrowserWorkspaceRepository} from '../web/workspace/repository.js';
import {MemoryStateStorage} from '../web/workspace/storage.js';
import {numericDelta} from '../web/workspace/contracts.js';

const deferred=()=>{let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return {promise,resolve,reject};};
const result=id=>({run_id:id,project_id:'product',status:'succeeded',payload:{n:1},report:{summary:id,metrics:[]},review_status:'unreviewed',review_version:0,mode:'local'});
function controller(){
 const nodes=new Map();
 const node=id=>{if(!nodes.has(id))nodes.set(id,{innerHTML:'',textContent:'',value:'',disabled:false,dataset:{},querySelectorAll:()=>[]});return nodes.get(id);};
 const c=new WorkspaceController({id:'product'},{native:true,readInput:()=>({n:1}),loadInput:()=>{},loadRun:()=>{},announce:()=>{}});
 c.element=node;
 return {c,node};
}

test('latest inspected run remains selected when an older request returns late',async()=>{
 const {c,node}=controller(),slow=deferred();
 c.repository={getRun:id=>id==='older'?slow.promise:Promise.resolve(result(id))};
 const first=c.inspect('older');await c.inspect('newer');slow.resolve(result('older'));await first;
 assert.equal(c.selectedRun.run_id,'newer');assert.match(node('workspace-review').innerHTML,/newer/);
});

test('a destroyed controller cannot publish an in-flight comparison',async()=>{
 const {c,node}=controller(),slow=deferred();node('comparison-left').value='left';node('comparison-right').value='right';
 c.repository={compare:()=>slow.promise};
 const pending=c.compare();c.destroy();slow.resolve({interpretation:'Late result',metrics:[],input_changes:[]});await pending;
 assert.equal(node('workspace-comparison').innerHTML,'');
});

test('latest comparison wins when the earlier comparison returns last',async()=>{
 const {c,node}=controller(),slow=deferred();node('comparison-left').value='left';node('comparison-right').value='old';
 c.repository={compare:(_left,right)=>right==='old'?slow.promise:Promise.resolve({interpretation:'New comparison',metrics:[],input_changes:[]})};
 const first=c.compare();node('comparison-right').value='new';await c.compare();slow.resolve({interpretation:'Old comparison',metrics:[],input_changes:[]});await first;
 assert.match(node('workspace-comparison').innerHTML,/New comparison/);assert.doesNotMatch(node('workspace-comparison').innerHTML,/Old comparison/);
});

test('browser scenario revisions are detached and stale writes are atomic',async()=>{
 let next=0;const storage=new MemoryStateStorage(),repo=new BrowserWorkspaceRepository('product',storage,()=>new Date(0).toISOString(),()=>String(++next));
 const input={nested:{n:1}},first=await repo.saveScenario('Original',input);input.nested.n=10;
 await repo.saveScenario('Revision',{nested:{n:2}},first.scenario_id,1);
 await assert.rejects(repo.saveScenario('Stale',{nested:{n:3}},first.scenario_id,1),/changed/);
 assert.equal((await repo.getScenario(first.scenario_id,1)).payload.nested.n,1);
 assert.equal((await repo.getScenario(first.scenario_id)).payload.nested.n,2);
 assert.equal((await repo.audit()).length,2);
});

test('failed browser persistence preserves earlier records',async()=>{
 const storage=new MemoryStateStorage(),repo=new BrowserWorkspaceRepository('product',storage,()=>new Date(0).toISOString(),()=>crypto.randomUUID());
 await repo.saveScenario('Baseline',{n:1});const prior=await storage.read();
 const original=storage.update.bind(storage);storage.update=()=>Promise.reject(new Error('Storage full'));
 await assert.rejects(repo.saveScenario('Unsaved',{n:2}),/Storage full/);storage.update=original;
 assert.deepEqual(await storage.read(),prior);
});

test('browser review cannot approve a failed run and rejects stale review versions',async()=>{
 let next=0;const repo=new BrowserWorkspaceRepository('product',new MemoryStateStorage(),()=>new Date(0).toISOString(),()=>String(++next));
 const failed=await repo.recordRun({n:1},null,'Execution failed');await assert.rejects(repo.reviewRun(failed.run_id,'approved','Reviewer','Reviewed',0),/successful/);
 const completed=await repo.recordRun({n:1},{summary:'Result',metrics:[]});await repo.reviewRun(completed.run_id,'approved','Reviewer','Reviewed',0);
 await assert.rejects(repo.reviewRun(completed.run_id,'needs_changes','Reviewer','Reviewed',0),/changed/);
 assert.equal((await repo.getRun(completed.run_id)).review_status,'approved');
});

test('decimal comparison preserves cent differences beyond binary float precision',()=>{
 assert.equal(numericDelta('999999999999999.99','1000000000000000.00'),'0.01');
 assert.equal(numericDelta('1e-6','0.000002'),'0.000001');
 assert.equal(numericDelta(true,1),null);
});

test('comparison retains all metrics when a duplicate suffix collides with a real label',async()=>{
 const {compareRuns}=await import('../web/workspace/contracts.js');
 const left=result('left'),right=result('right');
 left.report.metrics=[{label:'Amount',value:'1',unit:'USD'},{label:'Amount [3]',value:'2',unit:'USD'},{label:'Amount',value:'3',unit:'USD'}];
 right.report.metrics=structuredClone(left.report.metrics);
 assert.equal(compareRuns(left,right).metrics.length,3);
});

test('saved browser run pins the chosen immutable scenario revision',async()=>{
 let next=0;const repo=new BrowserWorkspaceRepository('product',new MemoryStateStorage(),()=>new Date(0).toISOString(),()=>String(++next));
 const original=await repo.saveScenario('Baseline',{n:1});
 await repo.saveScenario('Candidate',{n:2},original.scenario_id,1);
 const run=await repo.recordRun({n:1},{summary:'Original revision result',metrics:[]},null,original);
 assert.equal(run.scenario_id,original.scenario_id);assert.equal(run.scenario_version,1);
 await assert.rejects(repo.recordRun({n:2},{summary:'Wrong payload',metrics:[]},null,original),/does not match/);
 await repo.archiveScenario(original.scenario_id,2);
 await assert.rejects(repo.recordRun({n:1},{summary:'Archived revision',metrics:[]},null,original),/active/);
});

test('controller binds native execution only when selected payload exactly matches',async()=>{
 const {c}=controller();const selected={scenario_id:'scenario',version:1,payload:{n:1}};c.selectedScenario=selected;
 const calls=[];c.repository={execute:async(payload,signal,scenario)=>{calls.push(scenario);return result('run');}};
 await c.executeNative({n:1});await c.executeNative({n:2});
 assert.equal(calls[0],selected);assert.equal(calls[1],null);
});

test('native transport is invoked without a repository receiver',async()=>{
 const {NativeWorkspaceClient}=await import('../web/workspace/client.js');
 const transport=function(path,options){assert.equal(this,undefined);assert.equal(path,'/api/v1/diagnostics');return Promise.resolve({ok:true,json:async()=>({storage:'sqlite'})});};
 const client=new NativeWorkspaceClient('product',transport);
 assert.equal((await client.diagnostics()).storage,'sqlite');
});

test('typing a scalar control updates executable JSON before a blur event',async()=>{
 const {readFileSync}=await import('node:fs');const vm=await import('node:vm');const {applyField}=await import('../web/ui.js');
 const source=readFileSync(new URL('../web/app.js',import.meta.url),'utf8');
 const functionSource=source.slice(source.indexOf('function renderControls('),source.indexOf('function restoreExample('));
 const input={type:'number',value:'2',dataset:{path:'n',valueType:'number'}};
 const nodes={'#project-controls':{innerHTML:''},'#input':{value:'{"n":1}'},'#error':{hidden:true}};
 vm.runInNewContext('let importSerial=0;'+functionSource+';renderControls({n:1});',{$:selector=>nodes[selector],$$:()=>[input],design:{controls:()=>''},applyField,announce:()=>{},showError:message=>{throw new Error(message);}});
 assert.equal(typeof input.oninput,'function');input.oninput();
 assert.equal(JSON.parse(nodes['#input'].value).n,2);
});

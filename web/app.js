import {applyField} from './ui.js';
'use strict';
const $ = (s, root = document) => root.querySelector(s);
const $$ = (s, root = document) => [...root.querySelectorAll(s)];
const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pretty = key => key.replaceAll('_',' ').replace(/\b\w/, c => c.toUpperCase());
let catalog, current, currentReport, worker, pendingRun, serverMode = null, activeController = null, runSerial = 0;
let selectedExample = 0, design, renderedPayload = null, importSerial = 0, userTheme = null;

function announce(message) { $('#status').textContent = message; }
function valueText(value) {
  if (value === null || value === undefined) return 'Not provided';
  if (typeof value === 'object') return JSON.stringify(value);
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  return String(value);
}
function renderDetails(data) {
  return Object.entries(data).slice(0,24).map(([key,value]) => {
    if (Array.isArray(value) && value.length && value.every(x => x && typeof x === 'object' && !Array.isArray(x))) {
      const keys = [...new Set(value.slice(0,12).flatMap(Object.keys))].slice(0,7);
      return `<div class="table-wrap"><table class="detail-table"><caption>${escapeHtml(pretty(key))}</caption><thead><tr>${keys.map(k=>`<th scope="col">${escapeHtml(pretty(k))}</th>`).join('')}</tr></thead><tbody>${value.slice(0,20).map(row=>`<tr>${keys.map(k=>`<td>${escapeHtml(valueText(row[k]))}</td>`).join('')}</tr>`).join('')}</tbody></table>${value.length>20?`<p class="fine">Showing 20 of ${value.length} rows. Download the report for all records.</p>`:''}</div>`;
    }
    if (Array.isArray(value) && value.length && value.every(x=>typeof x !== 'object')) return `<div class="data-section"><h4>${escapeHtml(pretty(key))}</h4><p>${escapeHtml(value.join(', '))}</p></div>`;
    if (value && typeof value === 'object') return `<details class="disclosure"><summary>${escapeHtml(pretty(key))}</summary><pre>${escapeHtml(JSON.stringify(value,null,2))}</pre></details>`;
    return `<div class="data-section"><h4>${escapeHtml(pretty(key))}</h4><p>${escapeHtml(valueText(value))}</p></div>`;
  }).join('');
}
function renderReport(report, fresh = false, inputSnapshot = $('#input').value) {
  const p = report.provenance || {};
  const markup = `<div class="result-label">${fresh?'Fresh execution':'Executed example'}${p.mode==='live'?' with model integration':' using local algorithms'}</div>${design.result(report)}<details class="disclosure reasoning"><summary>Decision rationale and follow-up</summary><p class="decision">${escapeHtml(report.summary)}</p><div class="evidence-columns"><div><h3>Evidence behind the result</h3><ul>${report.evidence.map(x=>`<li>${escapeHtml(x)}</li>`).join('')}</ul></div><div><h3>Next decisions</h3><ul>${report.next_actions.map(x=>`<li>${escapeHtml(x)}</li>`).join('')}</ul></div></div></details><details class="disclosure"><summary>Inspect the full result</summary>${renderDetails(report.details)}</details><p class="proof">Executed ${escapeHtml(p.executed_at)} in ${escapeHtml(p.elapsed_ms)} ms. Input ${escapeHtml(p.input_sha256?.slice(0,16))}.<br>${escapeHtml(p.scope)}</p>`;
  $('#report').innerHTML=markup;currentReport=report;renderedPayload=inputSnapshot;
  $$('[data-operation]').forEach(b=>b.onclick=()=>runOperation(b));
  $$('[data-case-target]').forEach(a=>a.onclick=event=>{event.preventDefault();const target=document.getElementById('case-'+a.dataset.caseTarget);if(target){$$('.case-file').forEach(f=>f.hidden=f!==target);$$('[data-case-target]').forEach(link=>link.setAttribute('aria-current',String(link===a)));target.tabIndex=-1;target.focus({preventScroll:true});target.scrollIntoView({block:'start'});}});
  $('#download').disabled = false;
}
function setTab(name) {
  $$('.tabs [role=tab]').forEach(b=>{const active=b.dataset.tab===name;b.setAttribute('aria-selected',String(active));b.tabIndex=active?0:-1;});
  $$('.tab-panel').forEach(panel=>panel.hidden=panel.id!==`panel-${name}`);
}
function showProject(project) {
  current = project; selectedExample = 0;
  document.body.dataset.project=project.id;document.body.dataset.layout=design.layout;
  if(!userTheme)document.documentElement.dataset.theme=['incident-room','routing-lab'].includes(design.layout)?'dark':'light';
  $('#source-link').href=project.repo_url; $('#footer-source').href=project.repo_url;
  const detail = $('#project-detail'); detail.hidden = false;
  document.title = `${project.title} | Seshu Nuthakki`;
  detail.innerHTML = `<div class="detail-top"><div class="detail-heading"><p class="eyebrow">${escapeHtml(design.label)}</p><h1>${escapeHtml(project.title)}</h1><p>${escapeHtml(project.question)}</p></div><div class="detail-actions"><a class="button" href="${escapeHtml(project.repo_url)}">Open repository ↗</a><a class="button" href="${escapeHtml(project.repo_url)}/blob/main/README.md">Read the executive brief ↗</a><button class="button" id="download">Download report</button></div></div><div class="tabs" role="tablist" aria-label="Project views"><button role="tab" id="tab-demo" aria-controls="panel-demo" aria-selected="true" data-tab="demo">Workspace</button><button role="tab" id="tab-architecture" aria-controls="panel-architecture" aria-selected="false" tabindex="-1" data-tab="architecture">Architecture</button><button role="tab" id="tab-leadership" aria-controls="panel-leadership" aria-selected="false" tabindex="-1" data-tab="leadership">Leadership evidence</button></div><section class="tab-panel" id="panel-demo" role="tabpanel" aria-labelledby="tab-demo"><div class="workspace-layout"><aside class="workspace-controls"><h2>${escapeHtml(design.controlsTitle)}</h2><div class="scenario-bar"><label>Load an example<select id="scenario">${project.examples.map((example,i)=>`<option value="${i}">${escapeHtml(example.label)}</option>`).join('')}</select></label><div id="project-controls"></div><button id="run" class="button primary">${escapeHtml(design.action)}</button><button id="cancel" class="button" hidden>Cancel run</button></div><p id="run-note" class="run-note">${serverMode?`Connected to the local application (${escapeHtml(serverMode)} mode).`:'Run the same Python application in your browser. The first run loads the execution engine.'} No account or API key is needed for local algorithms.</p><div id="error" role="alert" hidden class="error"></div></aside><div class="workspace-results"><div id="report" class="report" aria-live="polite"></div><details class="disclosure"><summary>Change the input data</summary><p class="fine">Edit the structured sample, then run it. Input stays in this browser unless you explicitly run a local server with a model provider.</p><label for="input" class="sr-only">Scenario input JSON</label><textarea id="input" spellcheck="false"></textarea><button class="button" id="restore">Restore selected sample</button><label class="import-label">Load a JSON input file<input id="input-file" type="file" accept=".json,application/json"></label></details></div></div></section><section class="tab-panel" id="panel-architecture" role="tabpanel" aria-labelledby="tab-architecture" hidden><h2>How the decision is made</h2><p>${escapeHtml(project.description)}</p><ol class="architecture">${project.architecture.map(step=>`<li>${escapeHtml(step)}</li>`).join('')}</ol><div class="patterns">${project.patterns.map(p=>`<span class="pattern">${escapeHtml(p)}</span>`).join('')}</div><div class="two-column"><div><h3>Risks the design addresses</h3><ul>${project.risks.map(x=>`<li>${escapeHtml(x)}</li>`).join('')}</ul></div><div><h3>Boundaries of this implementation</h3><ul>${project.limits.map(x=>`<li>${escapeHtml(x)}</li>`).join('')}</ul></div></div><a class="inline-link" href="${escapeHtml(project.repo_url)}/tree/main/tests">Inspect the tests ↗</a></section><section class="tab-panel" id="panel-leadership" role="tabpanel" aria-labelledby="tab-leadership" hidden><h2>Evidence for two levels of responsibility</h2><div class="two-column"><div><h3>Principal: engineering judgment</h3><p>${escapeHtml(project.principal)}</p><p>Inspect the algorithm, its failure cases, trust boundaries and documented tradeoffs in the repository.</p></div><div><h3>Director: delivery judgment</h3><p>${escapeHtml(project.director)}</p><p>Use the output to discuss ownership, acceptance criteria, investment priorities and the evidence needed before wider adoption.</p></div></div><h3>Business stakeholder</h3><p>${escapeHtml(project.buyer)}</p><a class="inline-link" href="${escapeHtml(project.repo_url)}/blob/main/docs/OPERATING_MODEL.md">Read the operating model ↗</a></section>`;
  $$('.tabs button').forEach(b=>b.onclick=()=>setTab(b.dataset.tab));
  $('.tabs').onkeydown = event => {
    if (!['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
    const tabs=$$('.tabs button'), i=tabs.indexOf(document.activeElement);
    const n=event.key==='Home'?0:event.key==='End'?tabs.length-1:(i+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;
    event.preventDefault();setTab(tabs[n].dataset.tab);tabs[n].focus();
  };
  $('#scenario').onchange = () => { selectedExample=Number($('#scenario').value); restoreExample(); renderReport(project.examples[selectedExample].report); };
  $('#restore').onclick = restoreExample;
  $('#input').oninput = () => {++importSerial;announce('Input changed. Run again to update the results.');};
  $('#input').onchange=()=>{try{renderControls(JSON.parse($('#input').value));}catch{$('#project-controls').innerHTML='<p>Use the full input editor to finish this custom input.</p>';}};
  $('#input-file').onchange = loadInputFile;
  $('#run').onclick = runScenario;
  $('#cancel').onclick = () => cancelRun();
  $('#download').onclick = downloadReport;
  restoreExample(); renderReport(project.examples[0].report);

}
function renderControls(payload){
 $('#project-controls').innerHTML=design.controls(payload);
 $$('[data-path]').forEach(input=>input.onchange=()=>{
   try{++importSerial;const p=JSON.parse($('#input').value);applyField(p,input.dataset.path,input.type==='checkbox'?input.checked:input.value,input.dataset.valueType);$('#input').value=JSON.stringify(p,null,2);$('#error').hidden=true;announce('Input changed. Run again to update the results.');}
   catch(error){showError(error.message);}
 });
}
function restoreExample() { ++importSerial;const p=current.examples[selectedExample].payload;$('#input').value=JSON.stringify(p,null,2);renderControls(p);$('#error').hidden=true; }
function showError(text){$('#error').textContent=text;$('#error').hidden=false;announce(text);}
async function loadInputFile(event){
 const file=event.target.files[0];if(!file)return;
 const serial=++importSerial,run=runSerial,pid=current.id,priorInput=$('#input').value;
 try{
  if(file.size>262144)throw new Error('Input exceeds 256 KB.');
  const text=await file.text();
  if(serial!==importSerial||run!==runSerial||pid!==current.id||priorInput!==$('#input').value)return;
  const p=JSON.parse(text);if(!p||Array.isArray(p)||typeof p!=='object')throw new Error('Input must be an object.');
  $('#input').value=JSON.stringify(p,null,2);
  try{renderControls(p);}catch{$('#project-controls').innerHTML='<p>Custom structure loaded. Use the full input editor below.</p>';}
  $('#error').hidden=true;announce('Input file loaded. Run to validate and compute results.');
 }catch(error){if(serial===importSerial&&run===runSerial&&pid===current.id)showError(error.message);}
}
async function runOperation(button){
 try{
  if($('#input').value!==renderedPayload)throw new Error('Run the changed input before recording a review against this result.');
  const p=JSON.parse($('#input').value),d=currentReport.details;
  if(button.dataset.operation==='incident-approve'){
   const reviewer=$('#approval-reviewer').value.trim();if(!reviewer)throw new Error('Enter a simulation reviewer.');
   p.action_ledger=d.action_ledger;p.approval={approved:true,action:d.proposal.action,incident_revision:d.incident_revision,reviewer};
  }else{
   const id=button.dataset.entity,byAttr=attr=>$$('['+attr+']').find(e=>e.getAttribute(attr)===id);
   const to=byAttr('data-disposition').value,reviewer=byAttr('data-reviewer').value.trim(),rationale=byAttr('data-rationale').value.trim();
   if(!to||reviewer.length<3||rationale.length<3)throw new Error('Choose a disposition and enter a reviewer and rationale of at least three characters.');
   p.case_reviews=[...d.review_audit,{review_id:'review-'+crypto.randomUUID(),entity_id:id,from_state:d.case_states[id],to_state:to,reviewer,rationale,evidence_ids:d.entities.find(x=>x.entity_id===id).indicators.map(x=>x.id),expected_revision:d.activity_revision}];
  }
  $('#input').value=JSON.stringify(p,null,2);await runScenario();
 }catch(error){showError(error.message);}
}
function setBusy(busy,message) { for(const element of $$('[data-path], [data-operation], #input-file'))element.disabled=busy; for(const id of ['run','scenario','input','restore']) { const element=$('#'+id); if(element)element.disabled=busy; } $('#cancel').hidden=!busy;if(message)$('#run-note').textContent=message;announce(message||'Ready'); }
function cancelRun(silent=false) { ++runSerial; if(activeController){activeController.abort();activeController=null;} if(worker){worker.terminate();worker=null;} if(pendingRun){clearTimeout(pendingRun.timer);pendingRun.reject(new Error('Run cancelled.'));pendingRun=null;} if(!silent&&$('#run'))setBusy(false,'Run cancelled. Your previous report is unchanged.'); }
async function browserRun(payload) {
  if(!worker)worker=new Worker('worker.js',{type:'module'});
  return new Promise((resolve,reject)=>{
    const timer=setTimeout(()=>{worker.terminate();worker=null;pendingRun=null;reject(new Error('This run exceeded two minutes. Try a smaller input or use the local application.'));},120000);
    pendingRun={resolve,reject,timer};
    worker.onmessage=event=>{
      if(event.data.type==='progress'){setBusy(true,event.data.message);return;}
      clearTimeout(timer);pendingRun=null;
      if(event.data.error)reject(new Error(event.data.error)); else resolve(event.data.report);
    };
    worker.onerror=()=>{clearTimeout(timer);pendingRun=null;worker.terminate();worker=null;reject(new Error('The browser engine could not start. Check your connection or use the repository’s local run command.'));};
    worker.postMessage({project_id:current.id,payload});
  });
}
async function runScenario() {
  let payload;const inputSnapshot=$('#input').value;
  try{payload=JSON.parse($('#input').value);if(!payload||typeof payload!=='object'||Array.isArray(payload))throw new Error('Input must be an object.');if(new TextEncoder().encode($('#input').value).length>262144)throw new Error('Input exceeds 256 KB.');}
  catch(error){$('#error').textContent=`Check the input: ${error.message}`;$('#error').hidden=false;return;}
  const targetId=current.id, serial=++runSerial; activeController=new AbortController();
  setBusy(true,'Running the application…');$('#error').hidden=true;
  try{
    let report;
    if(serverMode){const response=await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project_id:targetId,payload}),signal:activeController.signal});report=await response.json();if(!response.ok)throw new Error(report.error||'The application rejected this input.');}
    else report=await browserRun(payload);
    if(runSerial===serial&&current?.id===targetId){renderReport(report,true,inputSnapshot);setBusy(false,'Execution finished. The report below reflects the input you ran.');}
  }catch(error){if(runSerial===serial&&current?.id===targetId){$('#error').textContent=error.message;$('#error').hidden=false;setBusy(false,'No new result was accepted. The previous report is still available.');}}
}
function downloadReport(){const a=document.createElement('a');const url=URL.createObjectURL(new Blob([JSON.stringify(currentReport,null,2)],{type:'application/json'}));a.href=url;a.download=`${current.id}-report.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
async function route(){
  cancelRun(true);
  let id;try{id=location.hash.startsWith('#project/')?decodeURIComponent(location.hash.slice(9)):null;}catch{id=null;}
  const item=catalog.projects.find(x=>x.id===id)||catalog.projects[0];
  if(!item){$('#project-detail').innerHTML='<p class="error">No application was included in this build. Open the repository for setup instructions.</p>';return;}
  const routeSerial=runSerial;
  try{const loaded=await import(`./templates/${item.id}.js`);if(routeSerial!==runSerial)return;design=loaded.default;showProject(item);}
  catch(error){$('#project-detail').innerHTML=`<p class="error">Application view could not load: ${escapeHtml(error.message)}</p>`;}
  window.scrollTo(0,0);
}
async function init(){
  try{
    if(location.hostname==='127.0.0.1'||location.hostname==='localhost'){try{const h=await fetch('/api/health');if(h.ok)serverMode=(await h.json()).mode;}catch{}}
    const response=await fetch('catalog.json');if(!response.ok)throw new Error('Project catalog unavailable.');catalog=await response.json();
    $('#theme').onclick=()=>{const dark=document.documentElement.dataset.theme==='dark'||(!document.documentElement.dataset.theme&&matchMedia('(prefers-color-scheme:dark)').matches);userTheme=dark?'light':'dark';document.documentElement.dataset.theme=userTheme;};
    window.addEventListener('hashchange',route);route();
  }catch(error){$('#project-detail').innerHTML=`<p class="error">${escapeHtml(error.message)} Reload this page or open the GitHub repository.</p>`;}
}
init();

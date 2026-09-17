/** Workspace presentation coordinates library, history, comparison and review. */
import {BrowserWorkspaceRepository} from './repository.js';
import {NativeWorkspaceClient} from './client.js';
import {canonical, escape, REVIEW_TRANSITIONS} from './contracts.js';

const show = value => value === null || value === undefined ? '—' : typeof value === 'object' ? JSON.stringify(value) : String(value);
const date = value => new Date(value).toLocaleString();
const options = rows => rows.map(row => `<option value="${escape(row.run_id)}">${escape(date(row.started_at))} · ${escape(row.status)} · ${escape(row.run_id.slice(0, 8))}</option>`).join('');

export class WorkspaceController {
  constructor(project, {native = false, authenticationRequired = false, readInput, loadInput, loadRun, announce}) {
    this.project = project;
    this.repository = native ? new NativeWorkspaceClient(project.id) : new BrowserWorkspaceRepository(project.id);
    this.authenticationRequired = authenticationRequired;
    this.connected = !authenticationRequired;
    this.readInput = readInput;
    this.loadInput = loadInput;
    this.loadRun = loadRun;
    this.announce = announce;
    this.selectedScenario = null;
    this.selectedRun = null;
    this.destroyed = false;
    this.generations = {refresh: 0, inspect: 0, compare: 0, scenario: 0};
  }
  element(id) { return document.getElementById(id); }
  static panels() {
    return `<section class="tab-panel workspace-panel" id="panel-library" role="tabpanel" aria-labelledby="tab-library" hidden><div class="workspace-section-heading"><div><h2>Scenario library</h2><p>Keep named inputs and their revisions. Loading a revision never overwrites it.</p></div><button class="button" id="workspace-export" data-workspace-action>Export workspace</button></div><div id="workspace-connection"></div><p id="workspace-notice" role="status" class="workspace-notice"></p><div class="workspace-editor"><label>Scenario name<input id="workspace-name" maxlength="120" placeholder="For example, quarter-end adverse case"></label><button id="workspace-save" class="button primary" data-workspace-action>Save current input as new scenario</button><button id="workspace-revise" class="button" data-workspace-action disabled>Save next revision</button></div><p id="workspace-selection" class="fine">No saved scenario is selected.</p><div id="workspace-scenarios"></div></section>
<section class="tab-panel workspace-panel" id="panel-history" role="tabpanel" aria-labelledby="tab-history" hidden><div class="workspace-section-heading"><div><h2>Execution history</h2><p>Reopen exact input and result pairs, compare outcomes, and record evidence review.</p></div><button id="workspace-refresh" class="button" data-workspace-action>Refresh history</button></div><div id="workspace-runs"></div><div id="workspace-review"></div><section class="comparison-workspace"><h3>Compare completed runs</h3><div class="workspace-editor"><label>Earlier run<select id="comparison-left"></select></label><label>Later run<select id="comparison-right"></select></label><button id="workspace-compare" class="button" data-workspace-action>Compare selected runs</button></div><div id="workspace-comparison"></div></section></section>`;
  }
  async initialize() {
    this.bind('workspace-save', () => this.save(false));
    this.bind('workspace-revise', () => this.save(true));
    this.bind('workspace-refresh', () => this.refresh());
    this.bind('workspace-compare', () => this.compare());
    this.bind('workspace-export', () => this.export());
    this.element('workspace-connection').innerHTML = this.authenticationRequired ? `<form id="workspace-connect-form" class="workspace-editor"><label>Workspace access token<input id="workspace-token" type="password" autocomplete="off" spellcheck="false" required></label><button class="button" type="submit" data-workspace-action>Connect to native workspace</button></form><p class="fine">The token remains in this tab's memory and is discarded when the page closes.</p>` : '';
    if (this.authenticationRequired) this.element('workspace-connect-form').onsubmit = event => {
      event.preventDefault();
      this.perform(async () => {
        this.repository.setToken(this.element('workspace-token').value);
        await this.repository.diagnostics();
        this.connected = true;
        this.element('workspace-token').value = '';
        this.element('workspace-connection').innerHTML = '<p class="workspace-notice">Connected to the native workspace.</p>';
        await this.refresh();
      });
    };
    if (this.connected) await this.refresh();
    else this.notice('Connect in Scenario library before running or reading the native workspace.');
  }
  bind(id, action) {
    const element = this.element(id);
    if (element) element.onclick = () => this.perform(action, element);
  }
  async perform(action, button = null) {
    if (button) button.disabled = true;
    try { await action(); }
    catch (error) { this.notice(error.message, true); }
    finally { if (button?.isConnected) button.disabled = false; }
  }
  notice(message, failed = false) {
    if (this.destroyed) return;
    const node = this.element('workspace-notice');
    if (node) { node.textContent = message; node.dataset.error = String(failed); }
    this.announce(message);
  }
  async refresh() {
    if (this.destroyed || !this.connected) return;
    const generation = ++this.generations.refresh;
    const [scenarios, runs, diagnostics, audit] = await Promise.all([
      this.repository.listScenarios(true), this.repository.listRuns(), this.repository.diagnostics(), this.repository.audit(),
    ]);
    if (this.destroyed || generation !== this.generations.refresh) return;
    this.renderScenarios(scenarios);
    this.renderRuns(runs);
    this.renderDiagnostics(diagnostics, audit);
    if (this.selectedRun) await this.inspect(this.selectedRun.run_id);
    this.notice(this.repository.kind === 'browser' ? 'Saved in this browser only. Export important records before clearing site data.' : 'Saved in the native SQLite workspace. Review labels identify operators; they are not separate authenticated accounts.');
  }
  renderScenarios(rows) {
    const target = this.element('workspace-scenarios');
    if (!rows.length) { target.innerHTML = '<div class="workspace-empty"><h3>Your library is empty</h3><p>Run an example, adjust its inputs, give it a useful name, and save it here.</p></div>'; return; }
    target.innerHTML = `<div class="table-wrap"><table class="workspace-table"><caption>Saved scenarios</caption><thead><tr><th>Name</th><th>Revision</th><th>Status</th><th>Actions</th></tr></thead><tbody>${rows.map(row => `<tr><td>${escape(row.name)}</td><td><label class="sr-only" for="version-${escape(row.id)}">Revision for ${escape(row.name)}</label><select id="version-${escape(row.id)}">${Array.from({length: row.version}, (_, index) => row.version - index).map(version => `<option value="${version}">v${version}</option>`).join('')}</select></td><td>${row.archived ? 'Archived' : 'Active'}</td><td><div class="row-actions"><button class="text-button" data-workspace-action data-load-scenario="${escape(row.id)}">Load revision</button><button class="text-button" data-workspace-action data-archive-scenario="${escape(row.id)}">${row.archived ? 'Restore' : 'Archive'}</button></div></td></tr>`).join('')}</tbody></table></div>`;
    target.querySelectorAll('[data-load-scenario]').forEach(button => button.onclick = () => this.perform(async () => {
      const id = button.dataset.loadScenario, version = Number(this.element('version-' + id).value);
      const generation = ++this.generations.scenario;
      const scenario = await this.repository.getScenario(id, version);
      if (this.destroyed || generation !== this.generations.scenario) return;
      if (scenario.archived) throw new Error('Restore this scenario before loading it for a new revision.');
      this.selectedScenario = scenario;
      this.element('workspace-name').value = scenario.name;
      this.element('workspace-revise').disabled = false;
      this.element('workspace-selection').textContent = `${scenario.name} · revision ${scenario.version}. Saving a revision requires this version to still be current.`;
      this.loadInput(scenario.payload);
      this.notice(`Loaded ${scenario.name}, revision ${scenario.version}. Run it to compute a new result.`);
    }, button));
    target.querySelectorAll('[data-archive-scenario]').forEach(button => button.onclick = () => this.perform(async () => {
      const row = rows.find(item => item.id === button.dataset.archiveScenario);
      await this.repository.archiveScenario(row.id, row.version, !row.archived);
      if (this.selectedScenario?.scenario_id === row.id) { this.selectedScenario = null; this.element('workspace-revise').disabled = true; this.element('workspace-selection').textContent = 'No saved scenario is selected.'; }
      await this.refresh();
    }, button));
  }
  async save(revise) {
    if (!this.connected) throw new Error('Connect to the native workspace first.');
    if (revise && !this.selectedScenario) throw new Error('Load a saved scenario before revising it.');
    const value = await this.repository.saveScenario(this.element('workspace-name').value, this.readInput(),
      revise ? this.selectedScenario.scenario_id : null, revise ? this.selectedScenario.version : null);
    if (this.destroyed) return;
    this.selectedScenario = value;
    this.element('workspace-revise').disabled = false;
    this.element('workspace-selection').textContent = `${value.name} · revision ${value.version} selected.`;
    await this.refresh();
    this.notice(`Saved ${value.name}, revision ${value.version}.`);
  }
  renderRuns(rows) {
    const target = this.element('workspace-runs');
    target.innerHTML = rows.length ? `<div class="table-wrap"><table class="workspace-table"><caption>Most recent 100 executions</caption><thead><tr><th>Started</th><th>Outcome</th><th>Review</th><th>Result</th><th>Action</th></tr></thead><tbody>${rows.map(row => `<tr><td>${escape(date(row.started_at))}<small>${escape(row.run_id.slice(0, 8))}</small></td><td>${escape(row.status)}</td><td>${escape(row.review_status.replaceAll('_', ' '))}</td><td>${escape(row.summary || row.error || 'Execution in progress')}</td><td><button class="text-button" data-workspace-action data-inspect-run="${escape(row.run_id)}">Inspect run</button></td></tr>`).join('')}</tbody></table></div>` : '<div class="workspace-empty"><h3>No recorded runs yet</h3><p>Execute a scenario in the workspace. Its input and result will appear here.</p></div>';
    target.querySelectorAll('[data-inspect-run]').forEach(button => button.onclick = () => this.perform(() => this.inspect(button.dataset.inspectRun), button));
    const successful = rows.filter(row => row.status === 'succeeded');
    this.element('comparison-left').innerHTML = options(successful);
    this.element('comparison-right').innerHTML = options(successful);
    if (successful.length > 1) this.element('comparison-left').value = successful[1].run_id;
    this.element('workspace-compare').disabled = successful.length < 2;
  }
  async inspect(id) {
    const generation = ++this.generations.inspect;
    const run = await this.repository.getRun(id);
    if (this.destroyed || generation !== this.generations.inspect) return;
    this.selectedRun = run;
    const target = this.element('workspace-review'), transitions = REVIEW_TRANSITIONS[run.review_status] || [];
    target.innerHTML = `<section class="run-inspector"><h3>Run ${escape(run.run_id.slice(0, 8))}</h3><p>${escape(run.report?.summary || run.error || 'Execution in progress')}</p><p class="fine">${escape(run.mode)} · ${escape(run.status)} · review revision ${run.review_version}</p><div class="row-actions"><button id="workspace-load-run" class="button" data-workspace-action ${run.status !== 'succeeded' ? 'disabled' : ''}>Open exact input and result</button><button id="workspace-export-run" class="button" data-workspace-action>Export execution record</button></div>${run.status === 'succeeded' ? `<form id="workspace-review-form"><h4>Record an evidence review</h4><p class="fine">This decision applies to this stored run. It does not authorize a production action.</p><div class="workspace-editor"><label>Decision<select id="workspace-decision">${transitions.map(value => `<option value="${value}">${value.replaceAll('_', ' ')}</option>`).join('')}</select></label><label>Reviewer identifier<input id="workspace-reviewer" maxlength="100" required></label></div><label>Rationale<textarea id="workspace-rationale" maxlength="2000" rows="3" required></textarea></label><button class="button primary" type="submit" data-workspace-action>Record review</button></form>` : ''}</section>`;
    this.bind('workspace-load-run', () => { this.loadRun(run.payload, run.report); this.notice('Loaded the stored input and result. New edits require a new execution.'); });
    this.bind('workspace-export-run', () => this.download(run, 'execution-' + run.run_id + '.json'));
    const form = this.element('workspace-review-form');
    if (form) form.onsubmit = event => { event.preventDefault(); this.perform(async () => {
      await this.repository.reviewRun(run.run_id, this.element('workspace-decision').value, this.element('workspace-reviewer').value, this.element('workspace-rationale').value, run.review_version);
      await this.refresh(); this.notice('Review recorded against the stored execution.');
    }); };
  }
  async compare() {
    const left = this.element('comparison-left').value, right = this.element('comparison-right').value;
    if (!left || !right || left === right) throw new Error('Select two different successful runs.');
    const generation = ++this.generations.compare;
    const result = await this.repository.compare(left, right);
    if (this.destroyed || generation !== this.generations.compare) return;
    this.element('workspace-comparison').innerHTML = `<p>${escape(result.interpretation)}</p><div class="table-wrap"><table class="workspace-table"><caption>Metric changes</caption><thead><tr><th>Metric</th><th>Earlier</th><th>Later</th><th>Exact decimal difference</th></tr></thead><tbody>${result.metrics.map(metric => `<tr><td>${escape(metric.label)}</td><td>${escape(show(metric.before?.value))} ${escape(metric.before?.unit || '')}</td><td>${escape(show(metric.after?.value))} ${escape(metric.after?.unit || '')}</td><td>${escape(show(metric.numeric_delta))}</td></tr>`).join('')}</tbody></table></div><h4>Changed inputs</h4>${result.input_changes.length ? `<ul class="input-diff">${result.input_changes.map(item => `<li><code>${escape(item.path)}</code> · ${escape(item.kind)}<pre>${escape(show(item.before))} → ${escape(show(item.after))}</pre></li>`).join('')}</ul>` : '<p>The input values are identical.</p>'}${result.input_changes_truncated ? '<p>Only the first 200 changed paths are shown.</p>' : ''}`;
  }
  renderDiagnostics(diagnostics, audit) {
    const target = this.element('workspace-diagnostics');
    if (!target) return;
    target.innerHTML = `<h3>Workspace state</h3><dl class="workspace-facts"><div><dt>Storage</dt><dd>${escape(diagnostics.storage)}</dd></div><div><dt>Scenarios</dt><dd>${diagnostics.scenarios}</dd></div><div><dt>Executions</dt><dd>${diagnostics.executions}</dd></div><div><dt>Audit events</dt><dd>${diagnostics.audit_events}</dd></div></dl><p class="fine">${this.repository.kind === 'browser' ? 'Browser records are local, editable by this browser user and unsigned. Native storage adds transactional revisions and a verifiable audit hash chain.' : 'The audit hash chain detects inconsistent records; it is not independently signed or protected against a database administrator.'}</p><details class="disclosure"><summary>Recent audit events</summary><div class="table-wrap"><table class="workspace-table"><caption>Latest 100 audit events</caption><thead><tr><th>When</th><th>Event</th><th>Entity</th><th>Details</th></tr></thead><tbody>${audit.map(event => `<tr><td>${escape(date(event.occurred_at))}</td><td>${escape(event.kind)}</td><td>${escape(event.entity_id.slice(0, 8))}</td><td>${escape(JSON.stringify(event.details))}</td></tr>`).join('')}</tbody></table></div></details>`;
  }
  matchingScenario(payload) {
    return this.selectedScenario && canonical(this.selectedScenario.payload) === canonical(payload) ? this.selectedScenario : null;
  }
  async executeNative(payload, signal) {
    if (!this.connected) throw new Error('Connect in Scenario library before running the native application.');
    const run = await this.repository.execute(payload, signal, this.matchingScenario(payload));
    if (run.status !== 'succeeded') throw new Error(run.error || 'This execution has not completed. Refresh history to inspect its state.');
    this.selectedRun = run;
    return run.report;
  }
  async recordBrowserRun(payload, report) {
    if (this.repository.kind !== 'browser') return;
    this.selectedRun = await this.repository.recordRun(payload, report, null, this.matchingScenario(payload));
  }
  async export() { this.download(await this.repository.exportWorkspace(), this.project.id + '-workspace.json'); }
  download(value, filename) {
    const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], {type: 'application/json'}));
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = filename; anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  destroy() { this.destroyed = true; this.repository.setToken?.(null); }
}

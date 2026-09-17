/** Browser workspace domain operations; persistent data is isolated per product. */
import {canonical, clone, compareRuns, REVIEW_TRANSITIONS, text, validateInput} from './contracts.js';
import {IndexedDBStateStorage} from './storage.js';

export class BrowserWorkspaceRepository {
  constructor(projectId, storage = null, clock = () => new Date().toISOString(), makeId = () => crypto.randomUUID()) {
    this.projectId = projectId;
    this.storage = storage || new IndexedDBStateStorage('application-workspace-v1-' + projectId);
    this.clock = clock;
    this.makeId = makeId;
    this.kind = 'browser';
  }
  event(state, kind, entityId, details) {
    state.audit.push({sequence: state.audit.length + 1, event_id: this.makeId(), occurred_at: this.clock(), kind, entity_id: entityId, details});
  }
  async saveScenario(name, payload, scenarioId = null, expectedVersion = null) {
    name = text(name, 'Scenario name'); payload = validateInput(payload);
    return this.storage.update(state => {
      if (scenarioId === null && expectedVersion !== null) throw new Error('New scenarios cannot have an expected revision.');
      if (scenarioId !== null && (!Number.isInteger(expectedVersion) || expectedVersion < 1)) throw new Error('Select a positive expected revision.');
      let current = scenarioId && Object.hasOwn(state.scenarios, scenarioId) ? state.scenarios[scenarioId] : null;
      if (scenarioId && !current) throw new Error('Scenario not found.');
      if (current && (current.version !== expectedVersion || current.archived)) throw new Error('Scenario changed or was archived. Reload before saving.');
      if (!current && Object.keys(state.scenarios).length >= 500) throw new Error('This browser workspace supports 500 scenarios. Export your records before creating another workspace.');
      const id = scenarioId || this.makeId(), version = current ? current.version + 1 : 1;
      const value = {scenario_id: id, project_id: this.projectId, name, version, payload, created_at: this.clock(), archived: false};
      state.scenarios[id] = {id, project_id: this.projectId, name, version, created_at: current?.created_at || value.created_at, archived: false};
      state.revisions[id] ||= [];
      if (state.revisions[id].length >= 500) throw new Error('A scenario supports at most 500 revisions in this browser workspace.');
      state.revisions[id].push(value);
      this.event(state, current ? 'scenario.revised' : 'scenario.created', id, {version});
      return value;
    });
  }
  async listScenarios(includeArchived = false) {
    const state = await this.storage.read();
    return Object.values(state.scenarios).filter(item => includeArchived || !item.archived).sort((a, b) => b.created_at.localeCompare(a.created_at));
  }
  async getScenario(id, version = null) {
    const state = await this.storage.read(), scenario = Object.hasOwn(state.scenarios, id) ? state.scenarios[id] : null;
    if (!scenario) throw new Error('Scenario not found.');
    const revision = state.revisions[id].find(item => item.version === (version ?? scenario.version));
    if (!revision) throw new Error('Scenario revision not found.');
    return {...revision, archived: scenario.archived};
  }
  async archiveScenario(id, expectedVersion, archived = true) {
    if (typeof archived !== 'boolean') throw new Error('Archive state must be a boolean.');
    return this.storage.update(state => {
      const current = Object.hasOwn(state.scenarios, id) ? state.scenarios[id] : null;
      if (!current) throw new Error('Scenario not found.');
      if (current.version !== expectedVersion) throw new Error('Scenario revision changed. Reload before archiving.');
      if (current.archived !== archived) { current.archived = archived; this.event(state, archived ? 'scenario.archived' : 'scenario.restored', id, {version: expectedVersion}); }
      return current;
    });
  }
  async recordRun(payload, report, error = null, scenario = null) {
    payload = validateInput(payload);
    if ((report === null) === (error === null)) throw new Error('Store a completed result or failure, not both.');
    if (report !== null && (!report || typeof report !== 'object' || Array.isArray(report))) throw new Error('Run report must be an object.');
    if (new TextEncoder().encode(canonical(report)).length > 16 * 1024 * 1024) throw new Error('Report exceeds the 16 MB workspace storage limit.');
    error = error === null ? null : text(error, 'Failure description', 500);
    const record = {run_id: this.makeId(), project_id: this.projectId, status: error ? 'failed' : 'succeeded', payload,
      report: report ? clone(report) : null, error: error ? text(error, 'Failure description', 500) : null,
      started_at: report?.provenance?.executed_at || this.clock(), finished_at: this.clock(),
      mode: 'local', review_status: 'unreviewed', review_version: 0, scenario_id: scenario?.scenario_id || null, scenario_version: scenario?.version || null};
    return this.storage.update(state => {
      if (Object.keys(state.executions).length >= 1000) throw new Error('This browser workspace holds at most 1,000 runs. Export your workspace before clearing browser storage.');
      if (scenario) {
        const current = state.scenarios[scenario.scenario_id];
        const revision = state.revisions[scenario.scenario_id]?.find(item => item.version === scenario.version);
        if (!current || current.archived || !revision || canonical(revision.payload) !== canonical(payload)) throw new Error('Execution does not match an active saved scenario revision.');
      }
      state.executions[record.run_id] = record;
      this.event(state, 'execution.' + record.status, record.run_id, {input_sha256: report?.provenance?.input_sha256 || null});
      return record;
    });
  }
  async listRuns() {
    const state = await this.storage.read();
    return Object.values(state.executions).sort((a, b) => b.started_at.localeCompare(a.started_at)).slice(0, 100).map(({payload, report, ...record}) => ({...record, summary: report?.summary || ''}));
  }
  async getRun(id) {
    const state = await this.storage.read();
    if (!Object.hasOwn(state.executions, id)) throw new Error('Execution not found.');
    return state.executions[id];
  }
  async reviewRun(id, decision, reviewer, note, expectedVersion) {
    reviewer = text(reviewer, 'Reviewer', 100); note = text(note, 'Review rationale', 2000);
    return this.storage.update(state => {
      const current = Object.hasOwn(state.executions, id) ? state.executions[id] : null;
      if (!current) throw new Error('Execution not found.');
      if (current.status !== 'succeeded') throw new Error('Only successful executions can be reviewed.');
      if (current.review_version !== expectedVersion) throw new Error('The review changed. Reload before deciding.');
      if (!REVIEW_TRANSITIONS[current.review_status]?.includes(decision)) throw new Error('This review transition is not permitted.');
      const previous = current.review_status;
      current.review_status = decision; current.review_version++;
      this.event(state, 'execution.reviewed', id, {from: previous, to: decision, reviewer, note, review_version: current.review_version});
      return current;
    });
  }
  async compare(left, right) { return compareRuns(await this.getRun(left), await this.getRun(right)); }
  async audit() { return (await this.storage.read()).audit.slice(-100).reverse(); }
  async diagnostics() {
    const state = await this.storage.read();
    return {storage: 'IndexedDB in this browser', schema_version: 1, scenarios: Object.keys(state.scenarios).length, executions: Object.keys(state.executions).length, audit_events: state.audit.length};
  }
  async exportWorkspace() { return {format: 'application-workspace/v1', project_id: this.projectId, exported_at: this.clock(), ...(await this.storage.read())}; }
}

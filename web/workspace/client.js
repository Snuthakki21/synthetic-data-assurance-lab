/** Native workspace transport; credentials remain in memory, never URLs/storage. */
export class NativeWorkspaceClient {
  constructor(projectId, transport = fetch) { this.projectId = projectId; this.transport = transport; this.token = null; this.kind = 'native'; }
  setToken(token) { this.token = token || null; }
  async request(path, body = undefined, signal = undefined) {
    const headers = {'Content-Type': 'application/json'};
    if (this.token) headers.Authorization = 'Bearer ' + this.token;
    const transport = this.transport;
    const response = await transport('/api/v1/' + path, {method: body === undefined ? 'GET' : 'POST', headers, body: body === undefined ? undefined : JSON.stringify(body), signal});
    const value = await response.json();
    if (!response.ok) throw new Error(value.error || `Workspace request failed (${response.status}).`);
    return value;
  }
  async saveScenario(name, payload, scenarioId = null, expectedVersion = null) {
    const body = {project_id: this.projectId, name, payload};
    if (scenarioId) Object.assign(body, {scenario_id: scenarioId, expected_version: expectedVersion});
    return this.request('scenarios', body);
  }
  async listScenarios(includeArchived = false) { return (await this.request(`scenarios?project_id=${encodeURIComponent(this.projectId)}&archived=${includeArchived}`)).items; }
  getScenario(id, version = null) { return this.request('scenarios/' + encodeURIComponent(id) + (version === null ? '' : '?version=' + version)); }
  archiveScenario(id, expectedVersion, archived = true) { return this.request('scenarios/' + encodeURIComponent(id) + '/archive', {expected_version: expectedVersion, archived}); }
  execute(payload, signal, scenario = null) { return this.request('executions', {project_id: this.projectId, payload, idempotency_key: crypto.randomUUID(), ...(scenario ? {scenario_id: scenario.scenario_id, scenario_version: scenario.version} : {})}, signal); }
  async listRuns() { return (await this.request('executions?project_id=' + encodeURIComponent(this.projectId))).items; }
  getRun(id) { return this.request('executions/' + encodeURIComponent(id)); }
  reviewRun(id, decision, reviewer, note, expectedVersion) { return this.request('executions/' + encodeURIComponent(id) + '/review', {decision, reviewer, note, expected_version: expectedVersion}); }
  compare(left, right) { return this.request('compare?left=' + encodeURIComponent(left) + '&right=' + encodeURIComponent(right)); }
  async audit() { return (await this.request('audit')).items; }
  diagnostics() { return this.request('diagnostics'); }
  async exportWorkspace() {
    const scenarios = await this.listScenarios(true), runs = await this.listRuns();
    return {format: 'application-workspace-export/v1', project_id: this.projectId, exported_at: new Date().toISOString(),
      scope: 'Current scenario revisions and the most recent 100 runs; use the native database backup for complete retained history.',
      scenarios: await Promise.all(scenarios.map(item => this.getScenario(item.id))),
      executions: await Promise.all(runs.map(item => this.getRun(item.run_id))), audit: await this.audit()};
  }
}

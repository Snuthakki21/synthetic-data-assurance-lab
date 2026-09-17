/** IndexedDB commits the complete mutation atomically, including optimistic checks. */
const emptyState = () => ({schema_version: 1, scenarios: {}, revisions: {}, executions: {}, audit: []});
const copy = value => structuredClone(value);

export class IndexedDBStateStorage {
  constructor(name, indexedDBFactory = indexedDB) {
    this.name = name;
    this.factory = indexedDBFactory;
    this.database = null;
  }
  async open() {
    if (this.database) return this.database;
    this.database = await new Promise((resolve, reject) => {
      const request = this.factory.open(this.name, 1);
      request.onupgradeneeded = () => request.result.createObjectStore('workspace');
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(new Error('Browser workspace storage could not open. Check browser storage permissions.'));
      request.onblocked = () => reject(new Error('Close older tabs for this application before opening the new workspace version.'));
    });
    this.database.onversionchange = () => { this.database.close(); this.database = null; };
    return this.database;
  }
  async read() {
    const database = await this.open();
    return new Promise((resolve, reject) => {
      const transaction = database.transaction('workspace', 'readonly');
      const request = transaction.objectStore('workspace').get('state');
      request.onsuccess = () => resolve(copy(request.result || emptyState()));
      request.onerror = () => reject(new Error('Could not read browser workspace.'));
    });
  }
  async update(mutator) {
    const database = await this.open();
    return new Promise((resolve, reject) => {
      const transaction = database.transaction('workspace', 'readwrite');
      const store = transaction.objectStore('workspace');
      const request = store.get('state');
      let result, failure;
      request.onsuccess = () => {
        try {
          const state = request.result || emptyState();
          if (state.schema_version !== 1) throw new Error('Workspace format is newer than this application.');
          result = mutator(state);
          if (result && typeof result.then === 'function') throw new Error('Storage mutations must complete synchronously.');
          store.put(state, 'state');
        } catch (error) { failure = error; transaction.abort(); }
      };
      transaction.oncomplete = () => resolve(copy(result));
      transaction.onerror = () => reject(failure || new Error('Workspace could not be saved. Storage may be full; export your existing records before clearing browser data.'));
      transaction.onabort = () => reject(failure || new Error('Workspace transaction was interrupted. No change was committed.'));
    });
  }
}

/** Deterministic adapter for domain-contract tests; production uses IndexedDB. */
export class MemoryStateStorage {
  constructor() { this.state = emptyState(); }
  async read() { return copy(this.state); }
  async update(mutator) {
    const candidate = copy(this.state);
    const result = mutator(candidate);
    this.state = candidate;
    return copy(result);
  }
}

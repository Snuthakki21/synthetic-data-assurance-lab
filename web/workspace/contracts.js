/** Workspace value contracts, exact metric differences and review transitions. */
export const REVIEW_TRANSITIONS = Object.freeze({
  unreviewed: ['approved', 'needs_changes', 'rejected'],
  needs_changes: ['approved', 'rejected'], approved: ['needs_changes'], rejected: ['needs_changes'],
});
export const clone = value => JSON.parse(JSON.stringify(value));
export const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

export function canonical(value) {
  if (typeof value === 'number' && !Number.isFinite(value)) throw new Error('Non-finite numbers cannot be stored.');
  if (value === undefined || typeof value === 'function' || typeof value === 'symbol' || typeof value === 'bigint') throw new Error('Workspace values must be JSON.');
  if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
  if (value && typeof value === 'object') return '{' + Object.keys(value).sort().map(key => JSON.stringify(key) + ':' + canonical(value[key])).join(',') + '}';
  return JSON.stringify(value);
}
export function validateInput(value) {
  if (!value || Array.isArray(value) || typeof value !== 'object') throw new Error('Scenario input must be an object.');
  const text = canonical(value);
  if (new TextEncoder().encode(text).length > 262144) throw new Error('Scenario input exceeds 256 KB.');
  return JSON.parse(text);
}
export function text(value, label, maximum = 120) {
  if (typeof value !== 'string' || !value.trim() || value.trim().length > maximum) throw new Error(`${label} must contain 1–${maximum} characters.`);
  return value.trim();
}
function decimal(value) {
  if (!['string', 'number'].includes(typeof value)) return null;
  const match = String(value).match(/^([+-]?)(\d+)(?:\.(\d*))?(?:e([+-]?\d+))?$/i);
  if (!match || String(value).length > 1000) return null;
  const exponent = Number(match[4] || 0);
  if (!Number.isInteger(exponent) || Math.abs(exponent) > 1000) return null;
  return {coefficient: BigInt((match[1] === '-' ? '-' : '') + match[2] + (match[3] || '')), scale: (match[3] || '').length - exponent};
}
export function numericDelta(before, after) {
  const a = decimal(before), b = decimal(after);
  if (!a || !b) return null;
  const scale = Math.max(a.scale, b.scale, 0);
  const difference = b.coefficient * 10n ** BigInt(scale - b.scale) - a.coefficient * 10n ** BigInt(scale - a.scale);
  const negative = difference < 0n;
  let digits = (negative ? -difference : difference).toString().padStart(scale + 1, '0');
  if (scale) digits = (digits.slice(0, -scale) + '.' + digits.slice(-scale)).replace(/0+$/, '').replace(/\.$/, '');
  return (negative ? '-' : '') + digits;
}
export function compareRuns(left, right, maximumChanges = 200) {
  if (left.project_id !== right.project_id) throw new Error('Compare runs from the same application.');
  if (left.status !== 'succeeded' || right.status !== 'succeeded') throw new Error('Both runs must have succeeded.');
  const changes = [];
  function visit(a, b, path) {
    if (changes.length > maximumChanges || canonical(a) === canonical(b)) return;
    if (a && b && typeof a === 'object' && typeof b === 'object' && !Array.isArray(a) && !Array.isArray(b)) {
      for (const key of [...new Set([...Object.keys(a), ...Object.keys(b)])].sort()) {
        const target = path + '[' + JSON.stringify(key) + ']';
        if (!Object.hasOwn(a, key)) changes.push({path: target, kind: 'added', after: b[key]});
        else if (!Object.hasOwn(b, key)) changes.push({path: target, kind: 'removed', before: a[key]});
        else visit(a[key], b[key], target);
        if (changes.length > maximumChanges) break;
      }
    } else changes.push({path, kind: 'changed', before: a, after: b});
  }
  visit(left.payload, right.payload, '$');
  const metricMap = values => {
    const result = new Map(), reserved = new Set(values.map((metric,index) => metric.label || `Metric ${index + 1}`));
    values.forEach((metric, index) => {
      let key = metric.label || `Metric ${index + 1}`;
      if (result.has(key)) {const base=key;let suffix=index+1;do {key=`${base} [${suffix++}]`;} while(result.has(key)||reserved.has(key));}
      result.set(key, metric);
    });
    return result;
  };
  const a = metricMap(left.report.metrics), b = metricMap(right.report.metrics);
  return {left_run_id: left.run_id, right_run_id: right.run_id, project_id: left.project_id,
    input_changes: changes.slice(0, maximumChanges), input_changes_truncated: changes.length > maximumChanges,
    metrics: [...new Set([...a.keys(), ...b.keys()])].sort().map(label => {
      const before = a.get(label) || null, after = b.get(label) || null;
      return {label, before, after, numeric_delta: before && after && before.unit === after.unit ? numericDelta(before.value, after.value) : null};
    }), before_summary: left.report.summary, after_summary: right.report.summary,
    interpretation: 'Observed differences between these inputs and runs; not causal attribution or statistical significance.'};
}

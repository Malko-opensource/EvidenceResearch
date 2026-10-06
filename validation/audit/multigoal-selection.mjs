/* Pure state regression reproduction: no browser, files, workspace or server mutations. */
import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const project = new URL('../../', import.meta.url);
const viewModel = await readFile(new URL('research_cli/web/view_model.js', project), 'utf8');
let source = await readFile(new URL('research_cli/web/app.js', project), 'utf8');
source = source.replace("from './view_model.js'", `from ${JSON.stringify('data:text/javascript,' + encodeURIComponent(viewModel))}`);
source = source.replace(/\nstart\(\);\s*$/u, '\nexport {state, present};\n');
const elements = new Map();
class Element {
  constructor() { this.dataset = {}; this.hidden = false; this.textContent = ''; }
  append() {} replaceChildren() {} setAttribute() {} querySelectorAll() { return []; }
}
globalThis.document = {body: new Element(), createElement: () => new Element(),
  createElementNS: () => new Element(), querySelectorAll: () => [], getElementById(id) {
  if (!elements.has(id)) elements.set(id, new Element());
  return elements.get(id);
}};
globalThis.matchMedia = () => ({matches: true});
const actualRecord = JSON.parse(await readFile(new URL('validation/agent-web-0.6.0/record.json', project), 'utf8')).data;
const recordB = structuredClone(actualRecord);
recordB.registration.goal_id = 'goal-B';
recordB.registration.id = 'registration-B';
recordB.hypothesis.goal_id = 'goal-B';
recordB.run.registration_id = 'registration-B';
recordB.evidence.forEach(evidence => evidence.registration_id = 'registration-B');
recordB.decision.registration_id = 'registration-B';
const goalB = {id: 'goal-B', title: 'Goal B test fixture', version: 1, state: 'active'};
const summaryB = {id: 'registration-B', execution: 'succeeded', verification: 'passed', decision: 'adopted'};
const requests = [];
globalThis.fetch = async (path, options = {}) => {
  requests.push(path);
  const url = new URL(path, 'http://127.0.0.1:8766');
  const incorrect = url.searchParams.get('goal') === 'goal-A' && url.searchParams.get('registration') === 'registration-B';
  let result;
  if (incorrect) result = {ok: false, error: {code: 'INVALID_INPUT', message: 'Selected registration does not belong to selected goal'}};
  else if (url.pathname === '/api/snapshot') result = {ok: true, data: {
    status: {revision: recordB.revision, goals: [goalB], registrations: [summaryB], hypotheses: [recordB.hypothesis]},
    registration: 'registration-B', report: {goal: goalB, records: [recordB]}}};
  else if (url.pathname === '/api/call') {
    const {tool} = JSON.parse(options.body);
    result = {ok: true, data: tool === 'research_show' ? recordB : {items: [], total: 0, revision: recordB.revision}};
  } else result = {ok: false, error: {code: 'UNEXPECTED_TEST_PATH', message: path}};
  return {json: async () => result};
};
const {state, present} = await import('data:text/javascript,' + encodeURIComponent(source));
Object.assign(state, {workspace: 'dedicated-audit', goalSelection: 'goal-A', selected: 'registration-A', token: 'local-test'});
const result = await present('research_view', {scene: 'overview', registration: 'registration-B'});
console.log(JSON.stringify({test: 'select another goal registration without redundant goal parameter',
  request: requests[0], selected: state.selected, goalSelection: state.goalSelection,
  result: {ok: result.ok, error: result.error, reportedGoal: result.data?.presentation?.goal}}, null, 2));
assert.equal(result.ok, true);
assert.equal(state.goalSelection, 'goal-B');
assert.ok(!new URL(requests[0], 'http://127.0.0.1').searchParams.has('goal'));

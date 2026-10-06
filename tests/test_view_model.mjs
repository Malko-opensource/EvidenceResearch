/* Presentation-only variants below are test fixtures, never stored research results. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';

const source = await readFile(new URL('../research_cli/web/view_model.js', import.meta.url), 'utf8');
const {buildViewModel, compareRecords, clipText, labelState, interpretMetric, repeatModels} = await import(`data:text/javascript,${encodeURIComponent(source)}`);
const readFixture = async (name) => JSON.parse(await readFile(new URL(`../validation/agent-web-0.6.0/${name}.json`, import.meta.url), 'utf8')).data;
const actualRecord = await readFixture('record');
const actualStatus = await readFixture('status');
const actualMemory = await readFixture('memory');
const reportDemoTranscript = (await readFile(new URL('../validation/research-report-0.8.0/skill-demo/cli-transcript.jsonl', import.meta.url), 'utf8'))
  .trim().split('\n').map(line => JSON.parse(line));
const reportDemoRecord = reportDemoTranscript.filter(call => call.argv.includes('run') && call.argv.includes('--full'))
  .map(call => JSON.parse(call.stdout)).filter(result => result.ok && result.data?.record).at(-1).data.record;
const clone = (value) => structuredClone(value);
const modelFor = (record = clone(actualRecord), extras = {}) => buildViewModel({record,
  snapshot: {status: clone(actualStatus), events: [], event_total: 0}, goal: clone(actualStatus.goals[0]),
  memory: clone(actualMemory), workspace: 'agent-observatory-20261004', ...extras});
const deepFreeze = (value) => {
  if (value && typeof value === 'object') {
    Object.values(value).forEach(deepFreeze); Object.freeze(value);
  }
  return value;
};
const criteriaVariant = (record, criteria, metrics) => {
  record.registration.spec.metrics = Object.keys(metrics);
  record.registration.spec.criteria = criteria;
  record.verification.metrics = metrics;
  const evaluate = {'>': (a, b) => a > b, '>=': (a, b) => a >= b, '<': (a, b) => a < b,
    '<=': (a, b) => a <= b, '==': (a, b) => a === b, '!=': (a, b) => a !== b};
  record.verification.details.criteria_results = criteria.map((criterion) => ({...criterion,
    actual: metrics[criterion.metric], passed: evaluate[criterion.op](metrics[criterion.metric], criterion.threshold)}));
  record.verification.state = record.verification.details.criteria_results.every((criterion) => criterion.passed) ? 'passed' : 'failed';
  return record;
};
const anotherRegistration = (record, registration = 'test-registration-second') => {
  record.registration.id = registration;
  record.run.registration_id = registration;
  record.evidence.forEach((evidence) => { evidence.registration_id = registration; });
  record.decision.registration_id = registration;
  return record;
};

test('saved actual record remains traceable and distinguishes registered metrics from artifact numbers', () => {
  const model = modelFor();
  assert.equal(model.question.title, actualStatus.goals[0].title);
  assert.equal(model.question.hypothesis, actualRecord.hypothesis.statement);
  assert.equal(model.metrics.length, 1);
  assert.equal(model.metrics[0].name, 'pass_rate');
  assert.equal(model.metrics[0].value, 1);
  assert.equal(model.metrics[0].unit, '단위 미등록');
  assert.equal(model.metrics[0].criteria[0].threshold, 1);
  assert.equal(model.metrics[0].criteria[0].passed, true);
  assert.equal(model.trust.supported, true);
  assert.equal(model.trust.tone, 'good');
  assert.equal(model.trust.validCount, 6);
  assert.deepEqual(model.states, {execution: 'succeeded', verification: 'passed', decision: 'adopted'});
  assert.ok(model.refs.some((ref) => ref.registration === actualRecord.registration.id && ref.field === 'verification.metrics.pass_rate'));
  assert.ok(!model.metrics.some((metric) => ['mean', 'variance'].includes(metric.name)));
});

test('actual CSV demonstration prioritizes the unmet business criterion without reordering registered metrics or guessing units', () => {
  const input = deepFreeze(clone(reportDemoRecord)), before = JSON.stringify(input);
  const model = modelFor(input);
  assert.deepEqual(model.metrics.map(metric => metric.name), ['calculation_matches', 'satisfaction_pct']);
  assert.equal(model.metrics[0].value, 1);
  assert.equal(model.metrics[0].criteria[0].passed, true);
  assert.equal(model.primaryMetric.name, 'satisfaction_pct');
  assert.equal(model.primaryMetric.value, 72);
  assert.equal(model.primaryMetric.supported, true);
  assert.equal(model.primaryMetric.unit, '단위 미등록');
  assert.equal(model.primaryMetric.criteria[0].threshold, 80);
  assert.equal(model.primaryMetric.criteria[0].passed, false);
  assert.equal(model.primaryMetricSelection.method, 'unmet_registered_criterion');
  assert.equal(model.primaryMetricSelection.reason, '미충족 등록 기준 우선');
  assert.equal(model.primaryMetricSelection.refs[0].field, 'registration.spec.criteria[1]');
  assert.equal(model.primaryMetricSelection.refs[0].goal_version, input.registration.goal_version);
  assert.equal(model.primaryMetricSelection.refs[0].revision, input.revision);
  assert.equal(JSON.stringify(input), before);
});

test('an explicit registered primary metric takes precedence while unsupported historical failures do not', () => {
  const explicit = clone(reportDemoRecord);
  explicit.registration.spec.primary_metric = 'calculation_matches';
  const selected = modelFor(explicit);
  assert.equal(selected.primaryMetric.name, 'calculation_matches');
  assert.equal(selected.primaryMetricSelection.method, 'registered_primary');
  assert.equal(selected.primaryMetricSelection.refs[0].field, 'registration.spec.primary_metric');
  const stale = clone(reportDemoRecord);
  stale.evidence.find(evidence => evidence.name === 'summary').integrity = 'tampered';
  const historical = modelFor(stale);
  assert.equal(historical.primaryMetric.name, 'calculation_matches');
  assert.equal(historical.primaryMetricSelection.method, 'registration_order');
  assert.equal(historical.primaryMetric.supported, false);
  assert.equal(historical.metrics[1].criteria[0].passed, null);
});

test('deeply frozen raw inputs are not modified or returned as mutable raw references', () => {
  const input = deepFreeze({record: clone(actualRecord), snapshot: {status: clone(actualStatus)},
    goal: clone(actualStatus.goals[0]), memory: clone(actualMemory), records: [clone(actualRecord)], workspace: 'test'});
  const before = JSON.stringify(input);
  const model = buildViewModel(input);
  compareRecords(input.records);
  model.metrics[0].criteria[0].threshold = 999;
  model.question.refs[0].field = 'test-change';
  assert.equal(JSON.stringify(input), before);
});

test('numbers and an adopted decision alone cannot create independently supported measurements', () => {
  const record = clone(actualRecord);
  record.verification = null; record.evidence = [];
  const model = modelFor(record);
  assert.equal(model.trust.supported, false);
  assert.notEqual(model.trust.tone, 'good');
  assert.equal(model.metrics[0].value, null);
  assert.equal(model.metrics[0].criteria[0].passed, null);
  assert.equal(model.states.decision, 'adopted');
});

test('current tampering invalidates support while historical passed/adopted states remain explicit', () => {
  const record = clone(actualRecord);
  record.evidence.find((evidence) => evidence.name === 'result').integrity = 'tampered';
  const model = modelFor(record);
  assert.equal(model.trust.invalidCount, 1);
  assert.equal(model.trust.supported, false);
  assert.equal(model.trust.tone, 'warn');
  assert.equal(model.states.verification, 'passed');
  assert.equal(model.states.decision, 'adopted');
  assert.equal(model.metrics[0].value, 1);
  assert.equal(model.metrics[0].supported, false);
  assert.equal(model.metrics[0].criteria[0].passed, null);
  assert.match(model.trust.text, /과거/);
});

test('missing files and absent registered artifact evidence are each unsupported', () => {
  const missing = clone(actualRecord);
  missing.evidence.find((evidence) => evidence.name === 'result').integrity = 'missing';
  assert.equal(modelFor(missing).trust.supported, false);
  assert.equal(modelFor(missing).trust.invalidCount, 1);
  const absent = clone(actualRecord);
  absent.evidence = absent.evidence.filter((evidence) => evidence.name !== 'result');
  assert.equal(modelFor(absent).trust.supported, false);
  assert.equal(modelFor(absent).metrics[0].supported, false);
});

test('current tampering or missing files require a presentation blocker even after durable adoption', () => {
  for (const integrity of ['tampered', 'missing']) {
    const record = clone(actualRecord);
    const evidence = record.evidence.find((item) => item.name === 'result');
    evidence.integrity = integrity;
    const status = deepFreeze(clone(actualStatus));
    const original = JSON.stringify(status);
    const model = modelFor(record, {snapshot: {status}});
    assert.equal(model.states.decision, 'adopted');
    assert.deepEqual(status.registrations[0].missing_evidence, []);
    assert.equal(JSON.stringify(status), original);
    assert.match(model.blockers[0].text, /복원 또는 원본 대조/);
    assert.equal(model.blockers[0].ref.field, 'evidence.integrity');
    assert.equal(model.blockers[0].ref.evidence, evidence.id);
    assert.ok(model.blockers[0].ref.evidence_ids.includes(evidence.id));
    evidence.integrity = 'valid';
    assert.ok(!modelFor(record, {snapshot: {status}}).blockers.some((blocker) => blocker.ref.field === 'evidence.integrity'));
  }
});

test('run, registration, fixed validator, and pinned source linkage cannot be silently substituted', () => {
  for (const mutate of [
    (record) => { record.verification.run_id = 'another-run'; },
    (record) => { record.run.registration_id = 'another-registration'; },
    (record) => { record.verification.details.validator_sha256 = 'b'.repeat(64); },
    (record) => { record.registration.spec.source_version.files['task.py'] = 'b'.repeat(64); },
    (record) => { record.evidence.find((evidence) => evidence.name === 'result').run_id = 'another-run'; }
  ]) {
    const record = clone(actualRecord); mutate(record);
    const model = modelFor(record);
    assert.equal(model.trust.supported, false);
    assert.equal(model.metrics[0].supported, false);
  }
});

test('negative values and multiple registered criteria retain their exact operators and failed facts', () => {
  const record = criteriaVariant(clone(actualRecord), [
    {metric: 'signed_error', op: '>=', threshold: -2},
    {metric: 'signed_error', op: '<=', threshold: 0}
  ], {signed_error: -3});
  const model = modelFor(record);
  assert.equal(model.metrics[0].value, -3);
  assert.deepEqual(model.metrics[0].criteria.map((criterion) => criterion.passed), [false, true]);
  assert.deepEqual(model.metrics[0].criteria.map((criterion) => criterion.op), ['>=', '<=']);
  assert.equal(model.metrics[0].supported, true);
  assert.equal(model.trust.supported, false);
  assert.equal(model.trust.tone, 'bad');
  assert.match(model.trust.text, /독립 검증에서 등록 기준 미달/);
  assert.ok(model.metrics[0].domain[0] < -3 && model.metrics[0].domain[1] > 0);
});

test('equality and inequality criteria are preserved without inventing a ranking direction', () => {
  const record = criteriaVariant(clone(actualRecord), [
    {metric: 'signed_error', op: '==', threshold: -3},
    {metric: 'signed_error', op: '!=', threshold: -4}
  ], {signed_error: -3});
  const metric = modelFor(record).metrics[0];
  assert.deepEqual(metric.criteria.map((criterion) => criterion.op), ['==', '!=']);
  assert.deepEqual(metric.criteria.map((criterion) => criterion.passed), [true, true]);
  assert.ok(!('rank' in metric));
});

test('non-finite and boolean values are missing measurements; extreme finite domains remain finite', () => {
  for (const value of [NaN, Infinity, -Infinity, true, '1']) {
    const record = clone(actualRecord); record.verification.metrics.pass_rate = value;
    const metric = modelFor(record).metrics[0];
    assert.equal(metric.value, null);
    assert.equal(metric.supported, false);
    assert.equal(metric.criteria[0].passed, null);
  }
  const extreme = criteriaVariant(clone(actualRecord), [{metric: 'extreme', op: '>=', threshold: Number.MAX_VALUE}], {extreme: Number.MAX_VALUE});
  assert.ok(modelFor(extreme).metrics[0].domain.every(Number.isFinite));
});

test('only explicit preregistered unit metadata supplies a metric unit', () => {
  const record = clone(actualRecord);
  record.registration.spec.metric_units = {pass_rate: '비율'};
  assert.equal(modelFor(record).metrics[0].unit, '비율');
  assert.equal(modelFor(record).metrics[0].value, 1);
});

test('unknown external usage stays unknown while explicitly measured zero is a known value', () => {
  const unknown = modelFor().resources;
  assert.equal(unknown.find((resource) => resource.label === '외부 모델 사용').known, false);
  assert.equal(unknown.find((resource) => resource.label === '외부 토큰 사용').value, '미확인');
  const record = clone(actualRecord);
  record.run.resources.external_tokens = 0;
  record.run.resources.wall_seconds = 0;
  const zero = modelFor(record).resources;
  assert.equal(zero.find((resource) => resource.label === '외부 토큰 사용').known, true);
  assert.equal(zero.find((resource) => resource.label === '외부 토큰 사용').value, '0 토큰');
  assert.equal(zero.find((resource) => resource.label === '실행 경과 시간').value, '0초');
});

test('internally inconsistent verifier state or criterion report cannot mark an observed threshold as satisfied', () => {
  const stateConflict = clone(actualRecord); stateConflict.verification.state = 'failed';
  const stateModel = modelFor(stateConflict);
  assert.equal(stateModel.metrics[0].supported, false);
  assert.equal(stateModel.metrics[0].criteria[0].passed, null);
  assert.doesNotMatch(stateModel.trust.text, /기준 미달이 확인/);
  const reportConflict = clone(actualRecord); reportConflict.verification.details.criteria_results[0].actual = 999;
  const reportModel = modelFor(reportConflict);
  assert.equal(reportModel.trust.supported, false);
  assert.equal(reportModel.metrics[0].criteria[0].passed, null);
});

test('distribution counts only this status page and does not present it as the entire store', () => {
  const status = {...clone(actualStatus), offset: 20, total: 100, registrations: [
    {id: 'test-1', execution: 'succeeded', verification: 'passed', decision: 'adopted'},
    {id: 'test-2', execution: 'succeeded', verification: 'failed', decision: 'rejected'},
    {id: 'test-3', execution: 'unknown', verification: 'pending', decision: 'pending'}]};
  const model = modelFor(null, {snapshot: {status}});
  assert.deepEqual(model.scope, {count: 3, total: 100, offset: 20, label: '이 조회 3건 / 전체 등록 100건 · 21–23번째'});
  for (const dimension of Object.values(model.distribution)) assert.equal(dimension.reduce((sum, entry) => sum + entry.count, 0), 3);
  assert.equal(model.distribution.execution.find((entry) => entry.key === 'unknown').count, 1);
});

test('real timestamps, event query limits, exact missing evidence, and revision skew remain explicit', () => {
  const record = clone(actualRecord); record.revision = 9;
  const status = clone(actualStatus);
  status.registrations[0].missing_evidence = ['independent verification', 'test unrecognized missing evidence'];
  const model = modelFor(record, {snapshot: {status, event_total: 80, events: [
    {id: 8, action: 'decision.create', created: actualRecord.decision.created, revision: 8},
    {id: 6, action: 'run.complete', created: actualRecord.run.finished, revision: 6}]}});
  assert.equal(model.timeline.items[0].created, actualRecord.run.finished);
  assert.equal(model.timeline.total, 80);
  assert.match(model.timeline.label, /2건 \/ 전체 80건/);
  assert.equal(model.blockers[0].text, '독립 검증');
  assert.equal(model.blockers[0].ref.value, 'independent verification');
  assert.equal(model.blockers[1].text, 'test unrecognized missing evidence');
  assert.ok(model.blockers.some((item) => item.ref.field === 'revision' && item.ref.revision === 9));
});

test('selected-registration event scope is disclosed instead of claiming a workspace-wide timeline', () => {
  const registration = actualRecord.registration.id;
  const model = modelFor(undefined, {snapshot: {status: clone(actualStatus), event_scope: 'selected_registration',
    registration, event_total: 8, events: [{id: 6, action: 'run.complete', revision: 6, created: actualRecord.run.finished}]}});
  assert.equal(model.timeline.label, '선택 실험 연결 사건 1건 / 전체 연결 8건');
  assert.equal(model.timeline.total, 8);
  assert.ok(model.refs.some((ref) => ref.field === 'snapshot.registration' && ref.registration === registration &&
    ref.event_scope === 'selected_registration'));
  const workspaceModel = modelFor(undefined, {snapshot: {status: clone(actualStatus), event_total: 44, events: []}});
  assert.equal(workspaceModel.timeline.label, '최근 조회 사건 0건 / 전체 44건');
});

test('memory failure remains a failed verification record, not an unknown execution or unsupported success', () => {
  const memory = clone(actualMemory);
  memory.items.push({...clone(memory.items[0]), id: 'test-failure-fixture', outcome: 'failure', verification: 'failed',
    decision: 'rejected', claim_verified: false, reason: 'Test fixture: registered criterion was not met.'});
  memory.items.push({...clone(memory.items[0]), id: 'test-unknown-fixture', outcome: 'inconclusive', execution: 'unknown',
    verification: 'pending', decision: 'pending', claim_verified: false});
  const lessons = modelFor(undefined, {memory}).lessons;
  assert.match(lessons[1].claimText, /독립 검증 실패 기록/);
  assert.equal(lessons[1].tone, 'bad');
  assert.match(lessons[2].claimText, /실행 미확정/);
  memory.items[0].evidence_integrity = 'invalid';
  memory.items[0].claim_verified = true;
  assert.equal(modelFor(undefined, {memory}).lessons[0].tone, 'warn');
});

test('duplicate reads and restored copies of one registration are not two experimental attempts', () => {
  const first = {...clone(actualRecord), workspace: 'original'};
  const restored = {...clone(actualRecord), workspace: 'restored-copy'};
  const cohorts = compareRecords([first, restored, first]);
  assert.equal(cohorts.length, 1);
  assert.equal(cohorts[0].items.length, 1);
  assert.equal(cohorts[0].comparable, false);
  assert.ok(cohorts[0].differences.some((difference) => difference.includes('반복 조회 2건')));
});

test('a foreign goal is not substituted for the selected registration and stale memory is disclosed', () => {
  const memory = clone(actualMemory); memory.revision = 7;
  const model = modelFor(undefined, {goal: {id: 'foreign', title: 'Wrong research question'}, memory});
  assert.equal(model.question.title, actualStatus.goals[0].title);
  assert.ok(model.blockers.some((blocker) => blocker.ref.field === 'memory.revision'));
});

test('comparable cohorts require at least two complete matching registrations and show source content changes', () => {
  const first = {...clone(actualRecord), workspace: 'source-a'};
  const second = {...anotherRegistration(clone(actualRecord)), workspace: 'source-b'};
  second.registration.spec.source_version.files['task.py'] = 'b'.repeat(64);
  const one = compareRecords([first]);
  assert.equal(one[0].comparable, false);
  assert.match(one[0].reason, /두 번째/);
  const cohorts = compareRecords([first, second]);
  assert.equal(cohorts.length, 1);
  assert.equal(cohorts[0].comparable, true);
  assert.ok(cohorts[0].differences.some((difference) => difference.includes('소스 파일 내용')));
  assert.equal(cohorts[0].items[0].refs[0].workspace, 'source-a');
  assert.equal(cohorts[0].items[1].refs[0].workspace, 'source-b');
  assert.ok(!('ranking' in cohorts[0]));
});

test('incompatible or incomplete experiments are separate groups with explicit condition differences', () => {
  for (const mutate of [
    (record) => { record.registration.spec.data_split = 'test: different evaluation input'; },
    (record) => { record.registration.spec.criteria[0].threshold = 0.5; },
    (record) => { record.registration.spec.conditions = {test_condition: 'different'}; },
    (record) => { record.registration.spec.validator_sha256 = 'b'.repeat(64); },
    (record) => { record.registration.spec.metric_units = {pass_rate: 'percent'}; },
    (record) => { record.registration.goal_id = 'different-research-question'; }
  ]) {
    const second = anotherRegistration(clone(actualRecord)); mutate(second);
    const cohorts = compareRecords([actualRecord, second]);
    assert.equal(cohorts.length, 2);
    assert.ok(cohorts.every((cohort) => !cohort.comparable));
    assert.ok(cohorts.every((cohort) => cohort.differences.length));
  }
  const incomplete = clone(actualRecord); delete incomplete.registration.spec.validator_sha256;
  assert.match(compareRecords([incomplete, clone(incomplete)])[0].reason, /미확인/);
  assert.ok(compareRecords([incomplete, clone(incomplete)]).every((cohort) => !cohort.comparable));
});

test('empty stores remain empty, and explanations clip by Unicode characters without fabricated progress', () => {
  const model = buildViewModel({snapshot: {status: {registrations: [], goals: [], hypotheses: [], total: 0, offset: 0}}, workspace: 'empty'});
  assert.equal(model.scope.count, 0);
  assert.equal(model.trust.supported, false);
  assert.equal(model.metrics.length, 0);
  assert.equal(model.lessons.length, 0);
  assert.equal(model.timeline.items.length, 0);
  assert.deepEqual(compareRecords([]), []);
  assert.equal(clipText('🙂🙂🙂🙂', 3), '🙂🙂…');
  assert.equal(clipText('a\n   b'), 'a b');
  assert.equal(labelState('unknown'), '실행 미확정');
  assert.equal(labelState('failed', 'verification'), '검증 실패');
  assert.ok(!('progress' in model));
  assert.ok(!('score' in model));
});

const reportingFixture = (changes = {}) => ({goal: {...clone(actualStatus.goals[0]), version: 2,
  state: 'active', state_source: 'explicit', created: 100, lifecycle: {id: 'life-active', goal_version: 2, created: 100}},
  observed_at: 250, scope: {kind: 'selected_goal_all_runs', registrations_total: 32, runs_total: 8},
  totals: {run_wall_seconds: {value: 900, known: 7, unknown: 1}},
  resources: {cost_by_currency: [{currency: 'USD', amount: 2.5}], known_count: 2, unknown_count: 1,
    scope: 'recorded_external_observations_only', tokens: {observed_subtotal: 42, known_count: 1, unknown_count: 2}},
  runs: [{id: 'actual-run', registration_id: actualRecord.registration.id, finished: 220,
    resources: {wall_seconds: 5}}, {id: 'pending-run', created: 230, finished: null, resources: {wall_seconds: null}}],
  resource_observations: [{id: 'observation', created: 210, registration_id: actualRecord.registration.id,
    record: {cost: {status: 'known', amount: 2.5, currency: 'USD'}}}], resource_observations_total: 3,
  records_total: 32, records: [clone(actualRecord)], ...changes});
const reportingModel = (report) => modelFor(clone(actualRecord), {snapshot: {status: clone(actualStatus), report, events: []}});

test('overall lifecycle remains separate from successful execution, verification and adoption', () => {
  const model = reportingModel(reportingFixture());
  assert.equal(model.report.state, 'active');
  assert.equal(model.states.execution, 'succeeded');
  assert.equal(model.states.verification, 'passed');
  assert.equal(model.states.decision, 'adopted');
  assert.equal(model.report.terminal, false);
  assert.equal(model.report.elapsedSeconds, 150);
  assert.equal(model.report.cost.complete, false);
  assert.match(model.report.cost.scope, /전체 비용은 미확인/);
});

test('ended or paused report foregrounds reasons, results and unfinished scope without making verification', () => {
  for (const state of ['completed', 'paused', 'cancelled']) {
    const report = reportingFixture();
    report.goal.state = state;
    report.goal.lifecycle = {id: 'closed', created: 180, reason: '실제 자원 제한', results: ['기준 미달의 원인 확인'],
      incomplete: ['새 데이터에 대한 일반화'], goal_version: 2};
    const record = clone(actualRecord); record.verification = null; record.evidence = [];
    const model = modelFor(record, {snapshot: {status: clone(actualStatus), report}});
    assert.equal(model.report.terminal, true);
    assert.equal(model.report.elapsedSeconds, 80);
    assert.equal(model.report.reason, '실제 자원 제한');
    assert.deepEqual(model.report.results, ['기준 미달의 원인 확인']);
    assert.deepEqual(model.report.incomplete, ['새 데이터에 대한 일반화']);
    assert.equal(model.trust.supported, false);
  }
});

test('legacy goal has unknown overall lifecycle; its adopted experiment does not close the research', () => {
  const model = modelFor();
  assert.equal(model.report.state, 'unknown');
  assert.equal(model.report.stateLabel, '전체 연구 상태 미확인');
  assert.equal(model.report.terminal, false);
  assert.equal(model.report.elapsedSeconds, null);
  assert.equal(model.report.cost.text, '비용 미확인');
});

test('cumulative execution time uses exact all-goal aggregate while trends disclose only observed runs', () => {
  const report = reportingFixture(), model = reportingModel(report);
  assert.equal(model.scope.count, 1);
  assert.equal(model.report.runTime.value, 900);
  assert.equal(model.report.runTime.known, 7);
  assert.equal(model.report.runTime.unknown, 1);
  assert.equal(model.report.trends.runs.length, 1);
  assert.equal(model.report.trends.runs[0].created, 220);
  assert.equal(model.report.trends.runs[0].value, 5);
  assert.equal(model.report.trends.runsTotal, 8);
  assert.equal(model.report.runTime.scope, '선택 목표의 전체 고유 실행');
});

test('explicit zero cost is a scoped known observation, absent or unknown cost is not zero', () => {
  const report = reportingFixture();
  report.resources = {cost_by_currency: [{currency: 'KRW', amount: 0}], known_count: 1, unknown_count: 3};
  const model = reportingModel(report);
  assert.equal(model.report.cost.text, '0 KRW');
  assert.equal(model.report.cost.known, 1);
  assert.equal(model.report.cost.unknown, 3);
  assert.equal(model.report.cost.complete, false);
  report.resources = {cost_by_currency: [], known_count: 0, unknown_count: 1};
  assert.equal(reportingModel(report).report.cost.text, '비용 미확인');
});

test('currencies remain separate, externally reported cost and token subtotals retain unknown full usage', () => {
  const report = reportingFixture(); report.resources.cost_by_currency.push({currency: 'KRW', amount: 1000});
  const model = reportingModel(report);
  assert.equal(model.report.cost.text, '2.5 USD · 1,000 KRW');
  assert.equal(model.report.cost.provenance, 'external_report');
  assert.equal(model.report.tokens.observedSubtotal, 42);
  assert.equal(model.report.tokens.unknown, 2);
  assert.match(model.report.tokens.scope, /전체 사용량은 미확인/);
  assert.equal(model.report.trends.costs.length, 1);
  assert.equal(model.report.trends.costs[0].value, 2.5);
  assert.equal(model.report.trends.observationsTotal, 3);
});

test('goal-relative interpretation converts only explicit ratio or percent units and retains criterion operator', () => {
  const metric = {name: 'unhelpful_name', value: 0.87, unit: 'ratio', supported: true,
    criteria: [{op: '>=', threshold: 0.9, passed: false}]};
  const interpretation = interpretMetric(metric);
  assert.equal(interpretation.value, 87);
  assert.equal(interpretation.criteria[0].target, 90);
  assert.equal(interpretation.criteria[0].delta, -3);
  assert.equal(interpretation.criteria[0].deltaUnit, '%p');
  assert.match(interpretation.text, /3 %p 낮음/);
  assert.match(interpretation.text, />=/);
  assert.equal(interpretMetric({...metric, unit: '단위 미등록'}).value, 0.87);
  assert.equal(interpretMetric({...metric, value: 87, unit: '%', criteria: [{op: '<=', threshold: 90}]}).value, 87);
  assert.equal(interpretMetric({...metric, value: null}).criteria[0].delta, null);
});

test('lower is not automatically worse and equality comparisons receive no invented ranking', () => {
  const metric = {value: 3, unit: 'seconds', supported: true, criteria: [{op: '<=', threshold: 5, passed: true}]};
  assert.match(interpretMetric(metric).text, /낮음/);
  assert.ok(!/부족|나쁨/.test(interpretMetric(metric).text));
  assert.equal(interpretMetric({...metric, criteria: [{op: '==', threshold: 5, passed: false}]}).criteria[0].op, '==');
});

test('semantic path edges are backed by actual record keys and absent connections remain pending', () => {
  const model = modelFor();
  assert.deepEqual(model.flow.nodes.map(node => node.key), ['hypothesis', 'experiment', 'evidence', 'verification', 'conclusion']);
  assert.ok(model.flow.edges.every(edge => edge.recorded));
  assert.equal(model.flow.edges[1].ref.field, 'evidence.run_id');
  const record = clone(actualRecord); record.evidence = []; record.verification = null; record.decision = null;
  const missing = modelFor(record);
  assert.deepEqual(missing.flow.edges.map(edge => edge.recorded), [true, false, false, false]);
  assert.equal(missing.flow.nodes[2].text, '연결된 실측 산출물 없음');
});

test('graph exposes unmet frozen criteria and gaps without treating execution failure as hypothesis refutation', () => {
  const record = criteriaVariant(clone(actualRecord), [{metric: 'pass_rate', op: '>=', threshold: 2}], {pass_rate: 1});
  record.decision.state = 'rejected';
  let model = modelFor(record);
  assert.equal(model.graph.conclusions[0].opposingRegisteredCriteria[0].actual, 1);
  assert.equal(model.graph.conclusions[0].opposingRegisteredCriteria[0].threshold, 2);
  assert.equal(model.graph.conclusions[0].support.length, 0);
  record.run.state = 'failed'; record.verification = null;
  model = modelFor(record);
  assert.equal(model.graph.conclusions[0].opposingRegisteredCriteria.length, 0);
  assert.ok(model.graph.conclusions[0].gaps.some(gap => gap.includes('가설 반박을 뜻하지 않음')));
});

test('graph duplicate reads and copies of one registration do not create extra branches or confirmation', () => {
  const model = modelFor(actualRecord, {records: [clone(actualRecord), clone(actualRecord)]});
  assert.equal(model.graph.shown, 1);
  assert.equal(model.graph.nodes.length, 5);
  assert.equal(model.graph.conclusions[0].independence, 'not_established');
  assert.equal(model.judgment.evidenceIndependence, 'not_established');
});

const repeatFixture = (index, value) => {
  const record = anotherRegistration(clone(actualRecord), `repeat-reg-${index}`);
  record.registration.spec.seed = index;
  record.registration.spec.conditions.repeat_design = 'fixed_input_replications';
  record.registration.spec.metric_units = {pass_rate: 'ratio'};
  record.run.id = `repeat-run-${index}`;
  record.verification.run_id = record.run.id;
  record.evidence.forEach(item => {item.run_id = record.run.id; item.id = `${item.id}-${index}`;});
  return criteriaVariant(record, [{metric: 'pass_rate', op: '>=', threshold: 0.5}], {pass_rate: value});
};

test('registered repeated actual measurements produce n, exact range, mean and descriptive sample SD', () => {
  const records = [repeatFixture(1, 0.6), repeatFixture(2, 0.8), repeatFixture(3, 1)], input = deepFreeze(records), before = JSON.stringify(input);
  const groups = repeatModels(input);
  assert.equal(groups.length, 1);
  assert.deepEqual(groups[0].seeds, [1, 2, 3]);
  const metric = groups[0].metrics[0];
  assert.equal(metric.n, 3); assert.ok(Math.abs(metric.mean - 0.8) < 1e-14);
  assert.equal(metric.min, 0.6); assert.equal(metric.max, 1);
  assert.ok(Math.abs(metric.sampleSd - 0.2) < 1e-14);
  assert.match(metric.uncertainty, /신뢰구간.*독립성 미확인/);
  assert.equal(groups[0].independence, 'not_established');
  assert.equal(JSON.stringify(input), before);
});

test('repeat distribution requires explicit preregistered repeat design and enough observed runs for variation', () => {
  assert.deepEqual(repeatModels([actualRecord]), []);
  const group = repeatModels([repeatFixture(1, 0.8)])[0];
  assert.equal(group.metrics[0].n, 1);
  assert.equal(group.metrics[0].sampleSd, null);
  assert.match(group.metrics[0].uncertainty, /반복 측정 부족/);
});

test('same original run is counted once and tampered or unexecuted records cannot fill repeat samples', () => {
  const first = repeatFixture(1, 0.6), second = repeatFixture(2, 0.8), bad = repeatFixture(3, 1);
  bad.evidence[0].integrity = 'tampered';
  const groups = repeatModels([first, clone(first), second, bad]);
  assert.equal(groups[0].metrics[0].n, 2);
  const pending = repeatFixture(4, 0.9); pending.run = null; pending.verification = null;
  assert.equal(repeatModels([first, pending])[0].metrics[0].n, 1);
});

test('repeat treatment, source content, dataset or registered criteria differences form separate distributions', () => {
  for (const mutate of [record => {record.registration.spec.source_version.files['solution.py'] = 'a'.repeat(64);},
    record => {record.registration.spec.change = 'another treatment';},
    record => {record.registration.spec.data_split = {evaluation: 'another split'};},
    record => {record.registration.spec.conditions.repeat_design = 'another design';}]) {
    const second = repeatFixture(2, 0.8); mutate(second);
    assert.equal(repeatModels([repeatFixture(1, 0.6), second]).length, 2);
  }
});

test('report source refs provide current revision and goal version without a fabricated progress score', () => {
  const model = reportingModel(reportingFixture());
  assert.ok(model.refs.every(ref => Object.hasOwn(ref, 'revision') && Object.hasOwn(ref, 'goal_version')));
  assert.equal(model.report.goalVersion, 2);
  assert.ok(model.refs.some(ref => ref.field === 'snapshot.report' && ref.goal_version === 2));
  assert.ok(!('progress' in model.report));
  assert.ok(!('qualityScore' in model.judgment));
});

test('nested chart, relation and judgment refs retain frozen registration goal version after goal amendment', () => {
  const report = reportingFixture(), record = clone(actualRecord);
  record.registration.goal_version = 1;
  const model = modelFor(record, {goal: {...clone(actualStatus.goals[0]), version: 2},
    snapshot: {status: clone(actualStatus), report: {...report, records: [record]}}});
  assert.equal(model.metrics[0].ref.goal_version, 1);
  assert.equal(model.flow.edges[0].ref.goal_version, 1);
  assert.equal(model.graph.conclusions[0].ref.goal_version, 1);
  assert.equal(model.report.goalVersion, 2);
  assert.equal(model.sourceVersion.registration_goal_version, 1);
  assert.equal(model.metrics[0].ref.registration_fingerprint, actualRecord.registration.fingerprint);
});

test('goal closure without a known closure time leaves elapsed unknown instead of continuing a fake elapsed clock', () => {
  const report = reportingFixture(); report.goal.state = 'completed'; delete report.goal.lifecycle.created;
  assert.equal(reportingModel(report).report.elapsedSeconds, null);
});

test('descriptive repeat mean stays finite for extreme finite observations and unsupported SD stays unknown', () => {
  const first = repeatFixture(1, 1e308), second = repeatFixture(2, 1e308);
  const metric = repeatModels([first, second])[0].metrics[0];
  assert.equal(metric.mean, 1e308);
  assert.equal(metric.sampleSd, 0);
});

test('frozen goal version mismatch remains visible and prevents pretending changed goals are one comparison cohort', () => {
  const first = repeatFixture(1, 0.6), second = repeatFixture(2, 0.8);
  first.registration.goal_version = 1; second.registration.goal_version = 2;
  assert.equal(repeatModels([first, second]).length, 2);
  assert.equal(compareRecords([first, second]).length, 2);
  const model = modelFor(first, {goal: {...clone(actualStatus.goals[0]), version: 2},
    snapshot: {status: clone(actualStatus), report: reportingFixture()}});
  assert.ok(model.blockers.some(blocker => blocker.text.includes('목표 버전 1')));
  assert.ok(model.judgment.unanswered.some(blocker => blocker.text.includes('적용 범위')));
});

test('tiny nonzero thresholds and differences do not round into a false zero or apparent equality', () => {
  const interpretation = interpretMetric({value: 0, unit: 'dimensionless', supported: true,
    criteria: [{op: '<=', threshold: 1e-12, passed: true}]});
  assert.equal(interpretation.criteria[0].target, 1e-12);
  assert.match(interpretation.text, /1e-12/);
  assert.match(interpretation.text, /낮음/);
  assert.ok(!/기준과 일치/.test(interpretation.text));
});

test('actual object-form goal constraints preserve known limits, explicit unknowns and versioned source refs', () => {
  const report = reportingFixture();
  report.goal.brief = {resource_constraints: {cost: 'unknown', tokens: {status: 'unknown'},
    time: '사용자가 시간 한도를 정하지 않음', whole_research_iteration_limit: '임의 반복 한도를 만들지 않음'}};
  const input = deepFreeze(report), before = JSON.stringify(input), model = reportingModel(input);
  assert.equal(model.report.constraints.length, 4);
  assert.deepEqual(model.judgment.resources.constraintDetails.map(item => item.key),
    ['cost', 'tokens', 'time', 'whole_research_iteration_limit']);
  assert.equal(model.report.constraintDetails[0].label, '비용 제약');
  assert.equal(model.report.constraintDetails[0].value, 'unknown');
  assert.equal(model.report.constraintDetails[0].status, 'unknown');
  assert.equal(model.report.constraintDetails[1].status, 'unknown');
  assert.equal(model.report.constraintDetails[3].label, '전체 연구 반복 한도');
  assert.equal(model.report.constraintDetails[3].value, '임의 반복 한도를 만들지 않음');
  assert.equal(model.report.constraintsStatus, 'partially_unknown');
  assert.equal(model.report.constraintDetails[0].ref.field, 'goal.brief.resource_constraints.cost');
  assert.equal(model.report.constraintDetails[0].ref.goal_version, 2);
  assert.ok(Object.hasOwn(model.report.constraintDetails[0].ref, 'revision'));
  model.report.constraintDetails[1].value.status = 'changed-in-presentation';
  assert.equal(JSON.stringify(input), before);
});

test('string and array constraints retain recorded values and absent constraints do not imply unrestricted resources', () => {
  const report = reportingFixture();
  report.goal.brief = {resource_constraints: '허가된 로컬 실행만 사용'};
  let model = reportingModel(report);
  assert.deepEqual(model.report.constraints, ['기록된 자원 제약: 허가된 로컬 실행만 사용']);
  assert.equal(model.report.constraintDetails[0].ref.field, 'goal.brief.resource_constraints');
  report.goal.brief.resource_constraints = ['로컬 작업공간', 'unknown'];
  model = reportingModel(report);
  assert.deepEqual(model.report.constraintDetails.map(item => item.value), ['로컬 작업공간', 'unknown']);
  assert.equal(model.report.constraintDetails[1].status, 'unknown');
  assert.equal(model.report.constraintDetails[1].ref.field, 'goal.brief.resource_constraints[1]');
  delete report.goal.brief.resource_constraints;
  assert.equal(reportingModel(report).report.constraintsStatus, 'unrecorded');
});

test('snapshot registration reference is stamped after every reference is appended', () => {
  const record = clone(actualRecord); record.registration.goal_version = 1;
  const model = modelFor(record, {snapshot: {status: clone(actualStatus), report: reportingFixture(),
    registration: record.registration.id, event_scope: 'selected_registration'}});
  assert.ok(model.refs.every(ref => Object.hasOwn(ref, 'revision') && Object.hasOwn(ref, 'goal_version')));
  const snapshotRef = model.refs.find(ref => ref.field === 'snapshot.registration');
  assert.equal(snapshotRef.revision, record.revision);
  assert.equal(snapshotRef.goal_version, 1);
  assert.equal(snapshotRef.registration_fingerprint, record.registration.fingerprint);
});

test('registered diagnostic measurement does not need its own success criterion or manufacture a pass verdict', () => {
  const record = clone(actualRecord);
  record.registration.spec.metrics.push('latency');
  record.registration.spec.metric_units = {latency: 'seconds'};
  record.verification.metrics.latency = 4;
  record.verification.metrics.unregistered_artifact_number = 900;
  const model = modelFor(record), diagnostic = model.metrics.find(metric => metric.name === 'latency');
  assert.equal(diagnostic.value, 4);
  assert.equal(diagnostic.supported, true);
  assert.deepEqual(diagnostic.criteria, []);
  assert.match(diagnostic.interpretation.text, /등록 기준 없음/);
  assert.ok(!model.graph.conclusions[0].support.some(item => item.metric === 'latency'));
  assert.ok(!model.metrics.some(item => item.name === 'unregistered_artifact_number'));
  record.evidence[0].integrity = 'tampered';
  assert.equal(modelFor(record).metrics.find(metric => metric.name === 'latency').supported, false);
});

test('registered diagnostic metrics remain measured in repeat distribution without becoming success criteria', () => {
  const records = [repeatFixture(1, 0.8), repeatFixture(2, 1)];
  records.forEach((record, index) => {
    record.registration.spec.metrics.push('latency');
    record.registration.spec.metric_units.latency = 'seconds';
    record.verification.metrics.latency = index ? 6 : 4;
  });
  const diagnostic = repeatModels(records)[0].metrics.find(metric => metric.name === 'latency');
  assert.equal(diagnostic.n, 2);
  assert.equal(diagnostic.mean, 5);
  assert.equal(diagnostic.min, 4);
  assert.equal(diagnostic.max, 6);
});

test('unloaded old memory reference keeps its persisted goal version and memory read revision', () => {
  const memory = {revision: 7, items: [{id: 'older-unloaded-registration', goal_id: actualRecord.registration.goal_id,
    goal_version: 1, hypothesis: '이전 기록', outcome: 'inconclusive', execution: 'registered', verification: 'pending'}]};
  const model = modelFor(clone(actualRecord), {goal: {...clone(actualStatus.goals[0]), version: 2}, memory,
    snapshot: {status: clone(actualStatus), report: reportingFixture()}});
  assert.equal(model.report.goalVersion, 2);
  assert.equal(model.lessons[0].ref.goal_version, 1);
  assert.equal(model.lessons[0].ref.revision, 7);
  assert.equal(model.refs.find(ref => ref.registration === 'older-unloaded-registration').goal_version, 1);
});

test('standalone comparison preserves each original record revision, frozen goal version and fingerprint on every exposed ref', () => {
  const first = clone(actualRecord), second = anotherRegistration(clone(actualRecord), 'comparison-source-second');
  first.workspace = 'original'; second.workspace = 'original';
  first.registration.goal_version = second.registration.goal_version = 1;
  first.revision = 7; second.revision = 9;
  second.registration.fingerprint = 'b'.repeat(64);
  const input = deepFreeze([first, second]), before = JSON.stringify(input), group = compareRecords(input)[0];
  assert.equal(group.conditions[0].ref.revision, 7);
  assert.equal(group.conditions[0].ref.goal_version, 1);
  for (const item of group.items) {
    const original = input.find(record => record.registration.id === item.registration);
    const refs = [...item.refs, ...item.metrics.flatMap(metric => [metric.ref, ...metric.criteria.map(criterion => criterion.ref)])];
    for (const ref of refs) {
      assert.equal(ref.revision, original.revision);
      assert.equal(ref.goal_version, original.registration.goal_version);
      assert.equal(ref.registration_fingerprint, original.registration.fingerprint);
    }
  }
  group.items[0].refs[0].field = 'presentation-only-change';
  assert.equal(JSON.stringify(input), before);
});

test('standalone repeat samples, group references and conditions keep per-record versions without aggregate stamping', () => {
  const first = repeatFixture(1, 0.6), second = repeatFixture(2, 0.8);
  first.registration.goal_version = second.registration.goal_version = 1;
  first.revision = 4; second.revision = 8;
  second.registration.fingerprint = 'c'.repeat(64);
  const group = repeatModels(deepFreeze([first, second]))[0];
  assert.equal(group.conditions[0].ref.revision, 4);
  assert.equal(group.conditions[0].ref.goal_version, 1);
  assert.equal(group.metrics[0].samples[0].ref.revision, 4);
  assert.equal(group.metrics[0].samples[1].ref.revision, 8);
  assert.equal(group.metrics[0].samples[1].ref.registration_fingerprint, 'c'.repeat(64));
  assert.ok(group.refs.every(ref => ref.goal_version === 1 && Object.hasOwn(ref, 'revision')));
  const legacy = clone(actualRecord); delete legacy.registration.goal_version; delete legacy.revision; delete legacy.registration.fingerprint;
  const legacyRef = compareRecords([legacy])[0].items[0].refs[0];
  assert.equal(legacyRef.goal_version, null);
  assert.equal(legacyRef.revision, null);
  assert.equal(legacyRef.registration_fingerprint, null);
});

test('actual presentation routing clears stale goals for registration and evidence focus but preserves explicit mismatches', async () => {
  let appSource = await readFile(new URL('../research_cli/web/app.js', import.meta.url), 'utf8');
  appSource = appSource.replace("from './view_model.js'", `from ${JSON.stringify('data:text/javascript,' + encodeURIComponent(source))}`)
    .replace(/\nstart\(\);\s*$/u, '\nexport {state, present};\n');
  const oldDocument = globalThis.document, oldFetch = globalThis.fetch, elements = new Map(), requests = [];
  globalThis.document = {body: {dataset: {}}, getElementById(id) {
    if (!elements.has(id)) elements.set(id, {dataset: {}, hidden: false, textContent: ''});
    return elements.get(id);
  }};
  // Stop at the real snapshot boundary; no copied routing logic or simulated research verdict.
  globalThis.fetch = async path => {requests.push(new URL(path, 'http://127.0.0.1'));
    return {json: async () => ({ok: false, error: {code: 'READ_BOUNDARY', message: 'Transport boundary reached'}})};
  };
  try {
    const {state, present} = await import(`data:text/javascript,${encodeURIComponent(appSource)}`);
    const previousGoal = () => Object.assign(state, {workspace: 'dedicated-audit', goalSelection: 'goal-A',
      selected: 'registration-A', token: 'local-test', refreshing: null});
    previousGoal();
    await present('research_view', {scene: 'overview', registration: 'registration-B'});
    assert.equal(requests.at(-1).searchParams.get('registration'), 'registration-B');
    assert.equal(requests.at(-1).searchParams.has('goal'), false);
    previousGoal();
    await present('research_view', {scene: 'overview', goal: 'goal-A', registration: 'registration-B'});
    assert.equal(requests.at(-1).searchParams.get('goal'), 'goal-A');
    assert.equal(requests.at(-1).searchParams.get('registration'), 'registration-B');
    previousGoal();
    await present('research_inspect_evidence', {registration: 'registration-B', evidence: 'original-evidence'});
    assert.equal(requests.at(-1).pathname, '/api/snapshot');
    assert.equal(requests.at(-1).searchParams.get('registration'), 'registration-B');
    assert.equal(requests.at(-1).searchParams.has('goal'), false);
    assert.equal(state.scene, 'evidence');
  } finally {
    if (oldDocument === undefined) delete globalThis.document; else globalThis.document = oldDocument;
    globalThis.fetch = oldFetch;
  }
});

test('cancelled execution counts remain distinct and lifecycle/resource events have readable semantic labels', () => {
  const status = clone(actualStatus);
  status.registrations[0].execution = 'cancelled';
  const events = ['goal.amend', 'goal.close', 'goal.resume', 'resource.record'].map((action, index) =>
    ({id: index, action, created: 100 + index, revision: index + 1}));
  const model = modelFor(clone(actualRecord), {snapshot: {status, events}});
  assert.equal(model.distribution.execution.find(item => item.key === 'cancelled').count, 1);
  assert.equal(model.distribution.execution.find(item => item.key === 'cancelled').label, '취소');
  assert.deepEqual(model.timeline.items.map(item => item.title),
    ['연구 목표 버전 수정', '전체 연구 상태 보고', '전체 연구 재개', '외부 자원 사용 기록']);
});

test('actual execution audit preserves nullable unseen attempt counts and observed failure/recovery facts', () => {
  const report = reportingFixture();
  report.execution_audit = {requests_received_count: null, replay_attempt_count: null, request_keys_total: 3,
    per_registration: [{registration: actualRecord.registration.id, run_count: 1}],
    error_groups: [{cause: 'exit code 1', run_ids: ['failed-run-1', 'failed-run-2']}],
    unresolved_runs: [{id: 'unknown-original', state: 'unknown'}]};
  const input = deepFreeze(report), before = JSON.stringify(input), model = reportingModel(input);
  assert.equal(model.judgment.executionAudit.requests_received_count, null);
  assert.equal(model.judgment.executionAudit.replay_attempt_count, null);
  assert.equal(model.judgment.executionAudit.request_keys_total, 3);
  assert.deepEqual(model.judgment.executionAudit.error_groups[0].run_ids, ['failed-run-1', 'failed-run-2']);
  assert.equal(model.judgment.executionAudit.unresolved_runs[0].state, 'unknown');
  assert.equal(model.judgment.executionAudit.ref.field, 'snapshot.report.execution_audit');
  assert.equal(model.judgment.executionAudit.ref.goal_version, 2);
  assert.ok(Object.hasOwn(model.judgment.executionAudit.ref, 'revision'));
  model.judgment.executionAudit.error_groups[0].run_ids.push('presentation-only');
  assert.equal(JSON.stringify(input), before);
  assert.equal(modelFor().judgment.executionAudit.request_keys_total, null);
});

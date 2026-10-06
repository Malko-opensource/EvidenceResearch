/* Presentation-only negative and large-store variants below never change durable research data. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';

const source = await readFile(new URL('../research_cli/web/view_model.js', import.meta.url), 'utf8');
const {buildViewModel, displayMetricLabel} = await import(`data:text/javascript,${encodeURIComponent(source)}`);
const transcript = (await readFile(new URL('../validation/research-report-0.8.0/skill-demo/cli-transcript.jsonl', import.meta.url), 'utf8'))
  .trim().split('\n').map(line => JSON.parse(line));
const actualRecord = transcript.filter(call => call.argv.includes('run') && call.argv.includes('--full'))
  .map(call => JSON.parse(call.stdout)).filter(result => result.ok && result.data?.record).at(-1).data.record;
const clone = value => structuredClone(value);
const deepFreeze = value => {
  if (value && typeof value === 'object') {Object.values(value).forEach(deepFreeze); Object.freeze(value);}
  return value;
};
const modelFor = (record = clone(actualRecord), extras = {}) => buildViewModel({record, workspace: 'projection-test',
  snapshot: {status: {revision: actualRecord.revision, total: 1, offset: 0, registrations: [],
    goals: [{id: actualRecord.registration.goal_id, title: '고정 고객 응답의 계산과 사업 기준 확인', version: 2,
      state: 'completed', state_source: 'explicit', lifecycle: {id: 'test-lifecycle', created: 120,
        reason: 'Untrusted agent says perfect scientific success', results: ['RAW report floats 3.33333333333333']}}], hypotheses: []}},
  records: record ? [record] : [], ...extras});
const uniqueAttempt = index => {
  const record = clone(actualRecord), id = `projection-reg-${index}`, run = `projection-run-${index}`;
  record.registration.id = id;
  record.registration.spec.seed = index;
  record.registration.fingerprint = index.toString(16).padStart(64, '0');
  record.run.id = run; record.run.registration_id = id;
  record.verification.run_id = run;
  record.decision.registration_id = id;
  record.evidence.forEach((evidence, position) => {evidence.id = `projection-evidence-${index}-${position}`;
    evidence.registration_id = id; evidence.run_id = run;});
  return record;
};

test('compact actual negative result keeps 72 versus frozen 80 without inventing percentages or closure success', () => {
  const model = modelFor(), view = model.observatory;
  assert.equal(view.summary.state, 'completed');
  assert.equal(view.summary.stateNote, '외부 연구 상태 보고');
  assert.equal(view.metric.name, 'satisfaction_pct');
  assert.equal(view.metric.label, '만족도');
  assert.equal(view.metric.labelSource, 'display_translation_of_metric_name');
  assert.equal(view.metric.status, 'measured');
  assert.equal(view.metric.value, 72);
  assert.equal(view.metric.valueText, '72');
  assert.equal(view.metric.unit, '단위 미등록');
  assert.equal(view.metric.unitKnown, false);
  assert.equal(view.metric.criteria[0].threshold, 80);
  assert.equal(view.metric.criteria[0].passed, false);
  assert.equal(view.metric.selection.method, 'unmet_registered_criterion');
  assert.equal(view.bottleneck.kind, 'criterion_unmet');
  assert.equal(view.focus.experiment.stateLabel, '실행 성공');
  assert.equal(view.focus.verification.stateLabel, '검증 실패');
  assert.equal(view.focus.conclusion.stateLabel, '기각');
  assert.doesNotMatch(JSON.stringify(view), /Untrusted agent says|RAW report floats/);
  assert.equal(view.graph.nodes.filter(node => node.kind === 'hypothesis').length, 1);
  assert.ok(view.uncertainty.some(item => item.kind === 'metric_unit'));
});

test('declared frozen labels and units are respected while later goal briefs and generic condition unit are ignored', () => {
  const record = clone(actualRecord);
  record.registration.spec.metric_metadata = {satisfaction_pct: {label: '등록된 만족도', unit: '%'}};
  let view = modelFor(record).observatory;
  assert.equal(view.metric.label, '등록된 만족도');
  assert.equal(view.metric.labelSource, 'registration_metadata');
  assert.equal(view.metric.unitKnown, true);
  assert.equal(view.metric.unit, '%');
  assert.ok(view.metric.refs.some(ref => ref.field === 'registration.spec.metric_metadata.satisfaction_pct.label'));
  delete record.registration.spec.metric_metadata;
  const goal = {id: record.registration.goal_id, title: '후기 목표', version: 99,
    brief: {metric_metadata: {satisfaction_pct: {label: '단위를 바꾼 후기 이름', unit: '%'}}}};
  view = modelFor(record, {goal}).observatory;
  assert.equal(record.registration.spec.conditions.unit, 'percentage');
  assert.equal(view.metric.unit, '단위 미등록');
  assert.equal(view.metric.label, '만족도');
  assert.ok(view.uncertainty.some(item => item.kind === 'registration.goal_version'));
});

test('two display-name translations preserve exact raw metrics, unknown units, frozen operators and readable unknown names', () => {
  assert.equal(displayMetricLabel('satisfaction_pct'), '만족도');
  assert.equal(displayMetricLabel('calculation_matches'), '계산 일치');
  assert.equal(displayMetricLabel('custom_result_name'), 'custom result name');
  assert.equal(displayMetricLabel('constructor'), 'constructor');
  assert.equal(displayMetricLabel('satisfaction_pct', {metric_metadata: {satisfaction_pct: {label: '등록 이름', display_name: '보조 이름'}}}), '등록 이름');
  assert.equal(displayMetricLabel('satisfaction_pct', {metric_metadata: {satisfaction_pct: {label: '  ', display_name: '등록 대체 이름'}}}), '등록 대체 이름');
  const satisfaction = modelFor().observatory.metric;
  assert.equal(satisfaction.label, '만족도');
  assert.equal(satisfaction.name, 'satisfaction_pct');
  assert.equal(satisfaction.unit, '단위 미등록');
  assert.equal(satisfaction.value, 72);
  assert.equal(satisfaction.criteria[0].op, '>=');
  assert.equal(satisfaction.criteria[0].threshold, 80);
  assert.equal(satisfaction.criteria[0].passed, false);
  assert.ok(satisfaction.refs.some(ref => ref.field === 'registration.spec.metrics' && ref.metric === 'satisfaction_pct'
    && ref.display_transform === 'display_translation_of_metric_name'));
  const record = clone(actualRecord); record.registration.spec.primary_metric = 'calculation_matches';
  let metric = modelFor(record).observatory.metric;
  assert.equal(metric.label, '계산 일치');
  assert.equal(metric.labelSource, 'display_translation_of_metric_name');
  assert.equal(metric.unit, '단위 미등록');
  assert.equal(metric.value, 1);
  assert.equal(metric.criteria[0].op, '==');
  assert.equal(metric.criteria[0].threshold, 1);
  assert.equal(metric.criteria[0].passed, true);
  record.registration.spec.metric_metadata = {calculation_matches: {display_name: '등록 소유자가 정한 진단 이름'}};
  metric = modelFor(record).observatory.metric;
  assert.equal(metric.label, '등록 소유자가 정한 진단 이름');
  assert.equal(metric.labelSource, 'registration_metadata');
  assert.equal(metric.unit, '단위 미등록');
  record.registration.spec.metrics = ['custom_result_name'];
  record.registration.spec.primary_metric = 'custom_result_name';
  record.registration.spec.criteria = [{metric: 'custom_result_name', op: '>=', threshold: 80}];
  record.verification.metrics = {custom_result_name: 72};
  record.verification.details.criteria_results = [{metric: 'custom_result_name', op: '>=', threshold: 80, actual: 72, passed: false}];
  metric = modelFor(record).observatory.metric;
  assert.equal(metric.label, 'custom result name');
  assert.equal(metric.labelSource, 'name_readability');
  assert.equal(metric.unit, '단위 미등록');
});

test('tampered, missing, unsupported and absent measurements are distinct and never promoted to a current success', () => {
  for (const integrity of ['tampered', 'missing']) {
    const record = clone(actualRecord);
    record.evidence.find(evidence => evidence.name === 'summary').integrity = integrity;
    const view = modelFor(record).observatory;
    assert.equal(view.metric.status, 'invalid');
    assert.equal(view.metric.criteria[0].passed, null);
    assert.equal(view.bottleneck.kind, 'integrity');
    assert.equal(view.focus.evidence.state, integrity);
    assert.equal(view.focus.evidence.stateLabel, integrity === 'missing' ? '파일 누락' : '변조 감지');
    assert.equal(view.focus.evidence.tone, 'warn');
    assert.ok(view.graph.nodes.some(node => node.kind === 'evidence' && node.state === integrity && node.tone === 'warn'));
  }
  const mixed = clone(actualRecord);
  mixed.evidence.find(evidence => evidence.name === 'summary').integrity = 'missing';
  mixed.evidence.find(evidence => evidence.name === 'source:data.csv').integrity = 'tampered';
  const mixedView = modelFor(mixed).observatory;
  assert.equal(mixedView.focus.evidence.state, 'tampered');
  assert.equal(mixedView.focus.evidence.stateLabel, '변조 감지');
  assert.match(mixedView.focus.evidence.text, /현재 원본 확인 필요/);
  assert.ok(mixedView.uncertainty.some(item => item.kind === 'evidence.integrity' && /누락·변조/.test(item.text)));
  assert.equal(mixedView.metric.status, 'invalid');
  assert.equal(mixedView.metric.criteria[0].passed, null);
  const unlinked = clone(actualRecord); unlinked.verification.run_id = 'foreign-run';
  let view = modelFor(unlinked).observatory;
  assert.equal(view.metric.status, 'historical');
  assert.equal(view.bottleneck.kind, 'verification_failed');
  assert.ok(view.uncertainty.some(item => item.kind === 'measurement_support'));
  assert.ok(!view.graph.nodes.some(node => node.kind === 'verification'));
  const absent = clone(actualRecord); absent.verification = null;
  view = modelFor(absent).observatory;
  assert.equal(view.metric.status, 'unknown');
  assert.equal(view.metric.value, null);
  assert.equal(view.metric.valueText, '미확인');
  assert.equal(view.metric.criteria[0].passed, null);
});

test('shared hypothesis is drawn once across real distinct attempts and restored copies do not multiply the graph', () => {
  const records = [uniqueAttempt(0), uniqueAttempt(1), uniqueAttempt(2)], selected = records[1];
  const view = modelFor(selected, {records: [...records, clone(records[0])]}).observatory;
  assert.equal(view.graph.shown, 3);
  assert.equal(view.attempts.shown, 3);
  assert.equal(view.graph.nodes.length, 13);
  assert.equal(view.graph.nodes.filter(node => node.kind === 'hypothesis').length, 1);
  assert.equal(view.graph.nodes.filter(node => node.kind === 'experiment').length, 3);
  assert.equal(view.graph.nodes.filter(node => node.kind === 'evidence').length, 3);
  assert.equal(view.graph.nodes.filter(node => node.kind === 'verification').length, 3);
  assert.equal(view.graph.nodes.filter(node => node.kind === 'conclusion').length, 3);
  const hypothesis = view.graph.nodes.find(node => node.kind === 'hypothesis');
  assert.deepEqual(hypothesis.registrations, [selected.registration.id, records[0].registration.id, records[2].registration.id]);
  assert.equal(hypothesis.selected, true);
  assert.equal(view.graph.nodes.find(node => node.kind === 'experiment' && node.selected).seed, 1);
  assert.equal(view.graph.nodes.find(node => node.kind === 'experiment' && node.selected).ordinal, 2);
  assert.equal(view.attempts.items[0].title, '시도 2 · Seed 1');
  assert.equal(view.attempts.ordinalSource, 'current_query_order');
  assert.ok(view.graph.edges.every(edge => edge.recorded === true));
  assert.equal(view.graph.edges.filter(edge => edge.kind === 'registered_for').length, 3);
  assert.ok(view.graph.edges.every(edge => view.graph.nodes.some(node => node.id === edge.from) && view.graph.nodes.some(node => node.id === edge.to)));
  assert.ok(!view.graph.edges.some(edge => edge.kind === 'verification_caused_decision'));
  assert.ok(view.uncertainty.some(item => item.kind === 'independence'));
});

test('actual foreign keys determine the graph; missing records create no placeholder evidence or verdicts', () => {
  const record = clone(actualRecord);
  record.registration.hypothesis_id = 'foreign-hypothesis';
  record.run.registration_id = 'foreign-registration';
  record.decision.registration_id = 'foreign-registration';
  let view = modelFor(record).observatory;
  assert.deepEqual(view.graph.nodes.map(node => node.kind), ['experiment']);
  assert.equal(view.graph.edges.length, 0);
  const empty = clone(actualRecord); empty.run = null; empty.evidence = []; empty.verification = null; empty.decision = null;
  view = modelFor(empty).observatory;
  assert.deepEqual(view.graph.nodes.map(node => node.kind), ['experiment', 'hypothesis']);
  assert.equal(view.graph.edges.length, 1);
  assert.equal(view.metric.status, 'unknown');
});

test('compact graph is scoped to six loaded attempts and always includes selected record without treating a page as all history', () => {
  const records = Array.from({length: 10}, (_, index) => uniqueAttempt(index)), selected = records.at(-1);
  const view = modelFor(selected, {records,
    snapshot: {status: {revision: actualRecord.revision, total: 100, offset: 20, goals: [], hypotheses: [], registrations: []}}}).observatory;
  assert.equal(view.graph.shown, 6);
  assert.equal(view.graph.total, 100);
  assert.equal(view.graph.truncated, true);
  assert.equal(view.attempts.total, 100);
  assert.equal(view.attempts.items[0].registration, selected.registration.id);
  assert.equal(view.attempts.items[0].ordinal, 10);
  assert.equal(view.graph.nodes.filter(node => node.kind === 'experiment').length, 6);
  assert.ok(!('progress' in view));
  assert.ok(!('score' in view));
});

test('empty research has no metric, attempt, causal relation or invented percentage', () => {
  const view = buildViewModel({workspace: 'empty', snapshot: {status: {goals: [], hypotheses: [], registrations: [], total: 0}}}).observatory;
  assert.equal(view.summary.question, '연구 목표 미기록');
  assert.equal(view.metric, null);
  assert.deepEqual(view.attempts.items, []);
  assert.equal(view.attempts.total, 0);
  assert.deepEqual(view.graph.nodes, []);
  assert.deepEqual(view.graph.edges, []);
  assert.equal(view.graph.truncated, false);
});

test('projection references retain actual revision, frozen goal version, fingerprint and raw metric identity', () => {
  const view = modelFor().observatory;
  assert.ok(view.refs.length > 0);
  for (const ref of view.refs) {
    assert.ok(Object.hasOwn(ref, 'revision'));
    assert.ok(Object.hasOwn(ref, 'goal_version'));
    if (ref.registration === actualRecord.registration.id && !ref.field.startsWith('goal.')) {
      assert.equal(ref.goal_version, actualRecord.registration.goal_version);
      assert.equal(ref.registration_fingerprint, actualRecord.registration.fingerprint);
    }
  }
  assert.equal(view.metric.refs[0].field, 'verification.metrics.satisfaction_pct');
  assert.equal(view.metric.criteria[0].ref.field, 'registration.spec.criteria[1]');
  assert.equal(view.summary.refs.find(ref => ref.field === 'goal.title').goal_version, 2);
  assert.equal(view.metric.refs[0].goal_version, 1);
});

test('frozen inputs are untouched and projected labels, states and criterion numbers have no mutable raw references', () => {
  const record = deepFreeze(clone(actualRecord)), records = deepFreeze([uniqueAttempt(1)]);
  const before = JSON.stringify({record, records});
  const view = modelFor(record, {records}).observatory;
  view.metric.criteria[0].threshold = 999;
  view.graph.nodes[0].state = 'success';
  view.focus.verification.refs[0].field = 'changed-display';
  view.attempts.items[0].states.decision = 'adopted';
  assert.equal(JSON.stringify({record, records}), before);
});

test('unknown execution remains a missing original receipt even when a previous numeric verifier record exists', () => {
  const record = clone(actualRecord); record.run.state = 'unknown';
  const view = modelFor(record).observatory;
  assert.equal(view.bottleneck.kind, 'execution_unknown');
  assert.equal(view.metric.status, 'historical');
  assert.equal(view.focus.experiment.stateLabel, '실행 미확정');
  assert.equal(view.metric.criteria[0].passed, null);
});

test('a previous pass and adoption with current tampering are explicitly historical in graph and focus labels', () => {
  const record = clone(actualRecord);
  record.registration.spec.criteria = [{metric: 'satisfaction_pct', op: '>=', threshold: 70}];
  record.verification.details.criteria_results = [{metric: 'satisfaction_pct', op: '>=', threshold: 70, actual: 72, passed: true}];
  record.verification.state = 'passed'; record.decision.state = 'adopted';
  record.registration.spec.primary_metric = 'satisfaction_pct';
  record.evidence.find(evidence => evidence.name === 'summary').integrity = 'tampered';
  const view = modelFor(record).observatory;
  assert.equal(view.metric.status, 'invalid');
  for (const kind of ['verification', 'conclusion']) {
    assert.equal(view.focus[kind].historical, true);
    assert.match(view.focus[kind].stateLabel, /과거/);
    const node = view.graph.nodes.find(candidate => candidate.kind === kind);
    assert.equal(node.historical, true);
    assert.equal(node.tone, 'warn');
    assert.match(node.stateLabel, /과거/);
  }
});

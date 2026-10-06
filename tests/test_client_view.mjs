/* Read-only client brief tests use saved real records; variants never enter a research store. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';

const source = await readFile(new URL('../research_cli/web/view_model.js', import.meta.url), 'utf8');
const {buildViewModel, buildClientView} = await import(`data:text/javascript,${encodeURIComponent(source)}`);
const transcript = (await readFile(new URL('../validation/research-report-0.8.0/skill-demo/cli-transcript.jsonl', import.meta.url), 'utf8'))
  .trim().split('\n').map(line => JSON.parse(line));
const negative = transcript.filter(call => call.argv.includes('run') && call.argv.includes('--full'))
  .map(call => JSON.parse(call.stdout)).filter(result => result.ok && result.data?.record).at(-1).data.record;
const success = JSON.parse(await readFile(new URL('../validation/agent-web-0.6.0/record.json', import.meta.url), 'utf8')).data;
const clone = value => structuredClone(value);
const freeze = value => {
  if (value && typeof value === 'object') {Object.values(value).forEach(freeze); Object.freeze(value);}
  return value;
};
const goalFor = record => ({id: record.registration.goal_id, title: '고정 고객 응답의 보고 기준 확인',
  version: record.registration.goal_version ?? 1, state: 'completed', state_source: 'explicit',
  lifecycle: {id: 'client-test-lifecycle', reason: 'Unverified agent declares perfect success',
    results: ['Fake perfect 100 percent success'], incomplete: ['Private raw path C:/secret']}});
const modelFor = (record = clone(negative), extras = {}) => {
  const goal = extras.goal || goalFor(record);
  return buildViewModel({record, workspace: 'client-brief-test', goal,
    snapshot: {status: {revision: record.revision, total: 1, offset: 0, registrations: [], goals: [goal], hypotheses: []}},
    records: [record], ...extras});
};
const visibleStrings = view => JSON.stringify({question: view.question.title, answer: view.answer.headline,
  detail: view.answer.detail, assurance: view.assurance.label, assuranceDetail: view.assurance.detail,
  followup: view.followup.label, followupText: view.followup.text,
  required: view.followup.requiredEvidence.map(item => item.text), scope: view.limitations.scope,
  limitations: view.limitations.items.map(item => item.text)});

test('real negative result gives a confirmed negative answer rather than an execution or closure success', () => {
  const vm = modelFor(), view = buildClientView(vm);
  assert.equal(view.answer.status, 'criterion_unmet');
  assert.equal(view.answer.headline, '만족도 기준에 미치지 못했습니다.');
  assert.equal(view.answer.detail, '만족도 72 · 기준 80 이상');
  assert.equal(view.answer.metric.value, 72);
  assert.equal(view.answer.metric.status, 'measured');
  assert.equal(view.answer.metric.criteria[0].passed, false);
  assert.equal(view.assurance.label, '기준 미달을 확인함');
  assert.equal(view.assurance.status, 'confirmed_in_registered_scope');
  assert.equal(view.followup.label, '진행 종료로 보고됨');
  assert.equal(view.followup.reported, true);
  assert.equal(view.followup.text, '이 결과를 다른 조건에 적용하려면 추가 확인이 필요합니다.');
  assert.equal(view.followup.nextKind, null);
  assert.equal(view.assurance.detail, '계산 일치는 등록 기준을 충족했습니다. 결과는 실험 당시 조건에 한정됩니다.');
  assert.equal(view.answer.tone, 'bad');
  assert.ok(view.limitations.items.some(item => item.kind === 'metric_unit'));
  assert.doesNotMatch(visibleStrings(view), /Seed|seed|reg_|run_|goal_|hyp_|ev_|sha256|revision|100 percent|Unverified|Private raw path|72%/);
});

test('a fulfilled explicitly chosen diagnostic never conceals another unmet registered criterion', () => {
  const record = clone(negative); record.registration.spec.primary_metric = 'calculation_matches';
  const vm = modelFor(record), view = buildClientView(vm);
  assert.equal(vm.observatory.metric.name, 'calculation_matches');
  assert.equal(vm.observatory.metric.criteria[0].passed, true);
  assert.equal(view.answer.status, 'criterion_unmet');
  assert.equal(view.answer.metric.name, 'satisfaction_pct');
  assert.equal(view.answer.detail, '만족도 72 · 기준 80 이상');
  assert.equal(vm.primaryMetric.name, 'calculation_matches');
});

test('confirmed registered criteria and scientific adoption remain separate', () => {
  const record = clone(success); record.decision = null;
  const view = buildClientView(modelFor(record));
  assert.equal(view.answer.status, 'criteria_met');
  assert.equal(view.answer.headline, '등록 기준을 충족했습니다.');
  assert.equal(view.answer.metric.value, 1);
  assert.equal(view.assurance.status, 'confirmed_in_registered_scope');
  assert.equal(view.assurance.detail, '실험 당시 등록한 데이터와 조건에 한정한 결과입니다.');
  assert.doesNotMatch(view.answer.headline, /채택|연구 종료|의뢰 종료/);
  assert.match(view.limitations.scope, /선택한 시도.*등록 조건/);
});

test('tampered and missing current originals invalidate a past pass or adoption in the client brief', () => {
  for (const integrity of ['tampered', 'missing']) {
    const record = clone(success); record.evidence.find(item => item.name === 'result').integrity = integrity;
    const view = buildClientView(modelFor(record));
    assert.equal(view.answer.status, 'invalid');
    assert.equal(view.answer.metric.value, null);
    assert.equal(view.answer.metric.status, 'invalid');
    assert.ok(view.answer.metric.criteria.every(item => item.passed === null));
    assert.equal(view.assurance.status, 'unconfirmed');
    assert.equal(view.assurance.tone, 'warn');
    assert.equal(view.followup.requiredEvidence[0].kind, 'integrity');
    assert.doesNotMatch(view.answer.headline, /충족|성공|채택/);
  }
});

test('unsupported historical numbers remain unavailable as current chart values', () => {
  const record = clone(success); record.verification.details.validator_sha256 = '0'.repeat(64);
  const view = buildClientView(modelFor(record));
  assert.equal(view.answer.status, 'historical');
  assert.equal(view.answer.metric.status, 'historical');
  assert.equal(view.answer.metric.value, null);
  assert.equal(view.answer.metric.valueText, '미확인');
  assert.equal(view.assurance.label, '과거 판정만 남아 있음');
  assert.equal(view.followup.requiredEvidence[0].kind, 'verification');
});

test('execution failure yields no hypothesis refutation or confirmed numerical result', () => {
  const record = clone(negative); record.run.state = 'failed'; record.verification = null; record.decision = null;
  const view = buildClientView(modelFor(record));
  assert.equal(view.answer.status, 'execution_failed');
  assert.equal(view.answer.metric.value, null);
  assert.match(view.answer.detail, /가설이 틀렸다고.*수는 없습니다/);
  assert.equal(view.assurance.status, 'unconfirmed');
  assert.equal(view.followup.requiredEvidence[0].kind, 'execution_failure');
});

test('unknown execution requests evidence about the original execution without asking for a new run', () => {
  const record = clone(negative); record.run.state = 'unknown'; record.verification = null; record.decision = null;
  const view = buildClientView(modelFor(record));
  assert.equal(view.answer.status, 'execution_unknown');
  assert.equal(view.answer.metric.value, null);
  assert.match(view.followup.requiredEvidence[0].text, /원래 실행/);
  assert.doesNotMatch(visibleStrings(view), /새 실행|다시 실행|재실행/);
});

test('cancelled execution is not displayed as a pending run or a hypothesis rejection', () => {
  const record = clone(negative); record.run.state = 'cancelled'; record.verification = null; record.decision = null;
  const view = buildClientView(modelFor(record));
  assert.equal(view.answer.status, 'execution_cancelled');
  assert.equal(view.answer.metric.value, null);
  assert.equal(view.assurance.status, 'unconfirmed');
  assert.ok(!view.followup.requiredEvidence.some(item => item.kind === 'execution_receipt'));
  assert.doesNotMatch(view.answer.headline, /기각|기준.*미치지/);
});

test('running, unexecuted and executed-but-unverified attempts provide distinct waiting explanations', () => {
  for (const [state, expected, detail] of [['running', 'running', /도착하지/],
    ['unexecuted', 'awaiting_result', /등록 조건/], ['succeeded', 'awaiting_verification', /검증된 것은 아닙니다/]]) {
    const record = clone(negative); record.verification = null; record.decision = null;
    if (state === 'unexecuted') {record.run = null; record.evidence = [];}
    else record.run.state = state;
    const view = buildClientView(modelFor(record));
    assert.equal(view.answer.status, expected);
    assert.equal(view.answer.metric.value, null);
    assert.match(view.answer.detail, detail);
    assert.equal(view.assurance.status, 'unconfirmed');
  }
});

test('inconclusive verification and unsupported failed verification cannot become a confirmed negative answer', () => {
  for (const state of ['inconclusive', 'failed']) {
    const record = clone(negative); record.verification.state = state;
    record.verification.details.criteria_results = []; record.decision = null;
    const view = buildClientView(modelFor(record));
    assert.equal(view.answer.status, state === 'failed' ? 'unconfirmed' : 'inconclusive');
    assert.equal(view.answer.metric.value, null);
    assert.equal(view.assurance.status, 'unconfirmed');
    assert.equal(view.followup.requiredEvidence[0].kind, 'verification');
  }
});

test('goal changes qualify a valid measurement without changing frozen criteria or guessing units', () => {
  const goal = goalFor(negative); goal.version = (negative.registration.goal_version ?? 1) + 1;
  goal.brief = {evaluation: {units: {satisfaction_pct: 'percentage'}}};
  const view = buildClientView(modelFor(clone(negative), {goal}));
  assert.equal(view.answer.status, 'criterion_unmet');
  assert.equal(view.answer.metric.value, 72);
  assert.equal(view.answer.metric.unit, '단위 미등록');
  assert.equal(view.assurance.label, '등록 당시 조건에서 확인됨');
  assert.equal(view.followup.nextKind, 'goal_version');
  assert.equal(view.followup.text, '현재 의뢰에 적용할 수 있는지 대조가 필요합니다.');
  assert.ok(view.limitations.items.some(item => item.kind === 'goal_version'));
  assert.ok(view.limitations.items.some(item => item.kind === 'metric_unit'));
  assert.doesNotMatch(view.answer.detail, /%|percentage/);
});

test('mixed snapshot revisions override otherwise valid result numbers', () => {
  const record = clone(success), goal = goalFor(record);
  const vm = modelFor(record, {goal, snapshot: {status: {revision: record.revision + 1, total: 1,
    registrations: [], goals: [goal], hypotheses: []}}});
  const view = buildClientView(vm);
  assert.equal(view.answer.status, 'stale');
  assert.equal(view.answer.metric.value, null);
  assert.equal(view.assurance.status, 'unconfirmed');
  assert.equal(view.followup.requiredEvidence[0].kind, 'snapshot');
  assert.equal(view.followup.nextKind, 'snapshot');
  assert.equal(view.followup.text, view.followup.requiredEvidence[0].text);
});

test('a confirmed diagnostic criterion is reported separately from an unmet business criterion with its own references', () => {
  const view = buildClientView(modelFor());
  assert.match(view.answer.headline, /^만족도/);
  assert.match(view.assurance.detail, /^계산 일치는 등록 기준을 충족했습니다/);
  assert.ok(view.assurance.refs.some(ref => ref.field === 'verification.metrics.calculation_matches'));
  assert.ok(view.assurance.refs.some(ref => ref.field === 'registration.spec.criteria[0]'));
  assert.equal(view.answer.metric.name, 'satisfaction_pct');
  assert.equal(view.answer.metric.criteria[0].passed, false);
});

test('other-metric reassurance requires supported criteria and respects its registered display label', () => {
  const named = clone(negative);
  named.registration.spec.metric_metadata = {calculation_matches: {label: '등록 계산 검사'}};
  let view = buildClientView(modelFor(named));
  assert.equal(view.assurance.detail, '등록 계산 검사는 등록 기준을 충족했습니다. 결과는 실험 당시 조건에 한정됩니다.');
  const diagnostic = clone(negative);
  diagnostic.registration.spec.criteria = diagnostic.registration.spec.criteria.filter(item => item.metric !== 'calculation_matches');
  diagnostic.verification.details.criteria_results = diagnostic.verification.details.criteria_results.filter(item => item.metric !== 'calculation_matches');
  view = buildClientView(modelFor(diagnostic));
  assert.equal(view.assurance.detail, '실험 당시 등록한 데이터와 조건에 한정한 결과입니다.');
  const invalid = clone(named); invalid.evidence.find(item => item.name === 'summary').integrity = 'missing';
  view = buildClientView(modelFor(invalid));
  assert.doesNotMatch(view.assurance.detail, /계산 검사.*충족|계산 일치.*충족/);
});

test('pending records describe missing evidence without assuming that verification or execution work is underway', () => {
  for (const executed of [false, true]) {
    const record = clone(negative); record.verification = null; record.decision = null;
    if (!executed) {record.run = null; record.evidence = [];}
    const view = buildClientView(modelFor(record));
    assert.equal(view.answer.headline, executed ? '독립 검증이 필요합니다.' : '실행 결과가 아직 확인되지 않았습니다.');
    assert.doesNotMatch(view.answer.headline, /하는 중|진행 중/);
    assert.equal(view.assurance.detail, executed ? '등록 기준에 연결된 독립 검증이 아직 없습니다.' : '확인할 실행 결과가 아직 없습니다.');
    assert.doesNotMatch(view.assurance.detail, /채택|과거 판정|이전 판정/);
    assert.equal(view.followup.nextKind, view.followup.requiredEvidence[0].kind);
    assert.equal(view.followup.text, view.followup.requiredEvidence[0].text);
    assert.doesNotMatch(view.followup.text, /진행 보고|종료/);
  }
});

test('declared units are preserved exactly, including ratios without implicit percentage conversion', () => {
  const record = clone(negative);
  record.registration.spec.metric_metadata = {satisfaction_pct: {label: '등록된 만족도', unit: 'ratio'}};
  const view = buildClientView(modelFor(record));
  assert.equal(view.answer.metric.unit, 'ratio');
  assert.equal(view.answer.detail, '등록된 만족도 72 ratio · 기준 80 ratio 이상');
  assert.ok(!view.limitations.items.some(item => item.kind === 'metric_unit'));
});

test('the original request is used only for the same goal and version with an exact source reference', () => {
  const vm = modelFor(), goal = goalFor(negative); goal.brief = {original_request: '이 데이터를 믿고 보고할 수 있나요?'};
  const view = buildClientView(vm, {goal});
  assert.equal(view.question.title, goal.brief.original_request);
  assert.ok(view.question.refs.every(ref => ref.field === 'goal.brief.original_request' && ref.goal === goal.id));
  assert.equal(buildClientView(vm, {goal: {...goal, id: 'other-goal'}}).question.title, vm.question.title);
  assert.equal(buildClientView(vm, {goal: {...goal, version: goal.version + 1}}).question.title, vm.question.title);
});

test('empty and many-record views do not manufacture a result or report page counts as confidence', () => {
  const empty = buildClientView(buildViewModel({workspace: 'empty-client', snapshot: {status: {
    revision: 0, total: 0, registrations: [], goals: [], hypotheses: []}}}));
  assert.equal(empty.answer.status, 'empty');
  assert.equal(empty.answer.metric, null);
  assert.equal(empty.followup.label, '전체 진행 상황 미확인');
  assert.equal(empty.assurance.detail, '확인할 실행 결과가 아직 없습니다.');
  const vm = modelFor(); vm.scope.total = 3200;
  const view = buildClientView(vm);
  assert.equal(view.answer.status, 'criterion_unmet');
  assert.doesNotMatch(visibleStrings(view), /3200|진행률|확신도|신뢰도.*\d/);
});

test('a terminal state without a recorded lifecycle does not invent an external closure report', () => {
  const goal = goalFor(negative); delete goal.lifecycle;
  const view = buildClientView(modelFor(clone(negative), {goal}));
  assert.equal(view.answer.status, 'criterion_unmet');
  assert.equal(view.followup.reported, false);
  assert.equal(view.followup.label, '전체 진행 상황 미확인');
});

test('every brief component remains traceable and detached while the full model stays immutable', () => {
  const vm = freeze(modelFor()), before = JSON.stringify(vm), view = buildClientView(vm);
  assert.equal(JSON.stringify(vm), before);
  for (const part of ['question', 'answer', 'assurance', 'followup', 'limitations']) {
    assert.ok(view[part].refs.length > 0, part);
    assert.ok(view[part].refs.every(ref => Object.hasOwn(ref, 'revision') && Object.hasOwn(ref, 'goal_version')), part);
  }
  assert.ok(view.refs.some(ref => ref.field === 'verification.metrics.satisfaction_pct'));
  assert.ok(view.refs.some(ref => ref.field === 'registration.spec.criteria[1]'));
  assert.equal(view.refs.length, new Set(view.refs.map(ref => JSON.stringify(ref))).size);
  view.answer.refs[0].field = 'changed-output-reference'; view.sourceVersion.goal = 'changed';
  assert.equal(JSON.stringify(vm), before);
});

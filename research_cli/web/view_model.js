/* Read-only presentation of durable research facts. No state transitions or judgments. */
const LABELS = Object.freeze({registered: '조건 고정', running: '실행 중', succeeded: '실행 성공',
  failed: '실패', unknown: '실행 미확정', pending: '대기', passed: '검증 통과', adopted: '채택',
  rejected: '기각', inconclusive: '미결', valid: '해시 일치', tampered: '변조 감지', missing: '파일 누락',
  no_file: '원본 파일 없는 주장', measured: '측정값', literature: '문헌 주장', inference: '추론',
  proposal: '미실행 제안', success: '성공', failure: '실패', unrecorded: '아직 기록 없음',
  recorded: '목표 기록', proposed: '가설 제안', cancelled: '취소', paused: '연구 일시중단',
  completed: '연구 종료', active: '연구 진행'});
const EVENT_LABELS = Object.freeze({'goal.create': '연구 목표 기록', 'hypothesis.create': '가설 제안',
  'validator.register': '독립 검증기 고정', 'registration.create': '실험 조건 사전등록',
  'run.claim': '실행 요청 확보', 'run.complete': '실행 증거 수집', 'run.unknown': '실행 여부 미확정',
  'verification.complete': '독립 검증 기록', 'decision.create': '가설 결정 기록', 'evidence.add': '원본 증거 연결',
  'goal.amend': '연구 목표 버전 수정', 'goal.close': '전체 연구 상태 보고', 'goal.resume': '전체 연구 재개',
  'resource.record': '외부 자원 사용 기록'});
const MISSING_LABELS = Object.freeze({'execution receipt': '실행 결과 증거',
  'verified artifact metrics': '산출물의 검증된 지표',
  'confirmed terminal execution receipt': '실행 종료 여부가 확인된 결과 증거',
  'independent verification': '독립 검증'});
const CONDITION_LABELS = Object.freeze({comparison: '비교 기준', data_split: '데이터 분할', seed: 'Seed',
  source_version: '소스 버전', conditions: '실행 조건', validator: '등록 검증기'});
const OPS = Object.freeze({'>': (a, b) => a > b, '>=': (a, b) => a >= b,
  '<': (a, b) => a < b, '<=': (a, b) => a <= b, '==': (a, b) => a === b, '!=': (a, b) => a !== b});
const isObject = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);
const finite = (value) => typeof value === 'number' && Number.isFinite(value);
const list = (value) => Array.isArray(value) ? value : [];
const unwrap = (value) => isObject(value) && value.ok === true && isObject(value.data) ? value.data : value;
const stable = (value) => JSON.stringify(Array.isArray(value) ? value.map((item) => JSON.parse(stable(item)))
  : isObject(value) ? Object.fromEntries(Object.keys(value).sort().map((key) => [key, JSON.parse(stable(value[key]))]))
    : value === undefined || (typeof value === 'number' && !finite(value)) ? null : value);

export function labelState(key, dimension = '') {
  if (key === 'unknown' && dimension === 'goal') return '전체 연구 상태 미확인';
  if (key === 'failed' && dimension === 'execution') return '실행 실패';
  if (key === 'failed' && dimension === 'verification') return '검증 실패';
  return LABELS[key] || (typeof key === 'string' && key ? key : '미확인');
}

export function clipText(value, max = 180) {
  if (value === null || value === undefined) return '';
  const text = String(value).replace(/\s+/gu, ' ').trim();
  const length = Number.isInteger(max) && max > 0 ? max : 180;
  const characters = Array.from(text);
  return characters.length > length ? characters.slice(0, Math.max(0, length - 1)).join('') + '…' : text;
}

function asText(value) {
  if (value === undefined || value === null || value === '') return '미확인';
  if (Array.isArray(value)) return value.map(asText).join(' · ');
  if (isObject(value)) return Object.entries(value).map(([key, item]) => `${key}: ${asText(item)}`).join(' · ');
  return String(value);
}

function reference(workspace, registration, field, extra = {}) {
  return {workspace: workspace || '', ...(registration ? {registration} : {}), field, ...extra};
}

/** Exported record projections remain traceable when used without the aggregate view model. */
function stampRecordReferences(value, record) {
  if (Array.isArray(value)) { value.forEach(item => stampRecordReferences(item, record)); return value; }
  if (!isObject(value)) return value;
  if (typeof value.field === 'string' && typeof value.workspace === 'string') {
    value.revision ??= record?.revision ?? null;
    value.goal_version ??= record?.registration?.goal_version ?? null;
    value.registration_fingerprint ??= record?.registration?.fingerprint ?? null;
  }
  Object.values(value).forEach(item => stampRecordReferences(item, record));
  return value;
}

function conditions(spec, workspace = '', registration = '') {
  return ['comparison', 'data_split', 'seed', 'source_version', 'conditions', 'validator'].map((key) => ({
    label: CONDITION_LABELS[key], value: clipText(asText(key === 'source_version' ? spec.source_version?.label
      : key === 'conditions' ? spec.conditions || {} : spec[key]), 320),
    ref: reference(workspace, registration, `registration.spec.${key}`)}));
}

function unitFor(spec, name) {
  const candidates = [spec.metric_units?.[name], spec.units?.[name], spec.metric_metadata?.[name]?.unit];
  return candidates.find((unit) => typeof unit === 'string' && unit.trim())?.trim() || '단위 미등록';
}

function statesFor(record, summary = {}) {
  return {execution: record?.run?.state || summary.execution || (record?.registration ? 'registered' : 'unrecorded'),
    verification: record?.verification?.state || summary.verification || 'pending',
    decision: record?.decision?.state || summary.decision || 'pending'};
}

function supportFor(record) {
  const spec = record?.registration?.spec || {}, run = record?.run, verification = record?.verification;
  const evidence = list(record?.evidence), details = verification?.details || {};
  const invalid = evidence.filter((item) => ['tampered', 'missing'].includes(item.integrity));
  const linked = evidence.filter((item) => item.run_id === run?.id);
  const artifacts = list(spec.artifacts);
  const linkedCorrectly = !!(record?.registration?.id && run?.id && run.registration_id === record.registration.id &&
    verification?.run_id === run.id && /^[a-f\d]{64}$/i.test(spec.validator_sha256 || '') && details.validator_sha256 === spec.validator_sha256);
  const sourceFiles = Object.entries(spec.source_version?.files || {});
  const sourceComplete = sourceFiles.length > 0 && sourceFiles.every(([path, digest]) =>
    linked.some((item) => item.name === `source:${path}` && item.sha256 === digest && item.integrity === 'valid'));
  const evidenceComplete = linked.length > 0 && invalid.length === 0 &&
    linked.every((item) => item.integrity === 'valid' && item.registration_id === record.registration.id) &&
    sourceComplete && artifacts.length > 0 && artifacts.every((artifact) => linked.some((item) =>
      item.name === artifact.name && item.kind === 'measured' && item.path && item.integrity === 'valid'));
  const integrity = details.integrity !== false && !details.error && !list(details.missing_artifacts).length &&
    !list(details.missing_metrics).length;
  const measured = run?.state === 'succeeded' && ['passed', 'failed'].includes(verification?.state) &&
    linkedCorrectly && evidenceComplete && integrity;
  const criteria = list(spec.criteria);
  const outcomes = criteria.map((criterion) => {
    const actual = verification?.metrics?.[criterion.metric];
    if (!measured || !finite(actual) || !finite(criterion.threshold) || !OPS[criterion.op]) return null;
    const stored = list(details.criteria_results).find((result) => result.metric === criterion.metric &&
      result.op === criterion.op && result.threshold === criterion.threshold && result.actual === actual &&
      typeof result.passed === 'boolean');
    const evaluated = OPS[criterion.op](actual, criterion.threshold);
    return stored && stored.passed === evaluated ? evaluated : null;
  });
  const consistent = criteria.length > 0 && outcomes.every((value) => typeof value === 'boolean') &&
    (verification?.state === 'passed' ? outcomes.every((value) => value === true) : outcomes.some((value) => value === false));
  return {measured: measured && consistent, supported: measured && consistent && verification?.state === 'passed' && criteria.length > 0 &&
    outcomes.every((value) => value === true), outcomes, invalid,
    valid: evidence.filter((item) => item.integrity === 'valid'), evidence, linkedCorrectly, evidenceComplete};
}

function numericDomain(values) {
  const finiteValues = values.filter(finite);
  if (!finiteValues.length) return [0, 1];
  let min = Math.min(...finiteValues), max = Math.max(...finiteValues);
  // Padding makes both the measured point and every threshold visible; zero is not assumed.
  if (min === max) {
    const padding = Math.max(Math.abs(min) * 0.1, 1);
    if (finite(min - padding)) min -= padding;
    if (finite(max + padding)) max += padding;
  } else {
    const span = max - min;
    const padding = finite(span) ? span * 0.12 : 0;
    if (finite(min - padding)) min -= padding;
    if (finite(max + padding)) max += padding;
  }
  return [min, max];
}

function metricModels(record, workspace = '') {
  workspace = record?.workspace || workspace;
  const spec = record?.registration?.spec || {}, registration = record?.registration?.id || '';
  const support = supportFor(record), criteria = list(spec.criteria);
  return list(spec.metrics).filter((name) => typeof name === 'string').map((name) => {
    const actual = record?.verification?.metrics?.[name], value = finite(actual) ? actual : null;
    const tests = criteria.map((criterion, index) => ({criterion, index})).filter((item) => item.criterion.metric === name)
      .map(({criterion, index}) => ({op: criterion.op, threshold: finite(criterion.threshold) ? criterion.threshold : null,
        actual: value, passed: support.measured ? support.outcomes[index] : null,
        ref: reference(workspace, registration, `registration.spec.criteria[${index}]`,
          {run: record?.verification?.run_id || '', metric: name})}));
    return {name, label: clipText(spec.metric_metadata?.[name]?.label || spec.metric_metadata?.[name]?.display_name || name, 100),
      value, unit: unitFor(spec, name), criteria: tests,
      supported: support.measured && value !== null && tests.every((test) => test.passed !== null),
      ref: reference(workspace, registration, `verification.metrics.${name}`, {run: record?.verification?.run_id || ''}),
      domain: numericDomain([value, ...tests.map((test) => test.threshold)])};
  });
}

function trustModel(record, workspace, states) {
  const support = supportFor(record), registration = record?.registration?.id || '';
  let text = '독립 검증이 없어 현재 성공 주장을 확인할 수 없습니다.', tone = 'quiet';
  if (support.invalid.length) {
    text = `현재 원본 ${support.invalid.length}개의 누락·변조가 감지됐습니다. 과거 검증·채택 기록과 구분해야 합니다.`;
    tone = 'warn';
  } else if (support.supported) {
    text = '등록 기준을 독립 검증이 통과했고 연결된 실행 원본의 해시가 현재 일치합니다. 적용 범위를 함께 확인하세요.';
    tone = 'good';
  } else if (states.verification === 'failed' && support.measured) {
    text = '독립 검증에서 등록 기준 미달이 확인됐습니다. 실행 원본의 해시는 현재 일치합니다.';
    tone = 'bad';
  } else if (states.verification === 'failed') {
    text = '독립 검증 실패 기록은 있지만 현재 원본·등록 기준·검증 연결은 충분히 확인되지 않았습니다.';
    tone = 'warn';
  } else if (states.verification === 'passed') {
    text = '과거 검증 통과 기록은 있지만 현재 원본·등록 기준·검증 연결이 충분하지 않아 성공 주장은 미확인입니다.';
    tone = 'warn';
  } else if (states.verification === 'inconclusive') {
    text = '독립 검증은 미결입니다. 보존 파일의 해시 일치만으로 가설이 검증되지는 않습니다.';
  } else if (states.execution === 'unknown') {
    text = '실행 여부가 미확정입니다. 종료 증거를 확인하기 전에는 결과를 확정할 수 없습니다.';
  } else if (states.execution === 'failed') {
    text = '실행 실패 기록입니다. 실행 성공·독립 검증·가설 채택을 별도로 확인해야 합니다.';
    tone = 'bad';
  }
  const refs = [reference(workspace, registration, 'verification', {run: record?.verification?.run_id || ''}),
    ...support.evidence.map((item) => reference(workspace, registration, 'evidence.integrity', {evidence: item.id}))];
  return {supported: support.supported, invalidCount: support.invalid.length, validCount: support.valid.length,
    total: support.evidence.length, text, tone, refs};
}

function stageModel(states, trust, record, summary) {
  if (trust.invalidCount) return {text: '현재 원본 확인 필요', tone: 'warn'};
  if (states.execution === 'unknown') return {text: '실행 여부 확인 필요', tone: 'warn'};
  if (states.execution === 'running') return {text: '실행 진행 중', tone: 'warn'};
  if (states.execution === 'failed') return {text: '실행 실패 기록', tone: 'bad'};
  if (states.verification === 'failed') return {text: supportFor(record).measured ? '검증 기준 미달' : '독립 검증 실패 기록', tone: 'bad'};
  if (states.verification === 'inconclusive') return {text: '검증 미결', tone: 'quiet'};
  if (states.decision === 'adopted') return {text: trust.supported ? '채택 기록 · 적용 범위 확인' : '채택 기록 · 현재 근거 확인 필요', tone: trust.supported ? 'good' : 'warn'};
  if (states.decision === 'rejected') return {text: '기각 결정 기록', tone: 'bad'};
  if (states.decision === 'inconclusive') return {text: '미결 결정 기록', tone: 'quiet'};
  if (states.verification === 'passed') return {text: trust.supported ? '독립 검증 통과 · 결정 대기' : '과거 검증 통과 · 현재 근거 확인 필요', tone: trust.supported ? 'good' : 'warn'};
  if (list(summary?.missing_evidence).includes('independent verification')) return {text: '독립 검증 대기', tone: 'quiet'};
  if (record?.registration || summary?.id) return {text: '조건 고정 · 결과 증거 대기', tone: 'quiet'};
  return {text: '등록된 실험 없음', tone: 'quiet'};
}

function resourceModels(record, workspace) {
  const resources = record?.run?.resources || {}, registration = record?.registration?.id || '';
  const wallKnown = finite(resources.wall_seconds) && resources.wall_seconds >= 0;
  const tokens = finite(resources.external_tokens) && resources.external_tokens >= 0 ? resources.external_tokens
    : resources.tokens?.status === 'known' && finite(resources.tokens.value) && resources.tokens.value >= 0 ? resources.tokens.value : null;
  const model = resources.external_model_usage;
  const modelKnown = typeof model === 'string' && model.trim() !== '' && model !== 'unknown';
  return [{label: '실행 경과 시간', value: wallKnown ? `${resources.wall_seconds}초` : '미확인', known: wallKnown,
    ref: reference(workspace, registration, 'run.resources.wall_seconds')},
  {label: '외부 모델 사용', value: modelKnown ? clipText(model, 180) : '미확인', known: modelKnown,
    ref: reference(workspace, registration, 'run.resources.external_model_usage')},
  {label: '외부 토큰 사용', value: tokens === null ? '미확인' : `${tokens} 토큰`, known: tokens !== null,
    ref: reference(workspace, registration, finite(resources.external_tokens) ? 'run.resources.external_tokens' : 'run.resources.tokens')}];
}

function distribution(items, dimension, keys) {
  const counts = new Map(keys.map((key) => [key, 0]));
  for (const item of items) {
    const key = typeof item[dimension] === 'string' ? item[dimension] : 'unrecorded';
    counts.set(key, (counts.get(key) || 0) + 1);
  }
  return [...counts].map(([key, count]) => ({key, label: labelState(key, dimension), count}));
}

function lessonModels(memory, workspace) {
  return list(memory?.items).map((item, index) => {
    let claimText = '독립 검증 대기 · 기록 존재와 주장 검증은 별개', tone = 'quiet';
    if (item.evidence_integrity === 'invalid') {
      claimText = '현재 원본 누락·변조 · 과거 판정과 구분'; tone = 'warn';
    } else if (item.verification === 'failed') {
      claimText = item.evidence_integrity === 'valid' ? '독립 검증 실패 기록 · 현재 원본 해시 일치' : '독립 검증 실패 기록 · 현재 원본 미확인';
      tone = 'bad';
    } else if (item.claim_verified === true && item.verification === 'passed' && item.evidence_integrity === 'valid') {
      claimText = '독립 검증 통과 · 현재 원본 해시 일치'; tone = 'good';
    } else if (item.verification === 'passed') {
      claimText = '과거 검증 통과 · 현재 성공 주장 미확인'; tone = 'warn';
    } else if (item.verification === 'inconclusive') {
      claimText = '독립 검증 미결 · 추가 근거 필요';
    } else if (item.execution === 'unknown') {
      claimText = '실행 미확정 · 종료 증거 확인 필요';
    } else if (item.execution === 'failed') {
      claimText = '실행 실패 기록 · 독립 검증과 별도'; tone = 'bad';
    }
    return {title: clipText(item.summary || item.hypothesis || '등록된 시도', 110),
      summary: clipText(item.hypothesis || item.summary, 220), reason: clipText(item.reason || '결정 이유 미기록', 260),
      outcome: item.outcome || 'inconclusive', claimText, tone,
      conditions: conditions(item.conditions || {}).filter((entry) => ['비교 기준', '데이터 분할', 'Seed', '소스 버전'].includes(entry.label))
        .map(({label, value}) => ({label, value})),
      ref: reference(workspace, item.id, `memory.items[${index}]`, {goal: item.goal_id || '',
        goal_version: item.goal_version ?? null, revision: memory?.revision ?? null})};
  });
}

/** Deterministic, bounded text and exact numbers; the caller chooses how many cards to reveal. */
export function buildViewModel({snapshot, record, goal, summary, memory, records, limit, offset, workspace = ''} = {}) {
  snapshot = unwrap(snapshot) || {}; record = unwrap(record) || null; memory = unwrap(memory) || {};
  workspace = record?.workspace || workspace;
  const status = snapshot.status || snapshot, spec = record?.registration?.spec || {};
  const registration = record?.registration?.id || '', hypotheses = list(status.hypotheses);
  const selectedSummary = summary?.id === registration || (!registration && summary?.id) ? summary
    : list(status.registrations).find((item) => item.id === registration) || {};
  const suppliedGoal = unwrap(goal);
  const selectedGoal = (suppliedGoal && (!registration || suppliedGoal.id === record.registration.goal_id) ? suppliedGoal : null) ||
    list(status.goals).find((item) => item.id === record?.registration?.goal_id) ||
    (!registration ? list(status.goals)[0] : null) || {};
  const hypothesis = record?.hypothesis || hypotheses.find((item) => item.id === record?.registration?.hypothesis_id) ||
    (!registration ? hypotheses.find((item) => item.goal_id === selectedGoal.id) : null) || {};
  const states = statesFor(record, selectedSummary), trust = trustModel(record, workspace, states);
  const items = list(status.registrations), count = items.length;
  const total = Number.isInteger(status.total) && status.total >= 0 ? status.total : count;
  const pageOffset = Number.isInteger(status.offset) && status.offset >= 0 ? status.offset : Number.isInteger(offset) && offset >= 0 ? offset : 0;
  const metrics = metricModels(record, workspace), conditionModels = conditions(spec, workspace, registration);
  const blockers = list(selectedSummary.missing_evidence).map((text, index) => ({text: MISSING_LABELS[text] || clipText(text, 180),
    ref: reference(workspace, registration, `status.registrations.missing_evidence[${index}]`, {value: text})}));
  if (trust.invalidCount > 0) {
    const invalid = list(record?.evidence).filter((item) => ['tampered', 'missing'].includes(item.integrity));
    blockers.unshift({text: `현재 증거 원본 ${trust.invalidCount}개의 누락·변조가 감지되어 복원 또는 원본 대조가 필요합니다.`,
      ref: reference(workspace, registration, 'evidence.integrity',
        {evidence: invalid[0]?.id, evidence_ids: invalid.map((item) => item.id)})});
  }
  if (record && finite(status.revision) && finite(record.revision) && status.revision !== record.revision) {
    blockers.push({text: '조회 시점이 달라 화면 갱신이 필요합니다.', ref: reference(workspace, registration, 'revision', {revision: record.revision})});
  }
  if (finite(status.revision) && finite(memory.revision) && status.revision !== memory.revision) {
    blockers.push({text: '기억의 조회 시점이 달라 화면 갱신이 필요합니다.', ref: reference(workspace, registration, 'memory.revision', {revision: memory.revision})});
  }
  const timelineItems = list(snapshot.events).map((event) => ({title: EVENT_LABELS[event.action] || clipText(event.action || '연구 사건', 80),
    created: finite(event.created) ? event.created : null, revision: finite(event.revision) ? event.revision : null,
    ref: reference(workspace, '', 'snapshot.events', {event: event.id, target: event.target, revision: event.revision})}))
    .sort((a, b) => (a.created ?? Infinity) - (b.created ?? Infinity) || (a.revision ?? Infinity) - (b.revision ?? Infinity));
  const eventTotal = Number.isInteger(snapshot.event_total) && snapshot.event_total >= 0 ? snapshot.event_total : timelineItems.length;
  const questionRefs = [reference(workspace, registration, 'goal.title', {goal: selectedGoal.id || ''}),
    reference(workspace, registration, 'hypothesis.statement', {hypothesis: hypothesis.id || ''}),
    reference(workspace, registration, 'registration.spec.change'),
    selectedGoal.description ? reference(workspace, registration, 'goal.description', {goal: selectedGoal.id || ''})
      : reference(workspace, registration, 'registration.spec.data_split')];
  const model = {question: {title: clipText(selectedGoal.title || '연구 목표 미기록', 160),
    hypothesis: clipText(hypothesis.statement || '가설 미기록', 240), change: clipText(spec.change || '실험 변경점 미등록', 200),
    scope: clipText(selectedGoal.description || asText(spec.data_split?.evaluation || spec.data_split), 180), refs: questionRefs},
  states, stage: stageModel(states, trust, record, selectedSummary), trust, blockers, metrics, conditions: conditionModels,
  resources: resourceModels(record, workspace), scope: {count, total, offset: pageOffset,
    label: `이 조회 ${count}건 / 전체 등록 ${total}건${count ? ` · ${pageOffset + 1}–${pageOffset + count}번째` : ''}`},
  distribution: {execution: distribution(items, 'execution', ['registered', 'running', 'succeeded', 'failed', 'cancelled', 'unknown']),
    verification: distribution(items, 'verification', ['pending', 'passed', 'failed', 'inconclusive']),
    decision: distribution(items, 'decision', ['pending', 'adopted', 'rejected', 'inconclusive'])},
  timeline: {items: timelineItems, total: eventTotal,
    label: snapshot.event_scope === 'selected_registration'
      ? `선택 실험 연결 사건 ${timelineItems.length}건 / 전체 연결 ${eventTotal}건`
      : `최근 조회 사건 ${timelineItems.length}건 / 전체 ${eventTotal}건`},
  lessons: lessonModels(memory, workspace)};
  model.refs = [...questionRefs, ...trust.refs, ...blockers.map((item) => item.ref), ...metrics.flatMap((item) => [item.ref, ...item.criteria.map((criterion) => criterion.ref)]),
    ...conditionModels.map((item) => item.ref), ...model.resources.map((item) => item.ref), ...timelineItems.map((item) => item.ref), ...model.lessons.map((item) => item.ref),
    reference(workspace, '', 'status.registrations', {offset: pageOffset, limit: status.limit || limit || 20}),
    reference(workspace, '', 'memory', {offset: memory.offset || 0, limit: memory.limit || 20})];
  const report = snapshot.report || {};
  model.report = reportModel(report, selectedGoal, workspace, status.revision);
  model.metrics = metrics.map(metric => ({...metric, interpretation: interpretMetric(metric)}));
  const registeredPrimary = typeof spec.primary_metric === 'string'
    ? model.metrics.find(metric => metric.name === spec.primary_metric) : null;
  const unmetMetric = model.metrics.find(metric => metric.supported && metric.criteria.some(criterion => criterion.passed === false));
  model.primaryMetric = registeredPrimary || unmetMetric || model.metrics[0] || null;
  model.primaryMetricSelection = registeredPrimary
    ? {method: 'registered_primary', reason: '사전등록 핵심 지표', refs: [reference(workspace, registration, 'registration.spec.primary_metric')]}
    : unmetMetric ? {method: 'unmet_registered_criterion', reason: '미충족 등록 기준 우선',
      refs: unmetMetric.criteria.filter(criterion => criterion.passed === false).map(criterion => criterion.ref)}
      : {method: model.primaryMetric ? 'registration_order' : 'none',
        reason: model.primaryMetric ? '등록 순서의 첫 지표' : '등록 지표 없음',
        refs: [reference(workspace, registration, 'registration.spec.metrics')]};
  model.refs.push(...model.primaryMetricSelection.refs);
  model.flow = flowModel(record, selectedGoal, hypothesis, states, trust, selectedSummary, workspace);
  const relatedRecords = (list(records).length ? records : list(report.records))
    .map(sourceRecord => ({...sourceRecord, workspace: sourceRecord.workspace || workspace}));
  model.graph = relationshipModel(relatedRecords.length ? relatedRecords : record ? [record] : [], selectedGoal,
    registration, workspace, report.records_total);
  model.stability = repeatModels(relatedRecords.length ? relatedRecords : record ? [record] : []);
  model.judgment = {goal: {id: selectedGoal.id || null, version: selectedGoal.version ?? null, state: model.report.state},
    metrics: model.metrics.map(metric => ({name: metric.name, unit: metric.unit, value: metric.value,
      conditions: conditionModels, criteria: metric.criteria, interpretation: metric.interpretation, ref: metric.ref})),
    conclusions: model.graph.conclusions, repeatMeasurements: model.stability,
    unanswered: [...blockers, ...model.graph.gaps], recovery: states.execution === 'unknown'
      ? {state: 'unknown', originalRun: record?.run?.id || null, required: '원 실행의 종료 증거 확인',
        ref: reference(workspace, registration, 'run.state', {run: record?.run?.id || ''})} : null,
    resources: model.report, evidence: list(record?.evidence).map(item => ({kind: item.kind, kindLabel: labelState(item.kind),
      integrity: item.integrity, originalRun: item.run_id || null, originalEvidence: item.id,
      ref: reference(workspace, registration, 'evidence', {evidence: item.id, run: item.run_id || ''})})),
    executionAudit: {...(isObject(report.execution_audit) ? JSON.parse(JSON.stringify(report.execution_audit))
      : {requests_received_count: null, replay_attempt_count: null, request_keys_total: null, status: 'unrecorded'}),
      ref: reference(workspace, '', 'snapshot.report.execution_audit', {goal: selectedGoal.id || '',
        goal_version: model.report.goalVersion, revision: report.revision ?? status.revision ?? null})},
    evidenceIndependence: 'not_established',
    duplicatePrevention: '실행 요청 중복 방지는 CLI 규칙이며 반복 조회는 추가 실행이나 독립 확인으로 세지 않습니다.'};
  model.refs.push(...model.report.refs, ...model.flow.nodes.flatMap(node => node.refs),
    ...model.flow.edges.map(edge => edge.ref), ...model.graph.refs, ...model.stability.flatMap(group => group.refs),
    ...model.judgment.evidence.map(item => item.ref), model.judgment.executionAudit.ref);
  if (report.consistent === false) model.blockers.push({text: '목표 보고의 원본 조회 버전이 달라 갱신이 필요합니다.',
    ref: reference(workspace, '', 'snapshot.report.consistent', {revision: report.revision})});
  if (Number.isInteger(record?.registration?.goal_version) && Number.isInteger(model.report.goalVersion) &&
      record.registration.goal_version !== model.report.goalVersion) model.blockers.push({
    text: `이 실험은 목표 버전 ${record.registration.goal_version}에 등록됐습니다. 현재 목표 버전 ${model.report.goalVersion}과 적용 범위를 대조해야 합니다.`,
    ref: reference(workspace, registration, 'registration.goal_version', {goal_version: record.registration.goal_version})});
  model.judgment.unanswered = [...model.blockers, ...model.graph.gaps];
  model.refs.push(...model.blockers.map(item => item.ref));
  const sourceRecords = new Map([...relatedRecords, ...(record ? [record] : [])].map(sourceRecord =>
    [`${sourceRecord.workspace || workspace}:${sourceRecord.registration?.id}`, sourceRecord]));
  const stamp = value => {
    if (Array.isArray(value)) { value.forEach(stamp); return; }
    if (!isObject(value)) return;
    if (typeof value.field === 'string' && typeof value.workspace === 'string') {
      const sourceRecord = sourceRecords.get(`${value.workspace}:${value.registration}`);
      value.revision ??= sourceRecord?.revision ?? status.revision ?? record?.revision ?? null;
      value.goal_version ??= value.field.startsWith('goal.') || !sourceRecord
        ? model.report.goalVersion : sourceRecord.registration.goal_version ?? model.report.goalVersion;
      if (sourceRecord?.registration?.fingerprint) value.registration_fingerprint ??= sourceRecord.registration.fingerprint;
    }
    Object.values(value).forEach(stamp);
  };
  model.sourceVersion = {revision: status.revision ?? record?.revision ?? null, goal: selectedGoal.id || null,
    goal_version: model.report.goalVersion, registration_goal_version: record?.registration?.goal_version ?? null,
    registration_fingerprint: record?.registration?.fingerprint ?? null};
  model.observatory = observatoryModel(model, record, selectedGoal, hypothesis,
    relatedRecords.length ? relatedRecords : record ? [record] : [], workspace);
  model.refs.push(...model.observatory.refs);
  if (snapshot.registration) model.refs.push(reference(workspace, snapshot.registration, 'snapshot.registration',
    {event_scope: snapshot.event_scope || 'workspace'}));
  stamp(model);
  return model;
}

function numberText(value) {
  if (!finite(value)) return '미확인';
  if (value !== 0 && (Math.abs(value) < 1e-4 || Math.abs(value) >= 1e9)) return value.toExponential(5)
    .replace(/(\.\d*?[1-9])0+e/u, '$1e').replace(/\.0+e/u, 'e');
  return new Intl.NumberFormat('ko-KR', {maximumFractionDigits: 5}).format(value);
}

function readableMetricName(name) {
  return clipText(String(name || '').replace(/[_-]+/gu, ' ').replace(/([a-z\d])([A-Z])/gu, '$1 $2'), 100);
}

// Display translations for two explicit metric terms only. These labels provide no unit, range, formula or success criterion.
// Unknown terms retain their readable registered name; an explicitly registered display label always takes precedence.
const METRIC_DISPLAY_TRANSLATIONS = Object.freeze({satisfaction_pct: '만족도', calculation_matches: '계산 일치'});

function metricLabelDetails(name, spec = {}) {
  const metadata = spec.metric_metadata?.[name] || {};
  const labelField = ['label', 'display_name'].find(field => typeof metadata[field] === 'string' && metadata[field].trim());
  const translated = Object.hasOwn(METRIC_DISPLAY_TRANSLATIONS, name) ? METRIC_DISPLAY_TRANSLATIONS[name] : null;
  return {label: clipText(labelField ? metadata[labelField] : translated || readableMetricName(name), 100),
    labelSource: labelField ? 'registration_metadata' : translated ? 'display_translation_of_metric_name' : 'name_readability', labelField};
}

/** A display string only: explicit frozen label, two translated terms, then readable raw name. */
export function displayMetricLabel(name, spec = {}) {
  return metricLabelDetails(name, spec).label;
}

/** Compact labels never supply undeclared units, rewrite criteria, or turn a reported lifecycle into verification. */
function observatoryMetric(metric, spec = {}, selection = null, invalidCount = 0) {
  if (!metric) return null;
  const display = metricLabelDetails(metric.name, spec);
  const status = invalidCount ? 'invalid' : metric.supported ? 'measured' : metric.value === null ? 'unknown' : 'historical';
  const criteria = metric.criteria.map(criterion => ({op: criterion.op, threshold: criterion.threshold,
    thresholdText: numberText(criterion.threshold), passed: criterion.passed, ref: {...criterion.ref}}));
  return {name: metric.name, label: display.label, labelSource: display.labelSource, value: metric.value,
    valueText: numberText(metric.value), unit: metric.unit, unitKnown: metric.unit !== '단위 미등록', status,
    criteria, domain: [...metric.domain], selection: selection ? {method: selection.method, reason: selection.reason,
      refs: selection.refs.map(ref => ({...ref}))} : null,
    refs: [{...metric.ref}, ...criteria.map(criterion => ({...criterion.ref})),
      ...(display.labelSource === 'display_translation_of_metric_name' ? [reference(metric.ref.workspace, metric.ref.registration, 'registration.spec.metrics',
        {metric: metric.name, display_transform: 'display_translation_of_metric_name'})] : []),
      ...(display.labelField ? [reference(metric.ref.workspace, metric.ref.registration,
        `registration.spec.metric_metadata.${metric.name}.${display.labelField}`)] : [])]};
}

function toneForState(state, dimension, currentSupport = false) {
  if (['tampered', 'missing', 'unknown'].includes(state)) return 'warn';
  if (['failed', 'rejected'].includes(state)) return 'bad';
  if (dimension === 'execution' && state === 'succeeded') return 'quiet';
  if (['passed', 'adopted'].includes(state)) return currentSupport ? 'good' : 'warn';
  return 'quiet';
}

function observatoryModel(model, record, goal, hypothesis, records, workspace) {
  const spec = record?.registration?.spec || {}, registration = record?.registration?.id || '';
  const metric = observatoryMetric(model.primaryMetric, spec, model.primaryMetricSelection, model.trust.invalidCount);
  const uncertainty = [], addUncertainty = (text, kind, refs) => {
    if (!uncertainty.some(item => item.kind === kind)) uncertainty.push({text: clipText(text, 110), kind, refs});
  };
  for (const blocker of model.blockers) {
    const kind = blocker.ref.field;
    const text = kind === 'evidence.integrity' ? '원본 누락·변조 확인 필요'
      : kind === 'registration.goal_version' ? '등록 당시 목표와 현재 목표의 적용 범위 확인 필요'
        : kind.includes('revision') || kind === 'snapshot.report.consistent' ? '조회 시점 불일치 · 화면 갱신 필요' : blocker.text;
    addUncertainty(text, kind, [{...blocker.ref}]);
  }
  if (metric && !metric.unitKnown) addUncertainty('선택 지표의 단위가 사전등록되지 않음', 'metric_unit',
    [reference(workspace, registration, 'registration.spec.metric_metadata', {metric: metric.name}),
      reference(workspace, registration, 'registration.spec.metric_units', {metric: metric.name}),
      reference(workspace, registration, 'registration.spec.units', {metric: metric.name})]);
  if (metric && ['historical', 'unknown'].includes(metric.status)) addUncertainty('현재 측정값의 독립 검증 근거 미확인', 'measurement_support', model.trust.refs.map(ref => ({...ref})));
  if (metric && !metric.criteria.length) addUncertainty('선택 지표의 성공 기준 미등록', 'metric_criteria',
    [reference(workspace, registration, 'registration.spec.criteria', {metric: metric.name})]);
  if (new Set(records.map(item => item.run?.id).filter(Boolean)).size > 1) addUncertainty('반복 실행의 독립성·일반화는 확인되지 않음', 'independence',
    records.filter(item => item.run?.id).map(item => reference(item.workspace || workspace, item.registration.id,
      'run.id', {run: item.run.id})));
  let bottleneck = null;
  const bottleneckRef = field => [reference(workspace, registration, field, {run: record?.run?.id || ''})];
  if (model.trust.invalidCount) bottleneck = {text: '원본 복원 또는 대조 필요', tone: 'warn', kind: 'integrity',
    refs: model.trust.refs.map(ref => ({...ref}))};
  else if (model.states.execution === 'unknown') bottleneck = {text: '원 실행의 종료 증거 필요', tone: 'warn', kind: 'execution_unknown', refs: bottleneckRef('run.state')};
  else if (model.states.execution === 'running') bottleneck = {text: '실행 종료 증거 대기', tone: 'quiet', kind: 'running', refs: bottleneckRef('run.state')};
  else if (model.states.execution === 'failed') bottleneck = {text: '실행 실패 원인 확인 필요', tone: 'bad', kind: 'execution_failed', refs: bottleneckRef('run.reason')};
  else if (model.metrics.some(item => item.supported && item.criteria.some(criterion => criterion.passed === false))) bottleneck = {
    text: '사전등록 기준 미충족', tone: 'bad', kind: 'criterion_unmet',
    refs: model.metrics.flatMap(item => item.criteria.filter(criterion => criterion.passed === false).map(criterion => ({...criterion.ref})))};
  else if (model.states.verification === 'failed') bottleneck = {text: '검증 실패 기록 · 현재 판정 근거 확인 필요', tone: 'warn', kind: 'verification_failed', refs: bottleneckRef('verification')};
  else if (model.blockers.length) bottleneck = {text: clipText(model.blockers[0].text, 90), tone: 'warn', kind: 'missing_evidence', refs: [{...model.blockers[0].ref}]};
  else if (model.states.verification === 'pending' && record?.registration) bottleneck = {text: '독립 검증 증거 대기', tone: 'quiet', kind: 'verification_pending', refs: bottleneckRef('verification')};
  else if (model.states.verification === 'inconclusive') bottleneck = {text: '독립 검증 미결 · 추가 근거 필요', tone: 'quiet', kind: 'verification_inconclusive', refs: bottleneckRef('verification')};
  else if (['passed', 'adopted'].some(state => Object.values(model.states).includes(state)) && !model.trust.supported) bottleneck = {text: '과거 판정의 현재 원본 근거 확인 필요', tone: 'warn', kind: 'historical_support', refs: model.trust.refs.map(ref => ({...ref}))};
  else if (model.states.decision === 'pending' && record?.verification) bottleneck = {text: '외부 에이전트의 결정 기록 대기', tone: 'quiet', kind: 'decision_pending', refs: bottleneckRef('decision')};
  const focus = Object.fromEntries(model.flow.nodes.map(node => [node.key, {title: node.title, text: node.text,
    state: node.state, stateLabel: labelState(node.state, node.key === 'experiment' ? 'execution' : node.key),
    historical: Boolean(node.historical),
    tone: toneForState(node.state, node.key === 'experiment' ? 'execution' : node.key, model.trust.supported),
    lines: [], refs: node.refs.map(ref => ({...ref}))}]));
  if (focus.verification.historical) focus.verification.stateLabel = '과거 검증 통과 · 현재 근거 미확인';
  if (focus.conclusion.historical) focus.conclusion.stateLabel = '과거 채택 · 현재 근거 미확인';
  focus.hypothesis.text = clipText(hypothesis.statement || '가설 미기록', 220);
  focus.hypothesis.lines = [clipText(model.question.scope, 120)];
  focus.experiment.text = clipText(spec.change || '사전등록된 실험 없음', 180);
  focus.experiment.lines = record?.registration ? [`Seed ${asText(spec.seed)}`, clipText(asText(spec.comparison), 120)] : [];
  focus.evidence.lines = [`현재 원본 ${model.trust.validCount}/${model.trust.total}개 해시 일치`,
    '파일 무결성과 가설 검증은 별개'];
  focus.evidence.refs.push(...model.trust.refs.map(ref => ({...ref})));
  focus.verification.text = record?.verification ? model.trust.invalidCount ? '현재 원본 확인이 필요합니다.'
    : model.metrics.some(item => item.supported && item.criteria.some(criterion => criterion.passed === false)) ? '고정 기준에서 미달이 확인됐습니다.'
      : model.trust.supported ? '고정된 등록 기준을 통과했습니다.' : '검증 기록의 현재 근거를 확인해야 합니다.'
    : '독립 검증이 아직 기록되지 않았습니다.';
  focus.verification.lines = model.metrics.slice(0, 3).map(item => {
    const projected = observatoryMetric(item, spec, null, model.trust.invalidCount);
    return `${projected.label} · ${projected.valueText} ${projected.unit} · ${projected.criteria.some(criterion => criterion.passed === false) ? '기준 미충족'
      : projected.criteria.length && projected.criteria.every(criterion => criterion.passed === true) ? '기준 충족' : '판정 미확인'}`;
  });
  focus.verification.refs.push(...model.metrics.flatMap(item => [item.ref, ...item.criteria.map(criterion => criterion.ref)]).map(ref => ({...ref})));
  focus.conclusion.text = clipText(record?.decision?.reason || '가설 결정 이유 미기록', 200);
  focus.conclusion.lines = ['선택 실험의 결정 · 전체 연구 상태와 구분'];
  const originals = [], seen = new Set();
  for (const item of records) if (item?.registration?.id && !seen.has(item.registration.id)) {
    seen.add(item.registration.id); originals.push(item);
  }
  if (record?.registration && !seen.has(registration)) originals.unshift(record);
  const selectedRecords = [...originals.filter(item => item.registration.id === registration),
    ...originals.filter(item => item.registration.id !== registration)].slice(0, 6);
  const ordinals = new Map(originals.map((item, index) => [item.registration.id, index + 1]));
  const attempts = {items: selectedRecords.map(item => {
    const ws = item.workspace || workspace, sourceSpec = item.registration.spec || {}, states = statesFor(item),
      metrics = metricModels(item, ws), sourceSupport = supportFor(item);
    const primary = sourceSpec.primary_metric ? metrics.find(candidate => candidate.name === sourceSpec.primary_metric) : null;
    const chosen = primary || metrics.find(candidate => candidate.supported && candidate.criteria.some(criterion => criterion.passed === false)) || metrics[0];
    const ordinal = ordinals.get(item.registration.id);
    return {registration: item.registration.id, hypothesis: item.registration.hypothesis_id || null, ordinal,
      selected: item.registration.id === registration, title: `시도 ${ordinal} · Seed ${Number.isInteger(sourceSpec.seed) ? sourceSpec.seed : '미확인'}`,
      description: clipText(sourceSpec.change || item.hypothesis?.statement || '등록된 시도', 90),
      seed: Number.isInteger(sourceSpec.seed) ? sourceSpec.seed : null, states,
      metric: observatoryMetric(chosen, sourceSpec, null, sourceSupport.invalid.length),
      refs: [reference(ws, item.registration.id, 'registration.spec.change'), reference(ws, item.registration.id, 'registration.spec.seed'),
        reference(ws, item.registration.id, 'run.state', {run: item.run?.id || ''}),
        reference(ws, item.registration.id, 'verification.state', {run: item.verification?.run_id || ''}),
        reference(ws, item.registration.id, 'decision.state')]};
  }), shown: selectedRecords.length, total: Math.max(model.scope.total, originals.length),
    ordinalSource: 'current_query_order', scope: '조회한 원본 시도 · 번호는 조회 순서 · 조건이 다르면 성능 순위로 비교하지 않음'};
  const graph = observatoryGraph(selectedRecords, registration, workspace, attempts.total, ordinals);
  const summary = {question: clipText(model.question.title, 140), state: model.report.state, stateLabel: model.report.stateLabel,
    stateSource: model.report.stateSource, stateNote: model.report.lifecycleReported ? '외부 연구 상태 보고' : '연구 상태 기록',
    stage: model.stage.text, tone: model.stage.tone,
    refs: [...model.question.refs.filter(ref => ref.field === 'goal.title').map(ref => ({...ref})), ...model.report.refs.map(ref => ({...ref}))]};
  return {summary, metric, bottleneck, uncertainty, focus, attempts, graph,
    refs: [...summary.refs, ...(metric?.refs || []), ...(bottleneck?.refs || []), ...uncertainty.flatMap(item => item.refs),
      ...Object.values(focus).flatMap(item => item.refs), ...attempts.items.flatMap(item => [...item.refs, ...(item.metric?.refs || [])]), ...graph.refs]};
}

/** Shared persisted IDs make a shared graph; no placeholder verdict nodes or inferred causal edges. */
function observatoryGraph(records, selected, workspace, total, ordinals) {
  const nodes = new Map(), edges = new Map();
  const addNode = (node, registration) => {
    const existing = nodes.get(node.id);
    if (existing) {
      existing.registrations = [...new Set([...existing.registrations, registration])];
      existing.selected ||= node.selected;
      existing.refs.push(...node.refs);
    } else nodes.set(node.id, {...node, registrations: [registration]});
  };
  const addEdge = (from, to, kind, label, refs, chosen) => {
    const id = `${from}->${to}:${kind}`, existing = edges.get(id);
    if (existing) {existing.selected ||= chosen; existing.refs.push(...refs);}
    else edges.set(id, {id, from, to, kind, label, recorded: true, selected: chosen, refs});
  };
  for (const record of records) {
    const reg = record.registration, ws = record.workspace || workspace, chosen = reg.id === selected,
      states = statesFor(record), trust = trustModel(record, ws, states), hyp = record.hypothesis;
    const experimentId = `experiment:${ws}:${reg.id}`;
    addNode({id: experimentId, kind: 'experiment', title: '실험', ordinal: ordinals.get(reg.id),
      seed: Number.isInteger(reg.spec?.seed) ? reg.spec.seed : null,
      text: clipText(reg.spec?.change || '사전등록된 시도', 72), state: states.execution,
      stateLabel: labelState(states.execution, 'execution'), tone: toneForState(states.execution, 'execution'), selected: chosen,
      refs: [reference(ws, reg.id, 'registration', {run: record.run?.id || ''}), reference(ws, reg.id, 'run.state', {run: record.run?.id || ''})]}, reg.id);
    if (hyp?.id && reg.hypothesis_id === hyp.id) {
      const id = `hypothesis:${ws}:${hyp.id}`;
      addNode({id, kind: 'hypothesis', title: '가설', text: clipText(hyp.statement || '등록 가설', 100),
        state: 'proposed', stateLabel: labelState('proposed'), tone: 'quiet', selected: chosen,
        refs: [reference(ws, reg.id, 'hypothesis.statement', {hypothesis: hyp.id})]}, reg.id);
      addEdge(id, experimentId, 'registered_for', '사전등록', [reference(ws, reg.id, 'registration.hypothesis_id', {hypothesis: hyp.id})], chosen);
    }
    const runLinked = !!(record.run?.id && record.run.registration_id === reg.id);
    const measuredArtifacts = list(record.evidence).filter(item => item.id && item.kind === 'measured' && runLinked &&
      item.run_id === record.run.id && item.registration_id === reg.id && list(reg.spec?.artifacts).some(artifact => artifact.name === item.name));
    for (const evidence of measuredArtifacts) {
      const id = `evidence:${ws}:${evidence.id}`;
      addNode({id, kind: 'evidence', title: '산출물', text: clipText(evidence.name || '등록 산출물', 72),
        state: evidence.integrity || 'unknown', stateLabel: evidence.integrity ? labelState(evidence.integrity) : '원본 미확인',
        tone: ['tampered', 'missing'].includes(evidence.integrity) ? 'warn' : 'quiet', selected: chosen,
        refs: [reference(ws, reg.id, 'evidence', {evidence: evidence.id, run: evidence.run_id})]}, reg.id);
      addEdge(experimentId, id, 'produced', '실행 원본', [reference(ws, reg.id, 'evidence.run_id', {evidence: evidence.id, run: evidence.run_id})], chosen);
    }
    const verificationLinked = runLinked && record.verification?.run_id === record.run.id;
    if (verificationLinked) {
      const id = `verification:${ws}:${record.run.id}`;
      addNode({id, kind: 'verification', title: '검증', text: trust.invalidCount ? '현재 원본 확인 필요' : supportFor(record).measured
        ? states.verification === 'failed' ? '등록 기준 미충족' : '등록 기준 통과' : '현재 판정 근거 미확인',
        state: states.verification, historical: states.verification === 'passed' && !trust.supported,
        stateLabel: states.verification === 'passed' && !trust.supported ? '과거 검증 통과' : labelState(states.verification, 'verification'),
        tone: toneForState(states.verification, 'verification', trust.supported), selected: chosen,
        refs: [reference(ws, reg.id, 'verification', {run: record.verification.run_id})]}, reg.id);
      addEdge(experimentId, id, 'evaluated_run', '실행 검사', [reference(ws, reg.id, 'verification.run_id', {run: record.verification.run_id})], chosen);
      // Artifact edges show the registered run inputs, not proof of scientific causality or an invented per-file verdict.
      for (const evidence of measuredArtifacts) addEdge(`evidence:${ws}:${evidence.id}`, id, 'registered_artifact', '등록 산출물',
        [reference(ws, reg.id, 'registration.spec.artifacts'), reference(ws, reg.id, 'evidence.run_id', {evidence: evidence.id, run: evidence.run_id})], chosen);
    }
    if (record.decision?.registration_id === reg.id) {
      const id = `conclusion:${ws}:${reg.id}`;
      addNode({id, kind: 'conclusion', title: '결정', text: clipText(record.decision.reason || '결정 이유 미기록', 100),
        state: states.decision, historical: states.decision === 'adopted' && !trust.supported,
        stateLabel: states.decision === 'adopted' && !trust.supported ? '과거 채택' : labelState(states.decision),
        tone: toneForState(states.decision, 'decision', trust.supported), selected: chosen,
        refs: [reference(ws, reg.id, 'decision')]}, reg.id);
      addEdge(experimentId, id, 'decision_for', '가설 결정', [reference(ws, reg.id, 'decision.registration_id')], chosen);
    }
  }
  const renderedNodes = [...nodes.values()], renderedEdges = [...edges.values()];
  return {nodes: renderedNodes, edges: renderedEdges, shown: records.length, total,
    truncated: total > records.length, scope: '조회한 공유 가설과 실제 연결 · 과학적 인과관계·독립성 추정 없음',
    refs: [...renderedNodes.flatMap(node => node.refs), ...renderedEdges.flatMap(edge => edge.refs)]};
}

/** Conversion is permitted only by explicit units; neither metric names nor values imply percentages. */
export function interpretMetric(metric) {
  const ratio = metric.unit === 'ratio', percent = ['%', 'percent', 'percentage'].includes(metric.unit);
  const scale = ratio ? 100 : 1, unit = ratio || percent ? '%' : metric.unit;
  const value = finite(metric.value) ? metric.value * scale : null;
  const criteria = list(metric.criteria).map(criterion => {
    const target = finite(criterion.threshold) ? criterion.threshold * scale : null;
    const delta = value !== null && target !== null ? value - target : null;
    const deltaUnit = ratio || percent ? '%p' : metric.unit;
    const direction = delta === null ? '차이 미확인' : delta === 0 ? '기준과 일치'
      : `기준보다 ${numberText(Math.abs(delta))}${deltaUnit === '단위 미등록' ? ' (단위 미등록)' : ' ' + deltaUnit} ${delta < 0 ? '낮음' : '높음'}`;
    return {op: criterion.op, target, delta, unit, deltaUnit, passed: criterion.passed,
      text: `기준 ${criterion.op} ${numberText(target)} ${unit} · ${direction}`,
      ref: criterion.ref};
  });
  return {value, unit, currentSupported: metric.supported, criteria,
    text: value === null ? '측정값 미확인' : `${metric.supported ? '측정' : '과거 수치'} ${numberText(value)} ${unit}${criteria.length ? ' · ' + criteria[0].text : ' · 등록 기준 없음'}`};
}

function reportModel(raw, fallbackGoal, workspace, revision) {
  const goal = raw.goal || fallbackGoal || {}, lifecycle = goal.lifecycle || {}, observed = finite(raw.observed_at) ? raw.observed_at : null;
  const state = ['active', 'paused', 'completed', 'cancelled'].includes(goal.state) ? goal.state : 'unknown';
  const created = finite(goal.created) ? goal.created : null;
  const terminal = ['paused', 'completed', 'cancelled'].includes(state);
  const end = terminal ? finite(lifecycle.created) ? lifecycle.created : null : observed;
  const elapsed = created !== null && end !== null && end >= created ? end - created : null;
  const wall = raw.totals?.run_wall_seconds || {}, resources = raw.resources || {};
  const entries = Array.isArray(resources.cost_by_currency) ? resources.cost_by_currency
    : Object.entries(resources.cost_by_currency || {}).map(([currency, amount]) => ({currency, amount}));
  const cost = entries.filter(item => typeof item.currency === 'string' && finite(item.amount) && item.amount >= 0)
    .map(item => ({currency: item.currency, amount: item.amount, label: `${numberText(item.amount)} ${item.currency}`}));
  const known = Number.isInteger(resources.known_count) ? resources.known_count : 0;
  const unknown = Number.isInteger(resources.unknown_count) ? resources.unknown_count : null;
  const refs = [reference(workspace, '', 'snapshot.report', {goal: goal.id || '', goal_version: goal.version ?? null, revision}),
    reference(workspace, '', 'goal.lifecycle', {goal: goal.id || '', goal_version: lifecycle.goal_version ?? goal.version ?? null}),
    reference(workspace, '', 'goal.resources', {goal: goal.id || '', scope: resources.scope || 'recorded_external_observations_only'})];
  const rawConstraints = goal.brief?.resource_constraints;
  const constraintEntries = Array.isArray(rawConstraints) ? rawConstraints.map((value, index) => [String(index), value])
    : isObject(rawConstraints) ? Object.entries(rawConstraints)
      : typeof rawConstraints === 'string' ? [['statement', rawConstraints]] : [];
  const constraintLabels = {cost: '비용 제약', tokens: '토큰 제약', time: '시간 제약',
    whole_research_iteration_limit: '전체 연구 반복 한도', statement: '기록된 자원 제약'};
  const constraintDetails = constraintEntries.map(([key, value]) => ({key,
    label: constraintLabels[key] || (Array.isArray(rawConstraints) ? `기록된 자원 제약 ${Number(key) + 1}` : clipText(key, 100)),
    value: value === undefined ? null : JSON.parse(JSON.stringify(value)),
    status: value === null || value === undefined || value === 'unknown' || value?.status === 'unknown' ? 'unknown' : 'recorded',
    ref: reference(workspace, '', Array.isArray(rawConstraints) ? `goal.brief.resource_constraints[${key}]`
      : key === 'statement' && typeof rawConstraints === 'string' ? 'goal.brief.resource_constraints' : `goal.brief.resource_constraints.${key}`,
    {goal: goal.id || '', goal_version: goal.version ?? null})}));
  refs.push(...constraintDetails.map(item => item.ref));
  const runs = list(raw.runs).filter(run => run && typeof run.id === 'string'), seen = new Set();
  const uniqueRuns = runs.filter(run => !seen.has(run.id) && seen.add(run.id));
  const runTrend = uniqueRuns.filter(run => finite(run.finished) && finite(run.resources?.wall_seconds) && run.resources.wall_seconds >= 0)
    .sort((a, b) => a.finished - b.finished).map(run => ({created: run.finished, value: run.resources.wall_seconds,
      state: run.state, hypothesis: run.hypothesis_id || null, unit: '초',
      ref: reference(workspace, run.registration_id || '', 'run.resources.wall_seconds', {run: run.id})}));
  const observations = list(resources.observations || raw.resource_observations)
    .map(item => ({...(item.record || item), id: item.id, created: item.created,
      registration_id: item.registration_id, run_id: item.run_id}));
  const costTrend = observations.filter(item => item.cost?.status === 'known' && finite(item.cost.amount) && item.cost.amount >= 0 &&
    typeof item.cost.currency === 'string' && finite(item.created)).map(item => ({created: item.created,
      value: item.cost.amount, unit: item.cost.currency, source: '외부 보고 · 검증 판정 아님',
      ref: reference(workspace, item.registration_id || '', 'resource.cost', {observation: item.id, run: item.run_id || ''})}));
  refs.push(...runTrend.map(item => item.ref), ...costTrend.map(item => item.ref));
  return {state, stateLabel: labelState(state, 'goal'), stateSource: goal.state_source || 'legacy_mapping',
    goalVersion: goal.version ?? null, terminal, reason: clipText(lifecycle.reason || (terminal ? '종료·중단 사유 미기록' : ''), 240),
    results: list(lifecycle.results).map(value => clipText(value, 220)), incomplete: list(lifecycle.incomplete).map(value => clipText(value, 220)),
    lifecycleReported: Boolean(lifecycle.id), elapsedSeconds: elapsed, elapsedScope: '목표 기록부터 현재 보고 상태 시각까지 · 과거 대기·중단 시간 포함',
    cost: {items: cost, known, unknown, complete: false,
      text: cost.length ? cost.map(item => item.label).join(' · ') : '비용 미확인',
      scope: '기록된 외부 비용 관측만 집계 · 미기록 사용량 포함 전체 비용은 미확인',
      provenance: 'external_report', rawScope: resources.scope || 'recorded_external_observations_only'},
    runTime: {value: finite(wall.value) && wall.value >= 0 ? wall.value : null,
      known: wall.known ?? 0, unknown: wall.unknown ?? null,
      scope: raw.scope?.kind === 'selected_goal_all_runs' ? '선택 목표의 전체 고유 실행' : '집계 범위 미확인'},
    scope: {...raw.scope, goal_id: goal.id || null, goal_version: goal.version ?? null},
    tokens: {observedSubtotal: finite(resources.tokens?.observed_subtotal) ? resources.tokens.observed_subtotal : null,
      known: resources.tokens?.known_count ?? 0, unknown: resources.tokens?.unknown_count ?? null,
      scope: '명시된 외부 보고의 토큰 관측 소계 · 미기록 전체 사용량은 미확인'},
    constraints: constraintDetails.map(item => clipText(`${item.label}: ${item.status === 'unknown' ? '미확인' : asText(item.value)}`, 180)),
    constraintDetails, constraintsStatus: constraintDetails.length ? constraintDetails.every(item => item.status === 'unknown') ? 'unknown'
      : constraintDetails.some(item => item.status === 'unknown') ? 'partially_unknown' : 'recorded' : 'unrecorded',
    trends: {runs: runTrend, costs: costTrend, runsTotal: raw.scope?.runs_total ?? null,
      recordsTotal: raw.records_total ?? null, observationsTotal: raw.resource_observations_total ?? resources.observation_total ?? null},
    branches: list(raw.branches).map(branch => JSON.parse(JSON.stringify(branch))), refs};
}

function flowModel(record, goal, hypothesis, states, trust, summary, workspace) {
  const reg = record?.registration, evidence = list(record?.evidence), support = supportFor(record);
  const artifactEvidence = evidence.filter(item => item.run_id === record?.run?.id && item.kind === 'measured' &&
    list(reg?.spec?.artifacts).some(artifact => artifact.name === item.name));
  const evidenceState = evidence.some(item => item.integrity === 'tampered') ? 'tampered'
    : evidence.some(item => item.integrity === 'missing') ? 'missing' : artifactEvidence.length ? 'measured' : 'pending';
  const nodes = [
    {key: 'hypothesis', title: '가설', text: clipText(hypothesis.statement || '가설 미기록', 100),
      state: hypothesis.id ? 'proposed' : 'pending', refs: [reference(workspace, reg?.id, 'hypothesis.statement', {hypothesis: hypothesis.id || ''})]},
    {key: 'experiment', title: '실험', text: clipText(reg?.spec?.change || '사전등록된 실험 없음', 100),
      state: states.execution, refs: [reference(workspace, reg?.id, 'registration.spec.change'), reference(workspace, reg?.id, 'run.state', {run: record?.run?.id || ''})]},
    {key: 'evidence', title: '증거', text: artifactEvidence.length ? `실측 산출물 ${artifactEvidence.length}개 · 현재 원본 ${trust.invalidCount ? '확인 필요' : '보존 상태 확인'}` : '연결된 실측 산출물 없음',
      state: evidenceState,
      refs: artifactEvidence.length ? artifactEvidence.map(item => reference(workspace, reg?.id, 'evidence', {evidence: item.id, run: item.run_id}))
        : [reference(workspace, reg?.id, 'evidence')]},
    {key: 'verification', title: '검증', text: reg?.spec?.criteria?.length ? `고정 기준 ${reg.spec.criteria.length}개 · ${support.measured ? '산출물 실제 검사' : '현재 판정 근거 미확인'}` : '검사 기준 미등록',
      state: states.verification, historical: !trust.supported && states.verification === 'passed',
      refs: [reference(workspace, reg?.id, 'verification', {run: record?.verification?.run_id || ''})]},
    {key: 'conclusion', title: '결론', text: clipText(record?.decision?.reason || '가설 결정 이유 미기록', 110),
      state: states.decision, historical: !trust.supported && states.decision === 'adopted',
      refs: [reference(workspace, reg?.id, 'decision.reason')]}
  ];
  const labels = ['사전등록해 시험', '실행 원본 연결', '고정 기준으로 검사', '판정을 참고해 결정'];
  const fields = ['registration.hypothesis_id', 'evidence.run_id', 'verification.run_id', 'decision.registration_id'];
  return {nodes, edges: labels.map((label, index) => ({from: nodes[index].key, to: nodes[index + 1].key, label,
    recorded: index === 0 ? Boolean(reg?.hypothesis_id === hypothesis.id && hypothesis.id) : index === 1 ? Boolean(artifactEvidence.length)
      : index === 2 ? Boolean(record?.verification?.run_id && record.verification.run_id === record?.run?.id) : Boolean(record?.decision?.registration_id === reg?.id && reg?.id),
    ref: reference(workspace, reg?.id, fields[index], {goal: goal.id || '', run: record?.run?.id || ''})})),
    activePath: reg?.id || null, scope: '에이전트가 선택한 실제 가설·실험 경로 · 전체 연구 완료와 별개',
    missing: list(summary?.missing_evidence).map(value => MISSING_LABELS[value] || clipText(value, 120))};
}

/** Only persisted foreign keys make edges. Opposing criteria are not global hypothesis refutations. */
function relationshipModel(input, goal, selected, workspace, total) {
  const seen = new Set(), records = list(input).map(unwrap).filter(record => record?.registration?.id && !seen.has(record.registration.id) && seen.add(record.registration.id));
  const nodes = [], edges = [], conclusions = [], gaps = [], refs = [];
  for (const record of records.slice(0, 6)) {
    const ws = record.workspace || workspace, id = record.registration.id, hyp = record.hypothesis || {}, states = statesFor(record),
      trust = trustModel(record, ws, states), path = flowModel(record, {...goal, id: record.registration.goal_id}, hyp, states, trust, {}, ws);
    for (const node of path.nodes) nodes.push({...node, key: `${id}:${node.key}`, branch: id, selected: id === selected});
    for (const edge of path.edges) edges.push({...edge, from: `${id}:${edge.from}`, to: `${id}:${edge.to}`, branch: id, selected: id === selected});
    const metrics = metricModels(record, ws), support = metrics.filter(metric => metric.supported && metric.criteria.length > 0 && metric.criteria.every(criterion => criterion.passed));
    const unmet = metrics.flatMap(metric => metric.criteria.filter(criterion => criterion.passed === false).map(criterion => ({metric: metric.name,
      actual: metric.value, unit: metric.unit, op: criterion.op, threshold: criterion.threshold, ref: criterion.ref})));
    const missing = [];
    if (!record.run) missing.push('실행 결과 증거 없음');
    if (!record.verification) missing.push('독립 검증 없음');
    if (!record.decision) missing.push('결정 이유 없음');
    if (trust.invalidCount) missing.push('현재 원본 누락·변조');
    if (states.execution === 'unknown') missing.push('원 실행의 종료 여부 미확정');
    if (states.execution === 'failed') missing.push('실행 실패는 가설 반박을 뜻하지 않음');
    const conclusion = {registration: id, hypothesis: hyp.id || null, state: states.decision,
      reason: clipText(record.decision?.reason || '결정 미기록', 260), scope: conditions(record.registration.spec, ws, id),
      support: support.map(metric => ({metric: metric.name, actual: metric.value, unit: metric.unit, criteria: metric.criteria, ref: metric.ref})),
      opposingRegisteredCriteria: unmet, gaps: missing, currentClaimSupported: trust.supported,
      evidenceKinds: ['measured', 'literature', 'inference', 'proposal'].map(kind => ({kind, label: labelState(kind),
        count: list(record.evidence).filter(item => item.kind === kind).length,
        refs: list(record.evidence).filter(item => item.kind === kind).map(item => reference(ws, id, 'evidence.kind', {evidence: item.id, run: item.run_id || ''}))})),
      independence: 'not_established', ref: reference(ws, id, 'decision')};
    conclusions.push(conclusion);
    gaps.push(...missing.map(text => ({text, ref: reference(ws, id, 'registration')})));
    refs.push(...path.nodes.flatMap(node => node.refs), ...path.edges.map(edge => edge.ref), conclusion.ref,
      ...conclusion.evidenceKinds.flatMap(item => item.refs));
  }
  const branches = records.slice(0, 6).map(record => ({registration: record.registration.id, hypothesis: record.hypothesis?.id || null,
    title: clipText(record.hypothesis?.statement || record.registration.spec?.change || '등록된 시도', 110),
    selected: record.registration.id === selected, states: statesFor(record)}));
  return {nodes, edges, branches, conclusions, gaps, refs, shown: branches.length,
    total: Number.isInteger(total) ? total : records.length, scope: '조회한 원본 관계만 표시 · 과학적 인과관계·독립성 추정 없음'};
}

/** Descriptive variation across same-treatment original runs, not a confidence interval or an independence claim. */
export function repeatModels(input = []) {
  const groups = new Map(), seenRuns = new Set();
  for (const record of list(input).map(unwrap)) {
    if (!record?.registration || !record.run?.id || seenRuns.has(record.run.id)) continue;
    seenRuns.add(record.run.id);
    const missing = incompleteConditions(record), metrics = stampRecordReferences(metricModels(record, record.workspace || ''), record);
    if (missing.length) continue;
    if (typeof record.registration.spec.conditions?.repeat_design !== 'string' || !record.registration.spec.conditions.repeat_design.trim()) continue;
    const condition = comparisonConditions(record);
    delete condition.seed;
    const signature = stable({...condition, source_version: record.registration.spec.source_version,
      change: record.registration.spec.change});
    if (!groups.has(signature)) groups.set(signature, []);
    groups.get(signature).push({record, metrics});
  }
  return [...groups.values()].map((group, index) => {
    const first = group[0].record, names = list(first.registration.spec.metrics), refs = [];
    const metrics = names.map(name => {
      const samples = group.flatMap(({record, metrics}) => {
        const metric = metrics.find(item => item.name === name);
        if (!metric?.supported || !finite(metric.value)) return [];
        refs.push(metric.ref);
        return [{value: metric.value, seed: record.registration.spec.seed, run: record.run.id,
          registration: record.registration.id, ref: metric.ref}];
      });
      const n = samples.length, values = samples.map(sample => sample.value), scale = n ? Math.max(...values.map(value => Math.abs(value)), 1) : 1;
      const normalizedMean = n ? values.reduce((sum, value) => sum + value / scale, 0) / n : null;
      const mean = n ? normalizedMean * scale : null;
      const observedSd = n >= 2 ? Math.sqrt(values.reduce((sum, value) => sum + (value / scale - normalizedMean) ** 2, 0) / (n - 1)) * scale : null;
      const sd = finite(observedSd) ? observedSd : null;
      return {name, unit: unitFor(first.registration.spec, name), samples, n, mean,
        min: n ? Math.min(...values) : null, max: n ? Math.max(...values) : null, sampleSd: sd,
        calculation: 'mean=sum(x)/n; sampleSd=sqrt(sum((x-mean)^2)/(n-1))',
        uncertainty: n < 2 ? '반복 측정 부족 · 변동 미확인' : sd === null ? '숫자 범위를 초과한 변동 · 신뢰구간·독립성 미확인'
          : '조회된 반복의 기술 통계 · 신뢰구간·모집단 일반화·독립성 미확인'};
    });
    return {key: `repeat-${index + 1}`, title: clipText(first.registration.spec.change, 140), metrics,
      conditions: stampRecordReferences(conditions(first.registration.spec, first.workspace || '', first.registration.id)
        .filter(item => item.label !== 'Seed'), first),
      seeds: [...new Set(group.map(({record}) => record.registration.spec.seed))],
      runs: group.length, independence: 'not_established', refs,
      scope: '같은 목표·등록 평가 조건·변경점·소스의 고유 실행; seed 차이는 반복 조건으로 명시'};
  });
}

function comparisonConditions(record) {
  const spec = record?.registration?.spec || {};
  return {goal: record?.registration?.goal_id, goal_version: record?.registration?.goal_version,
    comparison: spec.comparison, data_split: spec.data_split, seed: spec.seed,
    metrics: list(spec.metrics).map((name) => ({name, unit: unitFor(spec, name)})).sort((a, b) => String(a.name).localeCompare(String(b.name))),
    criteria: list(spec.criteria).map((criterion) => ({metric: criterion.metric, op: criterion.op, threshold: criterion.threshold}))
      .sort((a, b) => stable(a).localeCompare(stable(b))),
    conditions: spec.conditions || {}, validator_sha256: spec.validator_sha256};
}

function incompleteConditions(record) {
  const spec = record?.registration?.spec || {}, missing = [];
  if (!record?.registration?.goal_id) missing.push('연구 목표 연결');
  if (typeof spec.comparison !== 'string' || !spec.comparison.trim()) missing.push('비교 기준');
  if (!((typeof spec.data_split === 'string' && spec.data_split.trim()) || (isObject(spec.data_split) && Object.keys(spec.data_split).length))) missing.push('데이터 분할');
  if (!Number.isInteger(spec.seed)) missing.push('seed');
  if (!list(spec.metrics).length || list(spec.metrics).some((item) => typeof item !== 'string' || !item)) missing.push('등록 지표');
  if (!list(spec.criteria).length || list(spec.criteria).some((criterion) => !finite(criterion.threshold) || !OPS[criterion.op] || !list(spec.metrics).includes(criterion.metric))) missing.push('등록 기준');
  if (spec.conditions !== undefined && !isObject(spec.conditions)) missing.push('실행 조건');
  if (typeof spec.validator_sha256 !== 'string' || !/^[a-f\d]{64}$/i.test(spec.validator_sha256)) missing.push('고정 검증기');
  if (!spec.source_version?.label || !isObject(spec.source_version?.files) || !Object.keys(spec.source_version.files).length) missing.push('소스 버전');
  return missing;
}

/** Cohorts are registration-compatible candidates, never a performance ranking. */
export function compareRecords(records = []) {
  const loaded = list(records).map(unwrap).filter((record) => record?.registration), seen = new Set();
  // Restoring an export retains registration IDs; copies are not additional experimental attempts.
  const originals = loaded.filter((record) => {
    if (!record.registration.id || seen.has(record.registration.id)) return false;
    seen.add(record.registration.id); return true;
  });
  const duplicates = loaded.length - originals.length, groups = new Map();
  const allConditions = originals.map(comparisonConditions), differenceLabels = {goal: '연구 목표', goal_version: '등록 당시 목표 버전', comparison: '비교 기준', data_split: '데이터 분할',
    seed: 'seed', metrics: '지표·단위', criteria: '등록 기준', conditions: '실행 조건', validator_sha256: '고정 검증기'};
  const differing = Object.keys(differenceLabels).filter((key) => new Set(allConditions.map((item) => stable(item[key]))).size > 1);
  originals.forEach((record, index) => {
    const missing = incompleteConditions(record), signature = missing.length ? `incomplete:${index}` : stable(allConditions[index]);
    if (!groups.has(signature)) groups.set(signature, {records: [], missing, condition: allConditions[index]});
    groups.get(signature).records.push(record);
  });
  return [...groups.values()].map((group, index) => {
    const comparable = group.records.length >= 2 && !group.missing.length;
    const changes = [...new Set(group.records.map((record) => clipText(record.registration.spec.change, 140)))];
    const versions = [...new Set(group.records.map((record) => clipText(record.registration.spec.source_version?.label, 100)))];
    const sourceFiles = new Set(group.records.map((record) => stable(record.registration.spec.source_version?.files)));
    const differences = differing.length ? [`다른 묶음과 조건 차이: ${differing.map((key) => differenceLabels[key]).join(' · ')}`] : [];
    if (duplicates) differences.push(`같은 등록의 반복 조회 ${duplicates}건은 별도 실험으로 세지 않습니다.`);
    if (versions.length > 1) differences.push(`소스 버전 차이: ${versions.join(' · ')}`);
    if (sourceFiles.size > 1) differences.push('사전 고정된 소스 파일 내용이 서로 다릅니다. 버전 이름만으로 동일성을 판단하지 않습니다.');
    if (changes.length > 1) differences.push(`시험한 변경점: ${changes.join(' · ')}`);
    const reason = group.missing.length ? `비교 조건 미확인: ${group.missing.join(' · ')}`
      : comparable ? `등록에 적힌 비교 조건이 같은 ${group.records.length}건입니다. 미등록 조건의 동일성은 확인되지 않았습니다.`
        : '같은 등록 조건의 두 번째 시도가 없어 수치 비교를 구성할 수 없습니다.';
    return {key: `cohort-${index + 1}`, comparable, reason, conditions: stampRecordReferences(conditions(group.records[0].registration.spec,
      group.records[0].workspace || '', group.records[0].registration.id), group.records[0]), differences,
      items: group.records.map((record) => stampRecordReferences({title: clipText(record.registration.spec.change || record.hypothesis?.statement || '등록된 시도', 150),
        registration: record.registration.id, source: clipText(record.registration.spec.source_version?.label || '소스 버전 미확인', 120),
        states: statesFor(record), metrics: metricModels(record),
        refs: [reference(record.workspace || '', record.registration.id, 'registration.spec'),
          reference(record.workspace || '', record.registration.id, 'verification', {run: record.verification?.run_id || ''})]}, record))};
  });
}

/**
 * Read-only briefing for the person who commissioned the research.
 * It compresses existing verified facts; it does not interpret an agent's closure report as a result,
 * choose a scientific hypothesis, supply missing units, or mutate the full presentation model.
 */
export function buildClientView(vm = {}, {goal} = {}) {
  const copy = value => JSON.parse(JSON.stringify(value ?? null));
  const refsFor = (...groups) => {
    const unique = new Map();
    for (const ref of groups.flatMap(group => list(group))) {
      if (isObject(ref) && typeof ref.field === 'string') unique.set(stable(ref), copy(ref));
    }
    return [...unique.values()];
  };
  const view = vm.observatory || {}, sourceVersion = copy(vm.sourceVersion || {}), states = vm.states || {},
    report = vm.report || {}, trust = vm.trust || {}, uncertainty = list(view.uncertainty);
  const currentGoal = unwrap(goal)?.goal || unwrap(goal);
  const matchingGoal = isObject(currentGoal) && currentGoal.id && currentGoal.id === sourceVersion.goal &&
    (currentGoal.version ?? null) === (sourceVersion.goal_version ?? null);
  const request = matchingGoal && typeof currentGoal.brief?.original_request === 'string'
    ? currentGoal.brief.original_request.trim() : '';
  const questionRefs = refsFor(list(vm.question?.refs).filter(ref => ref.field === 'goal.title'));
  const question = {title: clipText(request || vm.question?.title || '의뢰 내용이 아직 기록되지 않았습니다.', 160),
    refs: request ? refsFor(questionRefs.map(ref => ({...ref, field: 'goal.brief.original_request'}))) : questionRefs};
  const stale = list(vm.blockers).filter(item => item.ref?.field === 'snapshot.report.consistent' ||
    item.ref?.field === 'revision' || item.ref?.field === 'memory.revision');
  const scopeChanged = sourceVersion.registration_goal_version !== null && sourceVersion.registration_goal_version !== undefined &&
    sourceVersion.goal_version !== null && sourceVersion.goal_version !== undefined &&
    sourceVersion.registration_goal_version !== sourceVersion.goal_version;
  const failedMetric = list(vm.metrics).find(metric => metric.supported &&
    list(metric.criteria).some(criterion => criterion.passed === false));
  let sourceMetric = view.metric;
  // A fulfilled diagnostic metric must not conceal another unmet registered criterion.
  if (failedMetric && !list(sourceMetric?.criteria).some(criterion => criterion.passed === false)) {
    sourceMetric = {name: failedMetric.name,
      label: failedMetric.label && failedMetric.label !== failedMetric.name
        ? failedMetric.label : displayMetricLabel(failedMetric.name),
      labelSource: failedMetric.label !== failedMetric.name ? 'registration_metadata' : 'display_name',
      value: failedMetric.value, unit: failedMetric.unit, unitKnown: failedMetric.unit !== '단위 미등록',
      status: 'measured', criteria: list(failedMetric.criteria), domain: failedMetric.domain,
      refs: refsFor([failedMetric.ref], list(failedMetric.criteria).map(item => item.ref))};
  }
  const invalid = trust.invalidCount > 0 || sourceMetric?.status === 'invalid';
  const historical = sourceMetric?.status === 'historical' ||
    (!trust.supported && (states.verification === 'passed' || states.decision === 'adopted'));
  const hasRegistration = Boolean(sourceVersion.registration_fingerprint ||
    list(view.attempts?.items).some(item => item.selected));
  let resultStatus = 'empty', headline = '아직 연구 결과가 없습니다.', tone = 'quiet';
  if (invalid) {resultStatus = 'invalid'; headline = '현재 근거를 확인할 수 없습니다.'; tone = 'warn';}
  else if (stale.length) {resultStatus = 'stale'; headline = '최신 기록을 확인해야 합니다.'; tone = 'warn';}
  else if (states.execution === 'unknown') {resultStatus = 'execution_unknown'; headline = '실행 여부부터 확인해야 합니다.'; tone = 'warn';}
  else if (states.execution === 'running') {resultStatus = 'running'; headline = '아직 결과를 확인하는 중입니다.';}
  else if (states.execution === 'failed') {resultStatus = 'execution_failed'; headline = '실행이 실패해 답을 얻지 못했습니다.'; tone = 'bad';}
  else if (states.execution === 'cancelled') {resultStatus = 'execution_cancelled'; headline = '실행이 취소되어 답을 얻지 못했습니다.';}
  else if (failedMetric) {resultStatus = 'criterion_unmet'; headline = `${sourceMetric.label} 기준에 미치지 못했습니다.`; tone = 'bad';}
  else if (trust.supported === true) {resultStatus = 'criteria_met'; headline = '등록 기준을 충족했습니다.'; tone = 'good';}
  else if (states.verification === 'inconclusive') {resultStatus = 'inconclusive'; headline = '아직 답을 확정할 수 없습니다.';}
  else if (states.verification === 'failed') {resultStatus = 'unconfirmed'; headline = '검증 기록을 다시 확인해야 합니다.'; tone = 'warn';}
  else if (historical) {resultStatus = 'historical'; headline = '이전 결과를 현재 확인할 수 없습니다.'; tone = 'warn';}
  else if (states.execution === 'succeeded') {resultStatus = 'awaiting_verification'; headline = '독립 검증이 필요합니다.';}
  else if (hasRegistration) {resultStatus = 'awaiting_result'; headline = '실행 결과가 아직 확인되지 않았습니다.';}
  const current = ['criterion_unmet', 'criteria_met'].includes(resultStatus);
  const metric = sourceMetric ? {...copy(sourceMetric),
    value: current && sourceMetric.status === 'measured' ? sourceMetric.value : null,
    status: current && sourceMetric.status === 'measured' ? 'measured'
      : invalid ? 'invalid' : stale.length ? 'stale' : historical ? 'historical' : 'unknown',
    criteria: list(sourceMetric.criteria).map(criterion => ({...copy(criterion), passed: current ? criterion.passed : null}))} : null;
  if (metric) metric.valueText = numberText(metric.value);
  const operatorText = {'>=': '이상', '>': '초과', '<=': '이하', '<': '미만', '==': '같음', '!=': '아님'};
  const displayUnit = metric?.unitKnown && metric.unit !== '무차원' ? ` ${metric.unit}` : '';
  const criterion = list(metric?.criteria).find(item => item.passed === false) || list(metric?.criteria)[0];
  const metricDetail = metric && finite(metric.value)
    ? `${metric.label} ${numberText(metric.value)}${displayUnit}${criterion && finite(criterion.threshold)
      ? ` · 기준 ${numberText(criterion.threshold)}${displayUnit} ${operatorText[criterion.op] || criterion.op}` : ''}` : '';
  const details = {invalid: '원본의 누락 또는 변조가 감지됐습니다.', stale: '서로 다른 조회 시점의 기록이 섞여 있습니다.',
    execution_unknown: '원래 실행의 종료 증거가 필요합니다.', running: '실행 결과가 아직 도착하지 않았습니다.',
    execution_failed: '실행 실패만으로 가설이 틀렸다고 판단할 수는 없습니다.',
    execution_cancelled: '취소된 실행에는 확정할 결과가 없습니다.',
    historical: '과거 판정에 연결된 현재 근거가 충분하지 않습니다.',
    inconclusive: '검증이 미결이라 추가 근거가 필요합니다.', unconfirmed: '판정과 원본의 연결을 확인해야 합니다.',
    awaiting_verification: '실행 완료만으로 결과가 검증된 것은 아닙니다.',
    awaiting_result: '등록 조건에 따른 실행 결과를 기다립니다.', empty: '의뢰와 실험이 기록되면 확인된 답을 보여 드립니다.'};
  const answer = {headline, detail: clipText(metricDetail || details[resultStatus], 160), status: resultStatus, tone,
    metric, refs: refsFor(sourceMetric?.refs, trust.refs,
      stale.map(item => item.ref), view.focus?.experiment?.refs, view.focus?.verification?.refs)};
  const confirmedOtherMetric = current && resultStatus === 'criterion_unmet'
    ? list(vm.metrics).find(item => item.name !== metric?.name && item.supported && finite(item.value) &&
      list(item.criteria).length > 0 && list(item.criteria).every(criterion => criterion.passed === true)) : null;
  const otherLabel = confirmedOtherMetric ? confirmedOtherMetric.label && confirmedOtherMetric.label !== confirmedOtherMetric.name
    ? confirmedOtherMetric.label : displayMetricLabel(confirmedOtherMetric.name) : '';
  const otherMetricRefs = confirmedOtherMetric
    ? refsFor([confirmedOtherMetric.ref], confirmedOtherMetric.criteria.map(item => item.ref)) : [];
  const unconfirmedScope = {
    empty: '확인할 실행 결과가 아직 없습니다.', awaiting_result: '확인할 실행 결과가 아직 없습니다.',
    running: '확인할 실행 결과가 아직 없습니다.',
    awaiting_verification: '등록 기준에 연결된 독립 검증이 아직 없습니다.',
    execution_failed: '실행 실패가 기록되어 결과를 확인할 수 없습니다.',
    execution_unknown: '원래 실행이 끝났는지 확인되지 않았습니다.',
    execution_cancelled: '실행 취소가 기록되어 결과가 없습니다.',
    inconclusive: '독립 검증이 미결로 기록되어 있습니다.',
    unconfirmed: '검증 기록과 원본의 연결이 확인되지 않았습니다.',
    stale: '같은 조회 시점의 기록이 아니어서 결과를 확정할 수 없습니다.',
    historical: '과거 판정만 있고 현재 근거는 확인되지 않았습니다.',
    invalid: '이전 검증·채택 기록은 현재 확인된 결과가 아닙니다.'};
  const assurance = {label: current ? scopeChanged ? '등록 당시 조건에서 확인됨'
    : resultStatus === 'criterion_unmet' ? '기준 미달을 확인함' : '등록 조건에서 확인됨'
    : invalid ? '현재 근거 확인 필요' : historical ? '과거 판정만 남아 있음' : '확인되지 않음',
    detail: current ? confirmedOtherMetric ? `${clipText(otherLabel, 60)}${/[가-힣]$/u.test(otherLabel) && (otherLabel.charCodeAt(otherLabel.length - 1) - 0xac00) % 28 ? '은' : '는'} 등록 기준을 충족했습니다. 결과는 실험 당시 조건에 한정됩니다.`
      : '실험 당시 등록한 데이터와 조건에 한정한 결과입니다.'
      : unconfirmedScope[resultStatus],
    status: current ? 'confirmed_in_registered_scope' : 'unconfirmed', tone: current ? 'quiet' : invalid || historical || stale.length ? 'warn' : 'quiet',
    refs: refsFor(trust.refs, view.focus?.verification?.refs, view.focus?.conclusion?.refs, otherMetricRefs)};
  const requiredEvidence = [];
  const require = (text, kind, refs) => requiredEvidence.push({text, kind, refs: refsFor(refs)});
  if (invalid) require('누락·변조된 원본의 복원 또는 대조', 'integrity', trust.refs);
  else if (stale.length) require('같은 조회 시점의 최신 기록', 'snapshot', stale.map(item => item.ref));
  else if (states.execution === 'unknown') require('원래 실행이 끝났는지 확인할 증거', 'execution_receipt', view.focus?.experiment?.refs);
  else if (states.execution === 'failed') require('실행 실패 원인과 복구 기록', 'execution_failure', view.focus?.experiment?.refs);
  else if (['awaiting_verification', 'inconclusive', 'unconfirmed', 'historical'].includes(resultStatus))
    require('등록 기준에 연결된 독립 검증 근거', 'verification', view.focus?.verification?.refs);
  else if (['running', 'awaiting_result'].includes(resultStatus)) require('등록 조건에 따른 실행 결과', 'execution_receipt', view.focus?.experiment?.refs);
  const progressLabels = {completed: '진행 종료로 보고됨', paused: '진행 일시중단으로 보고됨',
    cancelled: '의뢰 취소로 보고됨', active: '의뢰 진행 중'};
  const reported = report.lifecycleReported === true;
  const progressKnown = report.state === 'active' || reported;
  const nextKind = requiredEvidence[0]?.kind || (scopeChanged ? 'goal_version' : null);
  const followup = {label: progressKnown ? progressLabels[report.state] || '전체 진행 상황 미확인' : '전체 진행 상황 미확인',
    text: requiredEvidence[0]?.text || (scopeChanged ? '현재 의뢰에 적용할 수 있는지 대조가 필요합니다.'
      : current ? '이 결과를 다른 조건에 적용하려면 추가 확인이 필요합니다.' : '아직 전체 의뢰의 진행 보고가 없습니다.'),
    nextKind, requiredEvidence, terminal: report.terminal === true, reported,
    refs: refsFor(report.refs, requiredEvidence[0]?.refs,
      scopeChanged ? uncertainty.filter(item => item.kind === 'registration.goal_version').flatMap(item => item.refs) : [],
      current ? vm.conditions?.map(item => item.ref) : [])};
  const items = [], addLimit = (text, kind, refs) => {
    if (!items.some(item => item.kind === kind)) items.push({text, kind, refs: refsFor(refs)});
  };
  if (scopeChanged) addLimit('실험 당시 의뢰와 현재 의뢰의 적용 범위를 대조해야 합니다.', 'goal_version',
    uncertainty.filter(item => item.kind === 'registration.goal_version').flatMap(item => item.refs));
  if (metric && !metric.unitKnown) addLimit('지표의 단위가 등록되지 않았습니다.', 'metric_unit',
    uncertainty.filter(item => item.kind === 'metric_unit').flatMap(item => item.refs));
  if (states.execution === 'failed') addLimit('실행 실패는 가설 반박을 뜻하지 않습니다.', 'execution_failure', view.focus?.experiment?.refs);
  if (uncertainty.some(item => item.kind === 'independence')) addLimit('반복 시도의 독립성·일반화는 확인되지 않았습니다.', 'independence',
    uncertainty.filter(item => item.kind === 'independence').flatMap(item => item.refs));
  const limitations = {scope: hasRegistration ? '현재 선택한 시도의 등록 조건에 한정한 결과입니다.'
    : '아직 결과의 적용 범위를 확인할 수 없습니다.', items,
    refs: refsFor(vm.conditions?.map(item => item.ref), ...items.map(item => item.refs))};
  return {question, answer, assurance, followup, limitations, sourceVersion,
    refs: refsFor(question.refs, answer.refs, assurance.refs, followup.refs, limitations.refs,
      ...requiredEvidence.map(item => item.refs))};
}

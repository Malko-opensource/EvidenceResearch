"""Optional Laya input/result exchange. Inference belongs to the external agent."""
import hashlib
import json

from .core import ResearchError, canonical


SCHEMA = 'research-laya-choice-v1'
QUESTION = 'research_choice'


def _digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def _text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ResearchError('INVALID_INPUT', 'Expected nonempty text: ' + field)


def example(goal_id='REPLACE_WITH_GOAL_ID'):
    return {'goal_id': goal_id, 'context': 'Describe the task and resource conditions.',
            'question': 'Which proposal should the external agent investigate next?',
            'candidates': [
                {'id': 'candidate-a', 'hypothesis': 'Describe hypothesis A',
                 'applicability': 'Describe when A applies', 'conditions': {'seed': 7}, 'evidence': []},
                {'id': 'candidate-b', 'hypothesis': 'Describe hypothesis B',
                 'applicability': 'Describe when B applies', 'conditions': {'seed': 7}, 'evidence': []}]}


def _input(value):
    if not isinstance(value, dict):
        raise ResearchError('INVALID_INPUT', 'Laya input must be an object')
    # A finite JSON copy binds all original candidate conditions without retaining caller mutation.
    payload = json.loads(canonical(value))
    if set(payload) - {'goal_id', 'context', 'question', 'candidates'}:
        raise ResearchError('INVALID_INPUT', 'Unknown Laya input fields')
    _text(payload.get('goal_id'), 'goal_id')
    _text(payload.get('question'), 'question')
    if not isinstance(payload.get('context', ''), str):
        raise ResearchError('INVALID_INPUT', 'context must be text')
    candidates = payload.get('candidates')
    if not isinstance(candidates, list) or not candidates:
        raise ResearchError('INVALID_INPUT', 'candidates must be a nonempty list')
    seen = set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ResearchError('INVALID_INPUT', 'Each candidate must be an object')
        if set(candidate) - {'id', 'hypothesis', 'applicability', 'conditions', 'evidence', 'observation'}:
            raise ResearchError('INVALID_INPUT', 'Unknown candidate fields; declarations cannot set verification')
        for name in ('id', 'hypothesis', 'applicability'):
            _text(candidate.get(name), 'candidate.' + name)
        if candidate['id'] in seen:
            raise ResearchError('INVALID_INPUT', 'Duplicate candidate ID', {'id': candidate['id']})
        seen.add(candidate['id'])
        if not isinstance(candidate.get('conditions'), dict):
            raise ResearchError('INVALID_INPUT', 'Candidate conditions must be an object')
        references = candidate.get('evidence', [])
        if not isinstance(references, list):
            raise ResearchError('INVALID_INPUT', 'Candidate evidence must be a list of registration IDs')
        for reference in references:
            _text(reference, 'candidate.evidence registration ID')
        if len(set(references)) != len(references):
            raise ResearchError('INVALID_INPUT', 'Duplicate evidence registration ID')
        if not isinstance(candidate.get('observation', ''), str):
            raise ResearchError('INVALID_INPUT', 'Candidate observation must be declared text')
    return payload


def _snapshot(store, payload):
    def read(connection):
        goal = dict(store._required(connection, 'goals', payload['goal_id']))
        revision = int(connection.execute("SELECT value FROM meta WHERE key='revision'").fetchone()[0])
        memory = {}
        for candidate in payload['candidates']:
            for reference in candidate.get('evidence', []):
                if reference in memory:
                    continue
                record = store._show(connection, reference)
                if record['registration']['id'] != reference:
                    raise ResearchError('INVALID_INPUT', 'Evidence references must be registration IDs')
                run, verification = record['run'], record['verification']
                run_evidence = [item for item in record['evidence'] if run and item['run_id'] == run['id']]
                memory[reference] = {
                    'registration_id': reference, 'hypothesis': record['hypothesis']['statement'],
                    'conditions': record['registration']['spec'],
                    'execution': run['state'] if run else 'registered',
                    'verification': verification['state'] if verification else 'pending',
                    'decision': record['decision']['state'],
                    'metrics': verification['metrics'] if verification else {},
                    'claim_verified': bool(verification and verification['state'] == 'passed'
                                           and all(item['integrity'] == 'valid' for item in run_evidence)),
                    'evidence': [{name: item[name] for name in
                                  ('id', 'name', 'kind', 'claim', 'sha256', 'integrity', 'verified')}
                                 for item in record['evidence']]}
        return revision, {'goal': goal, 'memory': memory}
    return store._read(read)


def prepare(store, value):
    """Return a complete, unranked SDK request and a bound host receipt; read only."""
    payload = _input(value)
    revision, snapshot = _snapshot(store, payload)
    labels, criteria = {}, {}
    for index, candidate in enumerate(payload['candidates'], 1):
        label = 'C' + str(index)
        labels[label] = candidate['id']
        references = candidate.get('evidence', [])
        statuses = [snapshot['memory'][ref]['verification'] + '/current-claim-verified='
                    + str(snapshot['memory'][ref]['claim_verified']).lower() for ref in references]
        description = 'H: ' + candidate['hypothesis'] + '; IF: ' + candidate['applicability']
        description += '; V: unexecuted proposal; referenced checks: ' + (', '.join(statuses) or 'none')
        criteria[label] = description
    labels['abstain'] = None
    criteria['abstain'] = 'Abstain: insufficient evidence or no suitable proposal; ask the external agent to review.'
    state = canonical({'context': payload.get('context', ''), 'candidates_are_unexecuted_proposals': True,
                       'candidates': payload['candidates'],
                       'research_memory': snapshot})
    bundle = {'schema': SCHEMA, 'workspace': str(store.root), 'revision': revision,
              'input': payload, 'snapshot': snapshot, 'labels': labels, 'option_order': list(criteria),
              'request': {'state': state, 'questions': {QUESTION: {
                  'type': 'choice', 'instructions': payload['question'], 'criteria': criteria}}}}
    return bundle | {'sha256': _digest(bundle)}


def resolve(store, bundle, response, expected_sha256):
    """Link an externally supplied prediction to a proposal, never to verified success."""
    if not isinstance(bundle, dict) or not isinstance(expected_sha256, str):
        raise ResearchError('INVALID_INPUT', 'Expected a bundle and independently saved SHA-256')
    if len(expected_sha256) != 64 or any(c not in '0123456789abcdef' for c in expected_sha256):
        raise ResearchError('INVALID_INPUT', 'expected_sha256 must be a lowercase SHA-256')
    body = {name: value for name, value in bundle.items() if name != 'sha256'}
    if bundle.get('sha256') != expected_sha256 or _digest(body) != expected_sha256:
        raise ResearchError('EVIDENCE_TAMPERED', 'Laya bundle does not match the saved digest')
    if bundle.get('schema') != SCHEMA or bundle.get('workspace') != str(store.root):
        raise ResearchError('INVALID_INPUT', 'Laya bundle schema/workspace mismatch')
    current = prepare(store, bundle.get('input'))
    if bundle.get('revision') != current['revision']:
        raise ResearchError('REVISION_CONFLICT', 'Research context changed; prepare a new Laya bundle',
                            {'expected': bundle.get('revision'), 'actual': current['revision'], 'next': 'laya prepare'})
    if current['sha256'] != expected_sha256:
        raise ResearchError('EVIDENCE_TAMPERED', 'Referenced research evidence changed; prepare a new bundle')
    actual_order = list(bundle['request']['questions'][QUESTION]['criteria'])
    if actual_order != bundle['option_order']:
        raise ResearchError('EVIDENCE_TAMPERED', 'Laya option order differs from the bound order')
    if not isinstance(response, dict):
        raise ResearchError('INVALID_INPUT', 'Laya response must be an SDK response object')
    response = json.loads(canonical(response))
    answers = response.get('answers')
    answer = answers.get(QUESTION) if isinstance(answers, dict) else None
    if not isinstance(answer, dict) or 'choice' not in answer:
        raise ResearchError('INVALID_INPUT', 'Missing answers.research_choice.choice')
    choice = answer['choice']
    if choice is not None and (not isinstance(choice, str) or choice not in bundle['labels']):
        raise ResearchError('INVALID_INPUT', 'Unknown Laya choice label', {'choice': choice})
    if 'low_confidence' in answer and not isinstance(answer['low_confidence'], bool):
        raise ResearchError('INVALID_INPUT', 'low_confidence must be boolean')
    abstention = answer.get('abstention')
    if abstention not in (None, 'passed', 'abstained', 'unevaluated'):
        raise ResearchError('INVALID_INPUT', 'Unknown abstention state')
    usage = response.get('usage', {})
    if not isinstance(usage, dict) or not isinstance(usage.get('options', {}), dict):
        raise ResearchError('INVALID_INPUT', 'usage/options must be objects')
    collapsed = usage.get('options', {}).get(QUESTION)
    collision = False
    if collapsed is not None:
        if not isinstance(collapsed, dict) or any(isinstance(collapsed.get(name), bool)
                or not isinstance(collapsed.get(name), int) for name in ('total', 'distinct')):
            raise ResearchError('INVALID_INPUT', 'Option report requires integer total/distinct counts')
        if collapsed['total'] != len(bundle['option_order']) or not 0 <= collapsed['distinct'] <= collapsed['total']:
            raise ResearchError('INVALID_INPUT', 'Option counts do not match the prepared request')
        collision = collapsed['distinct'] < collapsed['total']
    abstained = choice in (None, 'abstain') or answer.get('low_confidence', False) or abstention == 'abstained' or collision
    return {'kind': 'proposal', 'verified': False, 'state': 'abstained' if abstained else 'proposed',
            'candidate_id': None if abstained else bundle['labels'][choice], 'requires_external_review': True,
            'projection_sha256': expected_sha256, 'response_sha256': _digest(response),
            'context_revision': bundle['revision'], 'token_preservation': 'unknown',
            'raw_response': response, 'projection': bundle}

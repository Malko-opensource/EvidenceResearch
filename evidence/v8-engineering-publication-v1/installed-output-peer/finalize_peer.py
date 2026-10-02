"""Seal already completed peer metadata; no package imports or source execution."""
from pathlib import Path
import hashlib
import json
HERE = Path(__file__).resolve().parent
NAMES = (
    'review.py', 'result.json', 'review.stdout.log', 'review.stderr.log',
    'finish_review.py', 'complete-result.json', 'finish.stdout.log', 'finish.stderr.log',
    'report.ko.md', 'commands.json', 'finalize_peer.py',
)
final = json.loads((HERE/'complete-result.json').read_text(encoding='utf-8'))
if final['status'] != 'pass':
    raise ValueError('Only the completed successful output audit can be sealed')
rows = []
for name in NAMES:
    raw = (HERE/name).read_bytes()
    rows.append({'relative':name, 'bytes':len(raw), 'sha256':hashlib.sha256(raw).hexdigest()})
value = {'kind':'version8_installed_output_static_peer_manifest', 'file_count':len(rows),
    'files':rows, 'external_pins':final['external_pins'],
    'role':'Revised external helper author; installed-output/log peer, not independent implementation reviewer.',
    'scope':'New v8 source111/raw recorded own environment proof only; old protected bodies not reopened.',
    'actual_provider_or_research_cpu_or_owner_or_git_actions':0,
    'no_successful_root_phase_repeated':True,
    'initial_failed_peer_preserved':True}
with (HERE/'manifest.json').open('x', encoding='utf-8', newline='\n') as stream:
    json.dump(value, stream, ensure_ascii=False, indent=2); stream.write('\n')
print(json.dumps({'complete_result_sha256':hashlib.sha256((HERE/'complete-result.json').read_bytes()).hexdigest(),
    'manifest_sha256':hashlib.sha256((HERE/'manifest.json').read_bytes()).hexdigest(),
    'report_sha256':hashlib.sha256((HERE/'report.ko.md').read_bytes()).hexdigest(),
    'file_count':len(rows)}))

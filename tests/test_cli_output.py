"""v0.2 presentation regression based on actual external-agent capture errors.

The durable-state contract is covered separately. This single scenario checks
large real verifier details, concise default replies, full retrieval and reuse.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from research_cli.core import Store

ROOT = Path(__file__).resolve().parents[1]
LARGE_DETAIL = "preserved-independent-detail-" * 3000


class CompactCLIOutput(unittest.TestCase):
    def setUp(self):
        self.test_root = ROOT / 'tests' / '.runs'
        self.test_root.mkdir(exist_ok=True)
        self.temporary = Path(tempfile.mkdtemp(prefix='output-', dir=self.test_root)).resolve()
        self.workspace = self.temporary / 'state'
        self.job = self.temporary / 'job'
        self.job.mkdir()
        self.invocations = self.temporary / 'actual-invocations.jsonl'
        source = ("import json\nfrom pathlib import Path\n"
                  f"with Path({str(self.invocations)!r}).open('a',encoding='utf-8') as stream:\n"
                  "    stream.write('{\"invoked\":true}\\n')\n"
                  "Path('invocations.jsonl').write_text('{\"invoked\":true}\\n',encoding='utf-8')\n"
                  "Path('result.json').write_text(json.dumps({'value':3}),encoding='utf-8')\n")
        (self.job / 'task.py').write_text(source, encoding='utf-8')
        self.validator = self.temporary / 'large_validator.py'
        self.validator.write_text(
            "import json,sys\nfrom pathlib import Path\n"
            "bundle=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))\n"
            "result=json.loads(Path(bundle['artifacts']['result.json']).read_text(encoding='utf-8'))\n"
            f"print(json.dumps({{'metrics':{{'pass_rate':float(result['value']==3)}},"
            f"'details':{{'large_detail':{LARGE_DETAIL!r},'basis':'actual_preserved_artifact'}}}}))\n",
            encoding='utf-8')
        initialized = Store.init(self.workspace)
        self.store = Store(self.workspace)
        self.store.validator_register('large-fixed', [sys.executable, str(self.validator), '{bundle}'],
                                      Path(initialized['owner_key_path']).read_text(encoding='utf-8').strip())
        goal = self.store.goal_create('Concise presentation of large verified records')
        hypothesis = self.store.hypothesis_create(goal['id'], 'Local artifact contains the fixed value 3')
        spec = {'hypothesis_id': hypothesis['id'], 'change': 'Write a small actual artifact',
                'comparison': 'Independently fixed value 3', 'data_split': 'Fixed local fixture', 'seed': 0,
                'source_version': {'label': 'output-v1', 'files': {
                    'task.py': hashlib.sha256((self.job / 'task.py').read_bytes()).hexdigest()}},
                'metrics': ['pass_rate'], 'criteria': [{'metric': 'pass_rate', 'op': '>=', 'threshold': 1}],
                'command': [sys.executable, 'task.py'], 'cwd': str(self.job),
                'artifacts': [{'name': name, 'path': name} for name in ('result.json', 'invocations.jsonl')],
                'validator': 'large-fixed'}
        self.registration = self.store.register(goal['id'], spec, 'output-register')['registration']['id']
        self.env = dict(os.environ)
        self.env['PYTHONPATH'] = str(ROOT) + os.pathsep + self.env.get('PYTHONPATH', '')

    def tearDown(self):
        self.assertTrue(self.temporary.is_relative_to(self.test_root.resolve()))
        shutil.rmtree(self.temporary)

    def cli(self, command, *args, small=False):
        completed = subprocess.run([sys.executable, '-m', 'research_cli', '--workspace', str(self.workspace),
                                    command, '--registration', self.registration, *args],
                                   cwd=ROOT, env=self.env, capture_output=True, text=True, encoding='utf-8',
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        if small:
            self.assertLessEqual(len(completed.stdout.encode('utf-8')), 4096,
                                 'Default output must omit raw receipts and large verifier details in this fixture')
        payload = json.loads(completed.stdout)
        self.assertTrue(payload['ok'])
        return payload['data']

    def assert_compact_record(self, data, expected_verification, integrity='valid'):
        record = data['record']
        self.assertEqual(record['run']['state'], 'succeeded')
        if expected_verification is None:
            self.assertIsNone(record['verification'])
        else:
            self.assertEqual(record['verification']['state'], expected_verification)
            self.assertEqual(record['verification']['metrics']['pass_rate'], 1.0)
        self.assertEqual(record['decision']['state'], 'pending')
        observed_integrity = record.get('evidence_integrity', record.get('evidence_summary', {}).get('integrity'))
        self.assertEqual(observed_integrity, integrity)
        retrieval = record.get('detail_retrieval', data.get('detail_retrieval'))
        self.assertIsInstance(retrieval, dict)
        self.assertEqual(retrieval['command'], 'show')
        self.assertEqual(retrieval['registration_id'], self.registration)
        artifacts = record.get('artifacts', data.get('artifacts'))
        self.assertIsInstance(artifacts, list)
        result = next(item for item in artifacts if item['name'] == 'result.json')
        self.assertTrue(Path(result['path']).is_absolute())
        if integrity == 'valid':
            self.assertEqual(hashlib.sha256(Path(result['path']).read_bytes()).hexdigest(), result['sha256'])
            self.assertEqual(result['integrity'], 'valid')
        else:
            self.assertNotEqual(result['integrity'], 'valid')
        return result

    def test_compact_defaults_preserve_detail_retrieval_integrity_and_idempotent_execution(self):
        first = self.cli('run', '--request-key', 'output-run', small=True)
        self.assertTrue(first['started'])
        self.assert_compact_record(first, None)
        verified = self.cli('verify', small=True)
        preserved_result = self.assert_compact_record(verified, 'passed')
        recovered = self.cli('recover', small=True)
        self.assert_compact_record(recovered, 'passed')

        full = self.cli('show')
        self.assertEqual(full['verification']['details']['large_detail'], LARGE_DETAIL)
        self.assertIn('files', full['run']['receipt'])
        full_verified = self.cli('verify', '--full')
        self.assertEqual(full_verified['record']['verification']['details']['large_detail'], LARGE_DETAIL)
        full_recovered = self.cli('recover', '--full')
        self.assertEqual(full_recovered['record']['run']['receipt'], full['run']['receipt'])
        full_repeated = self.cli('run', '--request-key', 'output-run-other-key', '--full')
        self.assertFalse(full_repeated['started'])
        self.assertEqual(full_repeated['record']['run']['receipt'], full['run']['receipt'])
        repeated = self.cli('run', '--request-key', 'output-run', small=True)
        self.assertFalse(repeated['started'])
        self.assert_compact_record(repeated, 'passed')
        self.assertEqual(len(self.invocations.read_text(encoding='utf-8').splitlines()), 1)

        # A historical verifier pass must not conceal the current artifact hash mismatch.
        Path(preserved_result['path']).write_text('{"value":999}', encoding='utf-8')
        current = self.cli('run', '--request-key', 'output-run', small=True)
        self.assertFalse(current['started'])
        self.assert_compact_record(current, 'passed', integrity='invalid')
        self.assertEqual(len(self.invocations.read_text(encoding='utf-8').splitlines()), 1)


if __name__ == '__main__':
    unittest.main()

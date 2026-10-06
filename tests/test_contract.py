"""Model-free public CLI integration and durable-state contract checks."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


class ResearchCLIContract(unittest.TestCase):
    def setUp(self):
        self.test_root = ROOT / "tests" / ".runs"
        self.test_root.mkdir(exist_ok=True)
        self.temporary = Path(tempfile.mkdtemp(prefix="contract-", dir=self.test_root)).resolve()
        self.workspace = self.temporary / "state"
        self.processes = []
        self.env = dict(os.environ)
        self.env["PYTHONPATH"] = str(ROOT) + os.pathsep + self.env.get("PYTHONPATH", "")
        self.initial = self.cli("init")
        self.goal = self.cli("goal", "--title", "계약 연구 contract")['id']
        self.hypothesis = self.cli("hypothesis", "--goal", self.goal,
                                   "--statement", "original wording")['id']
        self.validator = self.temporary / "validator.py"
        self.validator.write_text(
            "import json,sys\nfrom pathlib import Path\n"
            "bundle=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))\n"
            "result=json.loads(Path(bundle['artifacts']['result.json']).read_text(encoding='utf-8'))\n"
            "print(json.dumps({'metrics':{'pass_rate':float(result['value']==3)},"
            "'details':{'basis':'fixed_expected_value_3'}}))\n", encoding="utf-8")
        self.cli("validator", "--name", "fixed", "--input", "-", "--key", self.initial['owner_key_path'],
                 payload=[sys.executable, str(self.validator), "{bundle}"])

    def tearDown(self):
        # Release only this test's own blocked workers before removing its checked directory.
        (self.temporary / "gate").touch()
        for process in self.processes:
            if process.poll() is None:
                process.terminate()
            process.communicate()
        self.assertTrue(self.temporary.is_relative_to(self.test_root.resolve()))
        shutil.rmtree(self.temporary)

    def argv(self, *args, workspace=None):
        return [sys.executable, "-m", "research_cli", "--workspace",
                str(workspace or self.workspace), *map(str, args)]

    def decode(self, completed, error=None):
        try:
            result = json.loads(completed.stdout)
        except (ValueError, TypeError):
            self.fail(f"CLI did not return JSON: {completed.stdout!r}; stderr={completed.stderr!r}")
        if error:
            self.assertNotEqual(completed.returncode, 0)
            self.assertFalse(result['ok'])
            self.assertEqual(result['error']['code'], error, result)
            return result['error']
        self.assertEqual(completed.returncode, 0, result)
        self.assertTrue(result['ok'], result)
        return result['data']

    def cli(self, *args, payload=None, error=None, workspace=None):
        completed = subprocess.run(self.argv(*args, workspace=workspace), cwd=ROOT, env=self.env,
                                   input=json.dumps(payload) if payload is not None else None,
                                   capture_output=True, text=True, encoding="utf-8",
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        return self.decode(completed, error)

    def launch(self, *args):
        process = subprocess.Popen(self.argv(*args), cwd=ROOT, env=self.env,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                   encoding="utf-8", creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.processes.append(process)
        return process

    def wait_for(self, predicate):
        # Test-harness hang detection only; this imposes no research execution limit.
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.02)
        self.fail("Test worker did not reach the expected durable checkpoint")

    def make_spec(self, label="default", value=3, exit_code=0, omit_artifact=False, blocked=False):
        job = self.temporary / ("job-" + label)
        job.mkdir()
        source = "import json,time\nfrom pathlib import Path\n"
        if blocked:
            source += f"gate=Path({str(self.temporary / 'gate')!r})\nwhile not gate.exists():\n    time.sleep(0.02)\n"
        source += f"with Path({str(self.temporary / 'global-invocations.txt')!r}).open('a') as s:\n    s.write('executed\\n')\n"
        source += "Path('marker.txt').write_text('executed\\n')\n"
        if not omit_artifact:
            source += f"Path('result.json').write_text(json.dumps({{'value':{value}}}))\n"
        source += f"raise SystemExit({exit_code})\n"
        (job / "experiment.py").write_text(source, encoding="utf-8")
        return {"hypothesis_id": self.hypothesis, "change": "test concrete local measurement",
                "comparison": "independent fixed value 3", "data_split": "local fixed fixture",
                "seed": 7, "source_version": {"label": label, "files": {
                    "experiment.py": hashlib.sha256((job / "experiment.py").read_bytes()).hexdigest()}},
                "metrics": ["pass_rate"], "criteria": [{"metric": "pass_rate", "op": ">=", "threshold": 1}],
                "command": [sys.executable, "experiment.py"], "cwd": str(job),
                "artifacts": [{"name": "result.json", "path": "result.json"},
                              {"name": "marker.txt", "path": "marker.txt"}],
                "validator": "fixed", "conditions": {"fixture": label}}

    def register(self, spec, key="registration", error=None, expect=None):
        args = ["register", "--goal", self.goal, "--input", "-", "--request-key", key]
        if expect is not None:
            args += ["--expect", str(expect)]
        return self.cli(*args, payload=spec, error=error)

    def execute_run(self, registration, key="run"):
        return self.cli("run", "--registration", registration, "--request-key", key, "--full")

    def show(self, registration):
        return self.cli("show", "--registration", registration)

    def verify(self, registration):
        return self.cli("verify", "--registration", registration, "--full")['record']

    def test_execution_verification_and_adoption_are_separate(self):
        spec = self.make_spec()
        registration = self.register(spec)['registration']['id']
        self.cli("verify", "--registration", registration, error="INVALID_TRANSITION")
        self.cli("decide", "--registration", registration, "--decision", "adopted", "--reason", "claim",
                 error="INVALID_TRANSITION")
        for kind in ("measured", "literature", "inference", "proposal"):
            self.cli("evidence", "--registration", registration, "--kind", kind,
                     "--claim", "pass_rate=1; agent declares success")
        self.assertIsNone(self.show(registration)['verification'])
        completed = self.execute_run(registration)['record']
        self.assertEqual(completed['run']['state'], 'succeeded')
        self.assertIsNone(completed['verification'])
        self.cli("decide", "--registration", registration, "--decision", "adopted", "--reason", "exit 0",
                 error="INVALID_TRANSITION")
        verified = self.verify(registration)
        self.assertEqual(verified['verification']['state'], 'passed')
        self.assertEqual(verified['decision']['state'], 'pending')
        self.cli("decide", "--registration", registration, "--decision", "adopted", "--reason", "fixed verifier passed")
        record = self.show(registration)
        self.assertEqual(record['decision']['state'], 'adopted')
        submitted = [e for e in record['evidence'] if e['run_id'] is None]
        self.assertEqual(len(submitted), 4)
        self.assertTrue(all(not e['verified'] for e in submitted))

    def test_preregistration_is_immutable_and_changed_conditions_require_new_record(self):
        spec = self.make_spec()
        first = self.register(spec)['registration']['id']
        changed = copy.deepcopy(spec)
        changed['criteria'][0]['threshold'] = 0.5
        self.register(changed, error="REQUEST_CONFLICT")
        second = self.register(changed, key="new-criteria")['registration']['id']
        self.assertNotEqual(first, second)
        self.assertEqual(self.show(first)['registration']['spec']['criteria'][0]['threshold'], 1)
        db = sqlite3.connect(self.workspace / ".research/state.sqlite3")
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE registrations SET spec=? WHERE id=?", (json.dumps(changed), first))
            db.rollback()
        finally:
            db.close()

    def test_revision_conflict_rolls_back_write(self):
        before = self.cli("status")
        self.cli("hypothesis", "--goal", self.goal, "--statement", "valid concurrent new record")
        after = self.cli("status")
        self.cli("hypothesis", "--goal", self.goal, "--statement", "stale proposal",
                 "--expect", str(before['revision']), error="REVISION_CONFLICT")
        final = self.cli("status")
        self.assertEqual(final['revision'], after['revision'])
        self.assertEqual(len(final['hypotheses']), len(after['hypotheses']))

    def test_description_changes_and_repeated_requests_do_not_rerun(self):
        spec = self.make_spec()
        first = self.register(spec)
        registration = first['registration']['id']
        renamed = self.cli("hypothesis", "--goal", self.goal, "--statement", "same experiment in other words")
        other = copy.deepcopy(spec)
        other['hypothesis_id'] = renamed['id']
        other['description'] = "New prose does not change concrete conditions"
        reused = self.register(other, key="renamed")
        self.assertTrue(reused['reused'])
        self.assertEqual(reused['registration']['id'], registration)
        self.assertTrue(self.execute_run(registration)['started'])
        self.assertFalse(self.execute_run(registration)['started'])
        self.assertFalse(self.execute_run(registration, "different-request-same-experiment")['started'])
        self.assertEqual((self.temporary / "global-invocations.txt").read_text().splitlines(), ['executed'])

    def test_two_cli_processes_cannot_claim_the_same_execution(self):
        registration = self.register(self.make_spec(blocked=True))['registration']['id']
        first = self.launch("run", "--registration", registration, "--request-key", "concurrent")
        self.wait_for(lambda: list((self.workspace / ".research/runs").glob("*/process.json")))
        second = self.launch("run", "--registration", registration, "--request-key", "concurrent")
        output, errors = second.communicate()
        result = self.decode(subprocess.CompletedProcess(second.args, second.returncode, output, errors))
        self.assertFalse(result['started'])
        self.assertEqual(result['record']['run']['state'], 'running')
        (self.temporary / "gate").touch()
        output, errors = first.communicate()
        result = self.decode(subprocess.CompletedProcess(first.args, first.returncode, output, errors))
        self.assertTrue(result['started'])
        self.assertEqual(result['record']['run']['state'], 'succeeded')
        self.assertEqual((self.temporary / "global-invocations.txt").read_text().splitlines(), ['executed'])

    def test_controller_interruption_recovers_original_worker_without_relaunch(self):
        registration = self.register(self.make_spec(blocked=True))['registration']['id']
        controller = self.launch("run", "--registration", registration, "--request-key", "interrupted")
        self.wait_for(lambda: list((self.workspace / ".research/runs").glob("*/process.json")))
        controller.terminate()
        controller.communicate()
        recovered = self.cli("recover", "--registration", registration)
        self.assertEqual(recovered['record']['run']['state'], 'unknown')
        self.assertIn('resume', recovered)
        self.assertFalse(self.execute_run(registration, "repeat-during-unknown")['started'])
        (self.temporary / "gate").touch()
        self.wait_for(lambda: list((self.workspace / ".research/runs").glob("*/receipt.json")))
        recovered = self.cli("recover", "--registration", registration)
        self.assertEqual(recovered['record']['run']['state'], 'succeeded')
        self.assertEqual((self.temporary / "global-invocations.txt").read_text().splitlines(), ['executed'])

    def test_claim_without_launch_stays_unknown_without_automatic_restart(self):
        from research_cli.core import Store
        registration = self.register(self.make_spec())['registration']['id']
        Store(self.workspace).claim(registration, 'crashed-before-launch')
        recovered = self.cli("recover", "--registration", registration)
        self.assertEqual(recovered['record']['run']['state'], 'unknown')
        self.assertFalse(self.execute_run(registration, "try-again")['started'])
        self.assertFalse((self.temporary / "global-invocations.txt").exists())

    def test_success_failure_unknown_search_and_pagination(self):
        good = self.register(self.make_spec("good"), "good")['registration']['id']
        self.execute_run(good, "good")
        self.verify(good)
        bad = self.register(self.make_spec("bad", value=2), "bad")['registration']['id']
        self.execute_run(bad, "bad")
        self.assertEqual(self.verify(bad)['verification']['state'], 'failed')
        unknown = self.register(self.make_spec("unknown"), "unknown")['registration']['id']
        from research_cli.core import Store
        Store(self.workspace).claim(unknown, 'unknown')
        self.cli("recover", "--registration", unknown)
        for outcome, expected, verified in (("success", good, True), ("failure", bad, False),
                                             ("inconclusive", unknown, False)):
            page = self.cli("memory", "--outcome", outcome, "--limit", "1")
            self.assertEqual(page['total'], 1)
            self.assertEqual(page['items'][0]['id'], expected)
            self.assertEqual(page['items'][0]['claim_verified'], verified)
            self.assertNotIn('evidence', page['items'][0])
            self.assertIn('conditions', page['items'][0])
        first = self.cli("memory", "--limit", "1", "--offset", "0")
        second = self.cli("memory", "--limit", "1", "--offset", "1")
        self.assertEqual(first['total'], 3)
        self.assertNotEqual(first['items'][0]['id'], second['items'][0]['id'])
        self.assertEqual(self.cli("memory", "--query", "test concrete")['total'], 3)
        self.cli("decide", "--registration", bad, "--decision", "adopted", "--reason", "unsupported",
                 error="INVALID_TRANSITION")

    def test_missing_artifact_and_changed_source_cannot_verify(self):
        missing = self.register(self.make_spec("missing", omit_artifact=True), "missing")['registration']['id']
        self.assertEqual(self.execute_run(missing, "missing")['record']['run']['state'], 'succeeded')
        record = self.verify(missing)
        self.assertEqual(record['verification']['state'], 'inconclusive')
        spec = self.make_spec("source-tamper")
        changed = self.register(spec, "source-tamper")['registration']['id']
        (Path(spec['cwd']) / 'experiment.py').write_text("raise SystemExit(0)\n", encoding="utf-8")
        record = self.execute_run(changed, "source-tamper")['record']
        self.assertEqual(record['run']['state'], 'failed')
        self.assertIn('Pinned source hash mismatch', record['run']['receipt']['error'])
        self.assertEqual(self.verify(changed)['verification']['state'], 'inconclusive')

    def test_evidence_and_fixed_validator_tampering_are_detected(self):
        first = self.register(self.make_spec("evidence-tamper"), "one")['registration']['id']
        record = self.execute_run(first, "one")['record']
        item = next(e for e in record['evidence'] if e['name'] == 'result.json')
        (self.workspace / item['path']).write_text('{"value":999}', encoding="utf-8")
        self.assertEqual(self.verify(first)['verification']['state'], 'inconclusive')
        self.assertFalse(self.cli("memory", "--query", "evidence-tamper")['items'][0]['claim_verified'])
        second = self.register(self.make_spec("validator-tamper", value=2), "two")['registration']['id']
        self.execute_run(second, "two")
        frozen = next((self.workspace / '.research/validators').glob('*.py'))
        frozen.write_text("print('{\"metrics\":{\"pass_rate\":1}}')\n", encoding="utf-8")
        self.assertEqual(self.verify(second)['verification']['state'], 'inconclusive')

    def test_capability_required_and_verification_cannot_be_overwritten(self):
        wrong = self.temporary / 'wrong.key'
        wrong.write_text('agent-has-no-owner-capability', encoding='utf-8')
        self.cli('validator', '--name', 'untrusted', '--input', '-', '--key', str(wrong),
                 payload=[sys.executable, str(self.validator), '{bundle}'], error='AUTHORITY_REQUIRED')
        registration = self.register(self.make_spec())['registration']['id']
        record = self.execute_run(registration)['record']
        from research_cli.core import ResearchError, Store
        store = Store(self.workspace)
        with self.assertRaises(ResearchError) as caught:
            store.complete_verification(record['run']['id'], {'pass_rate': 1}, {}, 'external-agent')
        self.assertEqual(caught.exception.code, 'AUTHORITY_REQUIRED')
        self.verify(registration)
        with self.assertRaises(ResearchError) as caught:
            store.complete_verification(record['run']['id'], {'pass_rate': 0}, {}, store.internal_key())
        self.assertEqual(caught.exception.code, 'INVALID_TRANSITION')

    def test_verified_history_does_not_hide_later_evidence_tampering(self):
        registration = self.register(self.make_spec())['registration']['id']
        self.execute_run(registration)
        record = self.verify(registration)
        item = next(e for e in record['evidence'] if e['name'] == 'result.json')
        (self.workspace / item['path']).unlink()
        self.cli('verify', '--registration', registration, error='EVIDENCE_INVALID')
        self.cli('decide', '--registration', registration, '--decision', 'adopted', '--reason', 'historical pass',
                 error='EVIDENCE_MISSING')
        memory = self.cli('memory')
        self.assertEqual(memory['items'][0]['verification'], 'passed')
        self.assertFalse(memory['items'][0]['claim_verified'])

    def test_model_executable_and_malformed_json_are_rejected(self):
        spec = self.make_spec()
        spec['command'][0] = 'codex'
        self.register(spec, error='INVALID_INPUT')
        completed = subprocess.run(self.argv('register', '--goal', self.goal, '--input', '-',
                                             '--request-key', 'malformed'),
                                   cwd=ROOT, env=self.env, input='{broken', capture_output=True,
                                   text=True, encoding='utf-8')
        self.decode(completed, error='INVALID_INPUT')
        self.assertEqual(self.cli('status')['total'], 0)

    def test_export_restore_preserves_records_and_reuses_completed_execution(self):
        registration = self.register(self.make_spec())['registration']['id']
        self.execute_run(registration)
        self.verify(registration)
        export_file = self.temporary / 'portable.zip'
        self.cli('export', '--output', str(export_file))
        restored = self.temporary / 'restored'
        self.cli('restore', '--input', str(export_file), workspace=restored)
        original = self.show(registration)
        copy_record = self.cli('show', '--registration', registration, workspace=restored)
        self.assertEqual(original['registration'], copy_record['registration'])
        self.assertEqual(original['run'], copy_record['run'])
        self.assertEqual(original['verification'], copy_record['verification'])
        self.assertEqual(original['evidence'], copy_record['evidence'])
        reused = self.cli('run', '--registration', registration, '--request-key', 'restored-request', workspace=restored)
        self.assertFalse(reused['started'])
        self.assertEqual((self.temporary / 'global-invocations.txt').read_text().splitlines(), ['executed'])

    def test_malformed_or_nonfinite_validator_output_is_inconclusive(self):
        outputs = ('{"metrics":"agent-success-claim"}', '{"metrics":{"pass_rate":NaN}}', '{broken')
        for index, output in enumerate(outputs):
            name = 'malformed-' + str(index)
            script = self.temporary / (name + '.py')
            script.write_text(f"print({output!r})\n", encoding='utf-8')
            self.cli('validator', '--name', name, '--input', '-', '--key', self.initial['owner_key_path'],
                     payload=[sys.executable, str(script), '{bundle}'])
            spec = self.make_spec(name)
            spec['validator'] = name
            registration = self.register(spec, name)['registration']['id']
            self.execute_run(registration, name)
            self.assertEqual(self.verify(registration)['verification']['state'], 'inconclusive')

    def test_restore_rejects_archive_parent_traversal_before_writing(self):
        registration = self.register(self.make_spec())['registration']['id']
        self.execute_run(registration)
        archive_path = self.temporary / 'clean.zip'
        self.cli('export', '--output', str(archive_path))
        hostile_path = self.temporary / 'hostile.zip'
        bad_name = '.research/../outside.txt'
        content = b'unsafe archive entry'
        with zipfile.ZipFile(archive_path) as source:
            manifest = json.loads(source.read('manifest.json'))
            manifest['files'][bad_name] = {'sha256': hashlib.sha256(content).hexdigest(), 'bytes': len(content)}
            with zipfile.ZipFile(hostile_path, 'w') as destination:
                for name in source.namelist():
                    if name != 'manifest.json':
                        destination.writestr(name, source.read(name))
                destination.writestr(bad_name, content)
                destination.writestr('manifest.json', json.dumps(manifest))
        target = self.temporary / 'unsafe-restore'
        self.cli('restore', '--input', str(hostile_path), workspace=target, error='EVIDENCE_INVALID')
        self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main()

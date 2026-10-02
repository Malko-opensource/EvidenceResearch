"""Source-snapshotted owner sampler fixtures, without providers or research fits.

Only temporary SYNTHETIC owner rows created here may be opened. Existing study
rows, registered evidence and frozen packages are never opened or modified.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
CANDIDATE=ROOT / "work/c6"
OUT=ROOT / "evidence/c6-independent-sampler-v2"


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if OUT.exists():raise ValueError("preserve prior independent sampler audit")
    OUT.mkdir(parents=True);snapshot=OUT / "source-snapshot";snapshot.mkdir()
    paths=list((CANDIDATE / "evidence_research").glob("*.py"))+[CANDIDATE / "tests" / name for name in ("test_sampled_pilot.py","test_study.py")]
    before={str(path):digest(path) for path in paths}
    for path in paths:
        target=snapshot / path.relative_to(CANDIDATE);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
        if digest(target)!=before[str(path)]:raise ValueError("source changed during snapshot")
    (snapshot / "tests/__init__.py").write_text("# Independent test snapshot package marker.\n",encoding="utf-8")
    shutil.copyfile(Path(__file__),snapshot / Path(__file__).name)
    frozen_before={str(path):digest(path) for base in (ROOT / "evidence_research",ROOT / "versions/v5-development/evidence_research") for path in base.glob("*.py")}
    fixture_root=ROOT / "work/c6-independent-sampler-fixtures-v2"
    if fixture_root.exists():raise ValueError("preserve previous temporary fixture workspace")
    fixture_root.mkdir()
    counts={"providers_blocked":0,"research_runner_or_fit_blocked":0,"original_owner_reads_blocked":0,"external_processes_blocked":0}
    def audit(event,args):
        if event=="open" and args and not isinstance(args[0],int):
            p=Path(os.fsdecode(args[0])).resolve()
            if p.is_relative_to(ROOT) and not p.is_relative_to(fixture_root) and ("runs" in p.relative_to(ROOT).parts or p.name.lower().endswith("-owner.json") or p.name.lower()=="private-suite.json"):
                counts["original_owner_reads_blocked"]+=1;raise RuntimeError("original owner/study paths cannot be opened")
        if event in {"subprocess.Popen","os.system","os.posix_spawn","os.posix_spawnp"}:
            counts["external_processes_blocked"]+=1;raise RuntimeError("independent sampler cannot launch processes")
    sys.addaudithook(audit);sys.path.insert(0,str(snapshot))
    from evidence_research import tasks
    from evidence_research.model import CodexProvider,FileProvider
    def block_provider(*a,**k):counts["providers_blocked"]+=1;raise RuntimeError("no providers permitted")
    def block_fit(*a,**k):counts["research_runner_or_fit_blocked"]+=1;raise RuntimeError("no research fits permitted")
    CodexProvider.complete=block_provider;FileProvider.complete=block_provider;tasks.run_task=block_fit;tasks.fit=block_fit
    from evidence_research.study import create_sampled_pilot_config,register_pilot,load
    from evidence_research.evaluation import create_final_suite,_validate_final_suite_draws
    from tests import test_sampled_pilot
    from tests.test_study import settings
    original_tempdir=tempfile.TemporaryDirectory
    def controlled_temporary_directory(*args,**kwargs):
        kwargs["dir"]=fixture_root
        value=original_tempdir(*args,**kwargs)
        if not Path(value.name).resolve().is_relative_to(fixture_root):raise RuntimeError("temporary cleanup target escaped fixture workspace")
        return value

    class IndependentNegativeFixtures(unittest.TestCase):
        def setUp(self):
            self.temp=controlled_temporary_directory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        def test_secure_default_branch_calls_randbits256_and_does_not_print_owner_seed(self):
            base=settings();base.pop("units");path=self.root / "synthetic-owner-config.json"
            # Known value is synthetic, never an actual secret generation seed.
            with patch("secrets.randbits",return_value=2**255+451) as entropy:
                receipt=create_sampled_pilot_config(base,path,variance_relative_se=1)
            entropy.assert_called_once_with(256);config=load(path)
            self.assertEqual(config["owner_sampling_seed"],2**255+451)
            self.assertNotIn("owner_sampling_seed",receipt);self.assertNotIn("coefficients",receipt)
            registered=register_pilot(config,self.root / "synthetic-registration")
            for unit in registered["units"]:
                public=load(unit["public_path"]);encoded=json.dumps(public)
                for key in ("owner_sampling_seed","owner_split_seeds","owner_sampled_definition","coefficients","noise"):
                    self.assertNotIn(key,encoded)
        def test_final_secure_default_branch_hides_private_fields(self):
            with patch("secrets.randbits",return_value=2**255+729) as entropy:
                receipt=create_final_suite(self.root / "synthetic-suite",n_pairs=2,excluded_development_definition_hashes=[])
            entropy.assert_called_once_with(256);private=load(receipt["private_file"]);_validate_final_suite_draws(private)
            self.assertNotIn("owner_sampling_seed",receipt)
            for unit in private["units"]:
                encoded=json.dumps(load(unit["public_file"]))
                for key in ("owner_sampling_seed","owner_split_seeds","owner_sampled_definition","coefficients","noise"):
                    self.assertNotIn(key,encoded)
        def test_private_field_injected_into_public_payload_is_rejected_even_after_rehash(self):
            for field in ("owner_sampling_seed","owner_split_seeds","test"):
                suite=create_final_suite(self.root / f"inject-{field}",n_pairs=2,owner_seed=813,excluded_development_definition_hashes=[])
                private=load(suite["private_file"]);unit=private["units"][0];path=Path(unit["public_file"]);public=load(path)
                public[field]=private["owner_sampling_seed"] if field=="owner_sampling_seed" else unit[field]
                tasks.write_json(path,public);unit["public_sha256"]=tasks.sha256_file(path)
                with self.subTest(field=field),self.assertRaises(ValueError):_validate_final_suite_draws(private)

    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromModule(test_sampled_pilot),unittest.defaultTestLoader.loadTestsFromTestCase(IndependentNegativeFixtures)])
    log=io.StringIO()
    with patch("tempfile.TemporaryDirectory",side_effect=controlled_temporary_directory):
        result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    (OUT / "test.log").write_text(log.getvalue(),encoding="utf-8")
    after={path:digest(Path(path)) for path in before};frozen_after={path:digest(Path(path)) for path in frozen_before}
    snapshot_hashes={str(path):digest(path) for path in snapshot.rglob("*") if path.is_file() and "__pycache__" not in path.parts}
    proof={"tests_run":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),"successful":result.wasSuccessful(),"source":{"path":str(Path(__file__)),"sha256":digest(Path(__file__))},"candidate_before":before,"candidate_after":after,"candidate_sources_unchanged":before==after,"source_snapshot":snapshot_hashes,"frozen_before":frozen_before,"frozen_after":frozen_after,"main_and_v5_sources_unchanged":frozen_before==frozen_after,"guard_counts":counts,"actual_model_requests":0,"research_runner_calls":0,"research_fit_calls":0,"original_owner_observations_opened":False,"synthetic_owner_data_policy":"Only ephemeral known-generation fixtures were read; weak explicit seeds and mocked entropy values are test fixtures, not future study seeds or evidence of entropy strength.","scope":"Component sampling/separation/draw-replay fixtures only. Does not certify all final execution, upstream source constants, natural-language reports or framework improvement."}
    (OUT / "result.json").write_text(json.dumps(proof,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({key:proof[key] for key in ("tests_run","failures","errors","successful","candidate_sources_unchanged","main_and_v5_sources_unchanged","guard_counts","actual_model_requests","research_runner_calls","original_owner_observations_opened")}))
    if any(counts.values()) or frozen_before!=frozen_after:raise RuntimeError("independent source/operation guard failed")
    if not result.wasSuccessful():raise SystemExit(1)


if __name__=="__main__":main()

"""Protocol/path/credential fixtures only; no Git mutation or model calls."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts/release_check_batch.py"
spec = importlib.util.spec_from_file_location("fixture_batch_checker", MODULE_PATH)
checker = importlib.util.module_from_spec(spec); spec.loader.exec_module(checker)


def object_id(data, algorithm="sha1"):
    function = hashlib.sha1 if algorithm == "sha1" else hashlib.sha256
    return function(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def entry(name, data, *, mode="100644", stage=0):
    return {"path":name,"mode":mode,"stage":stage,"oid":object_id(data)}


def response(data, algorithm="sha1"):
    oid = object_id(data,algorithm)
    return oid.encode() + b" blob " + str(len(data)).encode() + b"\n" + data + b"\n"


class BatchContracts(unittest.TestCase):
    def setUp(self):
        owned = Path(__file__).resolve().parent / "work"
        owned.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=owned)
        self.root = Path(self.temp.name).resolve()
        self.assertTrue(self.root.is_relative_to(owned.resolve()))
        self.addCleanup(self.temp.cleanup)

    def write(self,name,data):
        path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)

    def test_nul_names_preserve_tabs_newlines_unicode_and_sha256_identity(self):
        names=["normal.py","folder/tab\tline\n\uac80\uc99d.txt"]
        data=b"100644 "+b"a"*40+b" 0\t"+names[0].encode()+b"\0"
        data+=b"100755 "+b"b"*64+b" 0\t"+names[1].encode()+b"\0"
        rows=checker.parse_index_records(data)
        self.assertEqual([row["path"] for row in rows],names)
        self.assertEqual([len(row["oid"]) for row in rows],[40,64])

    def test_malformed_or_unterminated_index_fails_closed(self):
        for data in [b"100644 "+b"a"*40+b" 0\tfile",b"100644 bad 0\tfile\0",b"invalid\0"]:
            with self.assertRaises(checker.ReleaseCheckError):checker.parse_index_records(data)

    def test_exact_binary_body_terminator_and_sequential_responses(self):
        first=b"abc\n\0\xff tail";second=b"";third=b"utf8 body"
        stream=io.BytesIO(response(first)+response(second)+response(third,"sha256"))
        for data,algorithm in [(first,"sha1"),(second,"sha1"),(third,"sha256")]:
            self.assertEqual(checker.read_batch_blob(stream,object_id(data,algorithm)),data)
        self.assertEqual(stream.read(),b"")

    def test_wrong_oid_type_size_eof_body_hash_or_terminator_rejected(self):
        data=b"protocol fixture only";oid=object_id(data)
        malformed=[b"0"*40+b" blob 0\n\n",oid.encode()+b" missing\n",
            oid.encode()+b" tree 0\n\n",oid.encode()+b" blob 999\nshort",
            response(data)[:-1]+b"X",oid.encode()+b" blob 1\nX\n"]
        for value in malformed:
            with self.assertRaises(checker.ReleaseCheckError):checker.read_batch_blob(io.BytesIO(value),oid)

    def test_manifest_is_staged_bytes_and_matches_legacy_core_fields(self):
        data=b"ordinary source";self.write("source.py",data)
        result=checker.scan_entries(self.root,[entry("source.py",data)],lambda oid:data)
        self.assertEqual(result,{"valid":True,"file_count":1,"credential_values_printed":False,"rejected":[],
            "manifest":[{"path":"source.py","bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()}],"scope":checker.SCOPE})

    def test_missing_and_work_changed_files_remain_rejected_with_staged_manifest(self):
        data=b"staged fixture";self.write("changed.py",b"later working fixture")
        for name in ("missing.py","changed.py"):
            result=checker.scan_entries(self.root,[entry(name,data)],lambda oid:data)
            self.assertFalse(result["valid"]);self.assertEqual(len(result["rejected"]),1)
            self.assertEqual(result["manifest"][0]["sha256"],hashlib.sha256(data).hexdigest())

    def test_private_and_external_paths_do_not_read_staged_bodies(self):
        names=[".venv/a.py",".runtime/a","private-evaluation/test.json","model-public/a","__pycache__/a","auth.json",".env","../outside"]
        calls=[]
        result=checker.scan_entries(self.root,[entry(name,b"unused") for name in names],lambda oid:calls.append(oid))
        self.assertFalse(result["valid"]);self.assertEqual(calls,[]);self.assertEqual(result["manifest"],[])
        self.assertEqual(len(result["rejected"]),len(names))

    def test_conflicts_duplicate_modes_and_symlinks_fail_closed_without_blob_read(self):
        data=b"ordinary";self.write("same.py",data)
        for rows in ([entry("same.py",data,stage=1),entry("same.py",data,stage=2)],
                     [entry("same.py",data,mode="120000")],[entry("same.py",data,mode="160000")]):
            calls=[];result=checker.scan_entries(self.root,rows,lambda oid:calls.append(oid))
            self.assertFalse(result["valid"]);self.assertEqual(calls,[])
        result=checker.scan_entries(self.root,[entry("same.py",data),entry("same.py",data)],lambda oid:data)
        self.assertFalse(result["valid"])

    def test_all_legacy_credential_patterns_reject_without_match_values(self):
        samples=[b"ghp_"+b"A"*25,b"sk-proj-"+b"B"*30,b"-----BEGIN "+b"OPENSSH "+b"PRIVATE KEY-----"]
        for number,data in enumerate(samples):
            name=f"credential-format-fixture-{number}";self.write(name,data)
            result=checker.scan_entries(self.root,[entry(name,data)],lambda oid:data)
            self.assertFalse(result["valid"])
            serialized=json.dumps(result).encode()
            self.assertNotIn(data,serialized)
            self.assertEqual(result["rejected"][0]["reason"],"credential pattern detected; value withheld")

    def test_cli_summary_never_prints_blob_credentials_and_staged_output_is_refused(self):
        data=b"sk-"+b"C"*40;self.write("fixture.txt",data)
        rows=[entry("fixture.txt",data)];result=checker.scan_entries(self.root,rows,lambda oid:data)
        index=b"100644 "+rows[0]["oid"].encode()+b" 0\tfixture.txt\0"
        capture=io.StringIO()
        with patch.object(checker,"git_index",return_value=index),patch.object(checker,"scan",return_value=(result,{"wall_seconds":0.0})),contextlib.redirect_stdout(capture):
            code=checker.main(["--root",str(self.root),"--output",str(self.root/"result.json")])
        self.assertEqual(code,1);self.assertNotIn(data.decode(),capture.getvalue())
        staged_output=b"100644 "+rows[0]["oid"].encode()+b" 0\tnew-result.json\0"
        with patch.object(checker,"git_index",return_value=staged_output),self.assertRaisesRegex(checker.ReleaseCheckError,"output is staged"):
            checker.main(["--root",str(self.root),"--output",str(self.root/"new-result.json")])


if __name__=="__main__":unittest.main(verbosity=2)

"""Prospective local-binding/public-row guards. Synthetic transport; no fits."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evidence_research import context_boundary as cb
from evidence_research.tasks import TASK_VERSION, value_hash
from tests.test_context_boundaries import TapeFixture, put as _put, sha


def put(path,value):
    _put(Path(path),value)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def link(path):
    return {'path':str(Path(path).resolve()), 'sha256':sha(path)}


def literal_public():
    task, seed = 'public-engineering-fixture', 7
    train = [{'id':f'{task}:{seed}:train:0', 'x':-1.0, 'y':1.0},
             {'id':f'{task}:{seed}:train:1', 'x':1.0, 'y':1.0}]
    validation = [{'id':f'{task}:{seed}:validation:0', 'x':0.0, 'y':0.0}]
    splits = {name:{'count':len(rows), 'sha256':value_hash(rows),
                    'ids_sha256':value_hash([row['id'] for row in rows])}
              for name, rows in (('train',train), ('validation',validation), ('test',[]))}
    return {'task_id':task, 'seed':seed, 'task_version':TASK_VERSION,
            'task_bundle':{'train':train, 'validation':validation,
                'split_manifest':{'task_id':task, 'seed':seed, 'task_version':TASK_VERSION,
                                  'generation':'Explicit fixed public component rows; no owner sampler', 'splits':splits}}}


def rehash_boundary(fixture, triple, *, binding=None, original_link=None):
    """Change local packet hashes, never hide the original binding difference."""
    boundary, _, _ = triple
    value = read(boundary['path'])
    if binding is not None:
        value['binding'] = binding
    if original_link is not None:
        value['original_binding'] = original_link
    put(boundary['path'],value)
    replacement = link(boundary['path'])
    rows = [json.loads(line) for line in fixture.recorder.path.read_text().splitlines()]
    previous = None
    for row in rows:
        if row.get('boundary') == boundary:
            row['boundary'] = replacement
        row['previous_sha256'] = previous
        row['event_sha256'] = cb._hash({key:item for key,item in row.items() if key != 'event_sha256'})
        previous = row['event_sha256']
    fixture.recorder.path.write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows),encoding='utf-8')
    transport = [json.loads(line) for line in fixture.transport.read_text().splitlines()]
    for row in transport:
        if row.get('context_boundary') == boundary:
            row['context_boundary'] = replacement
    fixture.transport.write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in transport),encoding='utf-8')
    return replacement


class OriginalBindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='context-local-binding-')
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def fixture(self, name='one', *, arm='C', public=None, qualified=True):
        return TapeFixture(self.root/name,arm,fixture_only=qualified,
                           public_task=literal_public() if public is None else public)

    def test_valid_explicit_b_c_prefix_keeps_facts_and_original_binding_evidence(self):
        measures = []
        for arm in ('B','C'):
            f = self.fixture(arm,arm=arm)
            with (patch('evidence_research.tasks.task_data',side_effect=AssertionError('no generation')),
                  patch('evidence_research.tasks.run_task',side_effect=AssertionError('no fitting'))):
                f.model(); boundary,_,_ = f.model()
                facts = cb.audit_context_boundary(boundary,f.root)
            self.assertFalse(facts['eligible']); self.assertTrue(facts['fixture_only'])
            self.assertIn(link(f.root/'context-boundaries/binding.json'),facts['evidence'])
            measures.append(facts['measures'])
        self.assertEqual(measures[0],measures[1])

    def test_original_binding_missing_is_not_reconstructed_from_boundary(self):
        f = self.fixture(); triple = f.model()
        (f.root/'context-boundaries/binding.json').unlink()
        with self.assertRaises(ValueError): cb.audit_context_boundary(triple[0],f.root)

    def test_original_binding_raw_mutation_invalidates_original_capture_link(self):
        f = self.fixture(); triple = f.model()
        path = f.root/'context-boundaries/binding.json'
        path.write_text(path.read_text()+' ',encoding='utf-8')
        with self.assertRaises(ValueError): cb.audit_context_boundary(triple[0],f.root)

    def test_rehashed_binding_file_cannot_change_its_complete_original_value(self):
        f = self.fixture(); triple = f.model()
        path = f.root/'context-boundaries/binding.json'
        value = read(path); value['resource_envelope_sha256']='0'*64; put(path,value)
        replacement = rehash_boundary(f,triple,original_link=link(path))
        with self.assertRaises(ValueError): cb.audit_context_boundary(replacement,f.root)

    def test_same_value_binding_copy_is_not_its_original_location(self):
        f = self.fixture(); triple = f.model()
        copied = f.root/'copied-binding.json'; put(copied,read(f.root/'context-boundaries/binding.json'))
        replacement = rehash_boundary(f,triple,original_link=link(copied))
        with self.assertRaises(ValueError): cb.audit_context_boundary(replacement,f.root)

    def test_registration_and_boundary_rehash_cannot_replace_original_task_conditions(self):
        f = self.fixture(); triple = f.model()
        original = read(f.root/'context-boundaries/binding.json')
        registration = read(f.registration); registration['public_task']['task_bundle']['train'][0]['y']=999
        put(f.registration,registration)
        binding = deepcopy(original); binding['registration']=link(f.registration)
        binding['public_task_sha256']=cb._hash(registration['public_task'])
        replacement = rehash_boundary(f,triple,binding=binding)
        with self.assertRaises(ValueError): cb.audit_context_boundary(replacement,f.root)
        self.assertEqual(read(f.root/'context-boundaries/binding.json'),original)

    def test_model_and_resource_joint_rehash_cannot_replace_original_binding(self):
        for key in ('model','resources'):
            f = self.fixture(key); triple = f.model(); binding=read(f.root/'context-boundaries/binding.json')
            registration=read(f.registration)
            if key=='model': registration['model_id']='other-model'; binding['model_id']='other-model'
            else:
                registration['resource_envelope']['network']=True
                binding['resource_envelope_sha256']=cb._hash(registration['resource_envelope'])
            put(f.registration,registration); binding['registration']=link(f.registration)
            replacement=rehash_boundary(f,triple,binding=binding)
            with self.assertRaises(ValueError): cb.audit_context_boundary(replacement,f.root)

    def test_changed_original_binding_blocks_a_later_capture_without_provider_packet(self):
        f = self.fixture(); f.model()
        path=f.root/'context-boundaries/binding.json'; value=read(path); value['arm']='B'; put(path,value)
        requests_before=list(f.root.rglob('request.json'))
        with self.assertRaises(ValueError): f.model('later input')
        self.assertEqual(list(f.root.rglob('request.json')),requests_before)

    def test_every_prefix_input_must_reference_the_original_binding(self):
        f=self.fixture(); prior=f.model(); target=f.model()
        changed=read(prior[0]['path']); changed.pop('original_binding'); put(prior[0]['path'],changed)
        rehash_boundary(f,prior)
        # Rebind the target's exact changed prefix as well, so the new original
        # binding check is reached instead of an older raw-prefix hash guard.
        target_value=read(target[0]['path'])
        raw=f.recorder.path.read_bytes().splitlines(keepends=True)
        prefix=b''.join(raw[:target_value['prefix_event_count']])
        target_value['prefix_tape_sha256']=hashlib.sha256(prefix).hexdigest()
        put(target[0]['path'],target_value)
        replacement=rehash_boundary(f,target)
        with self.assertRaisesRegex(ValueError,'exact path/SHA'):
            cb.audit_context_boundary(replacement,f.root)

    def test_rows_ids_counts_and_identity_are_checked_before_capture(self):
        mutations=(lambda p:p['task_bundle']['train'][0].update(y=999),
                   lambda p:p['task_bundle']['train'][0].update(id='changed'),
                   lambda p:p['task_bundle']['split_manifest']['splits']['train'].update(count=999),
                   lambda p:p['task_bundle']['split_manifest']['splits']['validation'].update(ids_sha256='0'*64),
                   lambda p:p['task_bundle']['split_manifest'].update(task_id='different'),
                   lambda p:p['task_bundle']['split_manifest'].update(seed=8),
                   lambda p:p['task_bundle']['split_manifest'].update(task_version='different'))
        for index, mutate in enumerate(mutations):
            public=literal_public(); mutate(public)
            with self.assertRaises(ValueError): self.fixture(str(index),public=public)
            self.assertFalse((self.root/str(index)/'context-boundaries').exists())

    def test_incomplete_explicit_bundle_cannot_use_the_legacy_path(self):
        for key in ('train','validation','split_manifest'):
            public=literal_public(); public['task_bundle'].pop(key)
            with self.assertRaises(ValueError): self.fixture(key,public=public)

    def test_audit_checks_public_rows_even_if_local_binding_is_wholly_rewritten(self):
        f=self.fixture(); triple=f.model()
        registration=read(f.registration); registration['public_task']['task_bundle']['train'][0]['y']=999
        put(f.registration,registration)
        path=f.root/'context-boundaries/binding.json'; binding=read(path)
        binding['registration']=link(f.registration); binding['public_task_sha256']=cb._hash(registration['public_task']); put(path,binding)
        replacement=rehash_boundary(f,triple,binding=binding,original_link=link(path))
        with self.assertRaisesRegex(ValueError,'public bundle'): cb.audit_context_boundary(replacement,f.root)

    def test_legacy_no_bundle_does_not_generate_owner_or_task_rows(self):
        public={'task_id':'legacy-public-input','seed':7}
        with (patch('evidence_research.tasks.task_data',side_effect=AssertionError('no generation')),
              patch('evidence_research.tasks.run_task',side_effect=AssertionError('no fitting'))):
            f=self.fixture(public=public); boundary,_,_=f.model(); facts=cb.audit_context_boundary(boundary,f.root)
        self.assertFalse(facts['eligible']); self.assertTrue(facts['fixture_only'])
        self.assertEqual(facts['measures']['actual_cpu_executions'],0)

    def test_exact_opaque_marker_requires_original_qualification_not_a_later_raw_alias(self):
        public={'task_id':'synthetic-only','seed':7,'task_bundle':{'kind':'explicit_synthetic_fixture'}}
        with self.assertRaisesRegex(ValueError,'qualification'):
            self.fixture(public=public,qualified=False)
        # There is no provider request on which a later alias could repair capture.
        self.assertEqual(list(self.root.rglob('request.json')),[])

    def test_qualified_opaque_marker_stays_nonactual(self):
        public={'task_id':'synthetic-only','seed':7,'task_bundle':{'kind':'explicit_synthetic_fixture'}}
        f=self.fixture(public=public); boundary,_,_=f.model(); facts=cb.audit_context_boundary(boundary,f.root)
        self.assertTrue(facts['fixture_only']); self.assertFalse(facts['eligible'])

    def test_marker_extra_rows_or_unknown_shape_cannot_avoid_public_bundle_validation(self):
        for index, bundle in enumerate(({'kind':'explicit_synthetic_fixture','train':[]},
                                        {'kind':'unknown-marker'},None,{})):
            public={'task_id':'synthetic-only','seed':7,'task_bundle':bundle}
            with self.assertRaises(ValueError): self.fixture(str(index),public=public)

    def test_old_schema_is_not_relabelled_as_a_new_original_binding(self):
        f=self.fixture(); triple=f.model(); value=read(triple[0]['path'])
        value['schema_version']='original-context-boundary-1-development'; put(triple[0]['path'],value)
        with self.assertRaises(ValueError): cb.audit_context_boundary(link(triple[0]['path']),f.root)

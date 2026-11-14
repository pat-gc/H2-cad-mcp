"""Offline coordinator lifecycle tests; actual geometry and writers have separate suites."""
import asyncio
import copy
import json
from pathlib import Path

import pytest

from h2cad import source_run as run
from h2cad.backend import Unsupported, UncertainWrite
from h2cad.journal import Journal
from h2cad.model import Target
from h2cad.validation import ValidationReport

TARGET = Target('a'*24, 'b'*24, 'c'*24)
SOURCE = Path(__file__).resolve().parents[1] / 'fixtures/car/basic_car.fs'


def sync(coro):
    return asyncio.run(coro)


class Backend:
    create_target = TARGET.to_dict()
    tab_id = 123

    def __init__(self, journal):
        self.journal = journal
        self.calls = 0
        self.state = {'target': TARGET.to_dict(), 'connected': True, 'editingFeatureId': None,
                      'element_microversion': '1'*24, 'tree': {'$type': 'bsedit.GBTMModel', 'children': []}}

    async def raw_state(self, target):
        return copy.deepcopy(self.state)

    def allocate(self, kind='assignVariable'):
        self.state['editingFeatureId'] = 'fresh'
        self.state['element_microversion'] = '2'*24
        self.state['tree']['children'].append({'featureType': kind, 'featureId': 'fresh', 'nodeId': 'node-fresh'})

    async def populate_test_variable(self, target, source, *, logical_id, previous_op_ids, journal):
        self.calls += 1
        plan = run._plan(source, target)
        stages = [f['stage'] for f in plan if f['kind'] == 'assignVariable']
        index = next(i for i,s in enumerate(stages) if s['logical_id'] == logical_id)
        before = copy.deepcopy(self.state)
        self.state['tree']['children'][-1]['name'] = logical_id
        self.state.update(editingFeatureId=None, element_microversion='3'*24)
        journal.prepare(op_id='test-op', target='/'.join(target.to_dict().values()), expected_revision='2'*24,
            action='experimental_variable_populate', logical_id=logical_id,
            intent={'source_stages': stages, 'source_index': index, 'before_state': before,
                    'expected_tree': copy.deepcopy(self.state['tree'])})
        journal.transition('test-op', 'sent')
        journal.transition('test-op', 'observed', observation={'definition_observed': True,
                           'feature_id': 'fresh', 'node_id': 'node-fresh'})


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(run, 'validate_fsgen', lambda text: ValidationReport('passed'))
    journal = Journal(tmp_path/'journal.sqlite')
    path = tmp_path/'run.json'
    run.initialize_run(path, SOURCE, TARGET, journal)
    yield path, journal, Backend(journal)
    journal.close()


def test_real_car_plan_order_and_supported_count(setup):
    path, _, _ = setup
    data = json.loads(path.read_text())
    assert len(data['plan']) == 22
    assert data['plan'][0]['logical_id'] == '#length'
    assert [f['kind'] for f in data['plan'][7:10]] == ['cPlane','newSketch','extrude']


def test_stage_idempotent_then_apply_and_resume_no_duplicate(setup):
    path, journal, backend = setup
    first = sync(run.next_action(path, backend, SOURCE, TARGET, journal))
    assert first == sync(run.next_action(path, backend, SOURCE, TARGET, journal))
    assert first['action'] == 'browser_allocate' and first['logical_id'] == '#length'
    backend.allocate()
    result = sync(run.apply_staged(path, backend, SOURCE, TARGET, journal))
    assert result['observed_logical_id'] == '#length'
    assert sync(run.apply_staged(path, backend, SOURCE, TARGET, journal))['reason'] == 'no_unapplied_stage'
    assert backend.calls == 1
    assert sync(run.next_action(path, backend, SOURCE, TARGET, journal))['logical_id'] == '#width'


def test_crash_after_observed_write_adopts_without_replay(setup):
    path, journal, backend = setup
    sync(run.next_action(path, backend, SOURCE, TARGET, journal))
    backend.allocate()
    sync(backend.populate_test_variable(TARGET, SOURCE.read_text(), logical_id='#length', previous_op_ids=[], journal=journal))
    assert json.loads(path.read_text())['bindings'] == {}
    sync(run.apply_staged(path, backend, SOURCE, TARGET, journal))
    assert backend.calls == 1
    assert '#length' in json.loads(path.read_text())['bindings']


@pytest.mark.parametrize('change', ['deleted', 'modified'])
def test_old_observation_never_hides_human_change(setup, change):
    path,journal,backend=setup
    sync(run.next_action(path,backend,SOURCE,TARGET,journal)); backend.allocate()
    sync(backend.populate_test_variable(TARGET,SOURCE.read_text(),logical_id='#length',previous_op_ids=[],journal=journal))
    if change == 'deleted': backend.state['tree']['children'] = []
    else: backend.state['tree']['children'][0]['name'] = 'changed'
    with pytest.raises(Unsupported, match='changed in live tree'):
        sync(run.apply_staged(path,backend,SOURCE,TARGET,journal))
    assert backend.calls == 1


@pytest.mark.parametrize('change', ['source','target','baseline','tab','wrong_draft','unrelated'])
def test_changed_inputs_fail_before_writer(setup,change):
    path,journal,backend=setup
    sync(run.next_action(path,backend,SOURCE,TARGET,journal))
    text=SOURCE.read_text(); target=TARGET
    if change=='source': text += '\n// source changed\n'
    if change=='target': target=Target('d'*24,'b'*24,'c'*24)
    if change=='tab': backend.tab_id=456
    if change=='baseline': backend.state['element_microversion']='9'*24
    if change in ('wrong_draft','unrelated'):
        backend.allocate('extrude' if change=='wrong_draft' else 'assignVariable')
        if change=='unrelated': backend.state['tree']['children'].append({'featureId':'foreign'})
        operation=run.apply_staged
    else: operation=run.next_action
    with pytest.raises(Unsupported): sync(operation(path,backend,text,target,journal))
    assert backend.calls == 0


def test_unresolved_other_target_blocks_dispatch(setup):
    path,journal,backend=setup
    journal.prepare(op_id='pending',target='other',expected_revision='x',action='test',logical_id='x',intent={})
    with pytest.raises(UncertainWrite): sync(run.next_action(path,backend,SOURCE,TARGET,journal))
    assert backend.calls==0


def test_corrupt_observed_source_rejected(setup):
    path,journal,backend=setup
    sync(run.next_action(path,backend,SOURCE,TARGET,journal)); backend.allocate()
    sync(backend.populate_test_variable(TARGET,SOURCE.read_text(),logical_id='#length',previous_op_ids=[],journal=journal))
    intent=json.loads(journal.get('test-op')['intent']); intent['source_stages'][0]['expression']='1 mm'
    journal._db.execute('UPDATE writes SET intent=? WHERE op_id=?',(json.dumps(intent),'test-op'))
    with pytest.raises(Unsupported,match='provenance'): sync(run.next_action(path,backend,SOURCE,TARGET,journal))


def test_partial_local_validation_cannot_initialize(tmp_path,monkeypatch):
    journal=Journal(tmp_path/'journal.sqlite')
    monkeypatch.setattr(run,'validate_fsgen',lambda text: ValidationReport('partial'))
    with pytest.raises(Unsupported,match='validation'): run.initialize_run(tmp_path/'run.json',SOURCE,TARGET,journal)
    assert not (tmp_path/'run.json').exists()
    journal.close()


def test_plane_query_resolution_is_read_only_and_same_revision(setup):
    path,journal,backend=setup
    backend.allocate('cPlane')
    query={'deterministicIds':['observed']}
    backend.state['tree']['children'][0]['parameters']=[{'parameterId':'entities','queries':[query]}]
    class Bridge:
        async def command(self, payload):
            assert payload['kind']=='native' and payload['command']=='ui.GBTUiGetQueryDataCall'
            assert payload['body']['queries']==[query]
            return {'result':{'$type':'ui.GBTUiGetQueryDataResponse','queryData':[{'featureId':'Top'}]}}
    backend.bridge=Bridge()
    result=sync(run._plane_binding(backend,TARGET,copy.deepcopy(backend.state)))
    assert result['query_data']['featureId']=='Top'
    stale=copy.deepcopy(backend.state); stale['element_microversion']='4'*24
    with pytest.raises(Unsupported): sync(run._plane_binding(backend,TARGET,stale))


def test_inspection_diagnostics_do_not_invalidate_idle_stage(setup):
    path, journal, backend = setup
    first = sync(run.next_action(path, backend, SOURCE, TARGET, journal))
    backend.state['h2Readback'] = {'visitedCount': 99, 'truncated': True}
    assert sync(run.next_action(path, backend, SOURCE, TARGET, journal)) == first
    backend.state['h2Readback']['incompleteFeatureEdit'] = {'op_id': 'pending'}
    with pytest.raises(Unsupported, match='saved idle'):
        sync(run.next_action(path, backend, SOURCE, TARGET, journal))
    assert backend.calls == 0


def test_remove_is_rejected_before_validation_or_run_creation(tmp_path, monkeypatch):
    compiled = run.compile_fsgen(SOURCE.read_text(), TARGET)
    next(f for f in compiled.features if f.kind == 'extrude').parameters['operationType'] = 'REMOVE'
    monkeypatch.setattr(run, 'compile_fsgen', lambda text, target: compiled)
    def unexpected_validation(text):
        pytest.fail('unsupported REMOVE must be rejected before local validation')
    monkeypatch.setattr(run, 'validate_fsgen', unexpected_validation)
    journal = Journal(tmp_path / 'journal.sqlite')
    try:
        with pytest.raises(Unsupported, match='only NEW'):
            run.initialize_run(tmp_path / 'run.json', SOURCE, TARGET, journal)
        assert not (tmp_path / 'run.json').exists()
    finally:
        journal.close()

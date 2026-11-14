"""Offline coordinator lifecycle tests; actual geometry and writers have separate suites."""
import asyncio
import copy
import json
from pathlib import Path

import pytest

from h2cad import source_run as run
from h2cad.backend import Unsupported, UncertainWrite
from h2cad.journal import Journal
from h2cad.fsgen import FsgenCompileError
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


def test_new_run_cannot_duplicate_an_existing_observed_source(setup):
    path, journal, backend = setup
    sync(run.next_action(path, backend, SOURCE, TARGET, journal))
    backend.allocate()
    sync(run.apply_staged(path, backend, SOURCE, TARGET, journal))
    other = path.with_name('duplicate.json')
    with pytest.raises(Unsupported, match='already exist'):
        run.initialize_run(other, SOURCE, TARGET, journal)
    assert not other.exists()
    assert backend.calls == 1


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


def test_unproven_remove_is_rejected_before_validation_or_run_creation(tmp_path, monkeypatch):
    compiled = run.compile_fsgen(SOURCE.read_text(), TARGET)
    next(f for f in compiled.features if f.kind == 'extrude').parameters['operationType'] = 'REMOVE'
    monkeypatch.setattr(run, 'compile_fsgen', lambda text, target: compiled)
    def unexpected_validation(text):
        pytest.fail('unsupported REMOVE must be rejected before local validation')
    monkeypatch.setattr(run, 'validate_fsgen', unexpected_validation)
    journal = Journal(tmp_path / 'journal.sqlite')
    try:
        with pytest.raises(Unsupported, match='source and semantic projection differ'):
            run.initialize_run(tmp_path / 'run.json', SOURCE, TARGET, journal)
        assert not (tmp_path / 'run.json').exists()
    finally:
        journal.close()


@pytest.mark.parametrize("source_name",["car","carrier"])
def test_all_features_dispatch_in_order_with_observed_dependencies(setup, monkeypatch, source_name):
    path, journal, backend = setup
    source=SOURCE
    if source_name=="carrier":
        from h2cad.validation import validate_fsgen
        monkeypatch.setattr(run,"validate_fsgen",validate_fsgen)
        source=SOURCE.parents[2]/"artifacts/robot/bearing_carrier_scope_fixture.fs"
        path=path.with_name("carrier-run.json")
        run.initialize_run(path,source,TARGET,journal)
        assert json.loads(path.read_text())["local_validation"]["geometry"]["parts"]==2
    plan = run._plan(source.read_text(), TARGET)
    observed = {}
    calls = []

    async def complete(kind, target, source, **kw):
        feature = plan[len(calls)]
        assert target == TARGET and kw['journal'] is journal
        assert feature['kind'] == kind and kw['logical_id'] == feature['logical_id']
        stage = feature['stage']
        previous = [observed[f['logical_id']] for f in plan[:len(calls)] if f['kind'] == kind]
        if kind in ('assignVariable', 'cPlane'):
            assert kw['previous_op_ids'] == previous
        if kind != 'assignVariable':
            assert kw['baseline']['editingFeatureId'] is None
            assert len(kw['baseline']['tree']['children']) == len(calls)
        if kind == 'cPlane':
            assert kw['variable_op_ids'] == {name: observed[name] for name in stage['dependencies']}
            assert kw['reference_binding']['query_data']['featureId'] == stage['reference_plane']
        elif kind == 'newSketch':
            assert kw['plane_op_id'] == observed[stage['plane_logical_id']]
            assert kw['variable_op_ids'] == {
                name: observed[name] for name in stage['source_stage']['source_variable_definitions']}
        elif kind == 'extrude':
            assert kw['sketch_op_id'] == observed[stage['sketch_logical_id']]
            assert kw['variable_op_id'] == (observed[stage['depth_expression']] if stage['variable'] else None)
            assert kw.get('target_body_op_id') == (observed[stage['target_body_logical_id']] if stage['operation_type']=='REMOVE' else None)
        before = copy.deepcopy(backend.state)
        node = backend.state['tree']['children'][-1]
        node['name'] = feature['logical_id']
        backend.state.update(editingFeatureId=None, element_microversion=f'{2*len(calls)+3:024x}')
        op_id = f'op-{len(calls)}'
        intent = {'before_state': before, 'expected_tree': copy.deepcopy(backend.state['tree']),
                  'source_feature': feature['source_feature']}
        if kind=='extrude' and stage['operation_type']=='REMOVE':
            intent['target_body_op_id']=kw['target_body_op_id']
        if kind in ('assignVariable', 'cPlane'):
            intent['source_stages'] = [f['stage'] for f in plan if f['kind'] == kind]
            intent['source_index'] = len(previous)
        journal.prepare(op_id=op_id, target='/'.join(TARGET.to_dict().values()),
            expected_revision=before['element_microversion'], action=run._ACTIONS[kind],
            logical_id=feature['logical_id'], intent=intent)
        journal.transition(op_id, 'sent')
        journal.transition(op_id, 'observed', observation={
            'definition_observed': True, 'feature_id': node['featureId'], 'node_id': node['nodeId'],
            'saved_feature': copy.deepcopy(node), 'constraint_graph_verified': True, 'origin_verified': True})
        observed[feature['logical_id']] = op_id
        calls.append(feature['logical_id'])

    async def variable(target, source, **kw): await complete('assignVariable', target, source, **kw)
    async def plane(owner, target, source, **kw): await complete('cPlane', target, source, **kw)
    async def sketch(owner, target, source, **kw): await complete('newSketch', target, source, **kw)
    async def extrude(owner, target, source, **kw): await complete('extrude', target, source, **kw)
    backend.populate_test_variable = variable
    monkeypatch.setattr(run, 'populate_test_plane', plane)
    monkeypatch.setattr(run, 'populate_source_sketch', sketch)
    monkeypatch.setattr(run, 'populate_source_extrusion', extrude)
    class Bridge:
        health_state={"extension_connected":True,"capabilities":["h2_source_remove_server_v1"],
                      "extension":{"capabilities":["h2_source_remove_page_v1"]}}
        async def health(self):return copy.deepcopy(self.health_state)
        async def command(self, job):
            assert job['kind'] == 'native' and job['command'] == 'ui.GBTUiGetQueryDataCall'
            return {'result': {'$type': 'ui.GBTUiGetQueryDataResponse',
                    'queryData': [{'featureId': plan[len(calls)]['stage']['reference_plane']}]}}
    backend.bridge = Bridge()
    for index, feature in enumerate(plan):
        if feature['kind']=='extrude' and feature['stage']['operation_type']=='REMOVE':
            good=copy.deepcopy(backend.bridge.health_state)
            for bad in ({**good,'capabilities':[]},{**good,'extension':{'capabilities':[]}},
                        {**good,'extension_connected':False}):
                backend.bridge.health_state=bad
                saved=path.read_bytes()
                with pytest.raises(Unsupported,match='before browser allocation'):
                    sync(run.next_action(path,backend,source,TARGET,journal))
                assert path.read_bytes()==saved and backend.state['editingFeatureId'] is None
                assert len(calls)==index
            backend.bridge.health_state=good
        action = sync(run.next_action(path, backend, source, TARGET, journal))
        if feature['kind']=='extrude' and feature['stage']['operation_type']=='REMOVE':
            assert action['defaults']=={'operationType':'REMOVE','bodyType':'SOLID','endBound':'BLIND',
                'selection':'whole_sketch','defaultScope':False,'oppositeDirection':False}
            assert action['target_body_reference']=={'logical_id':'Carrier blank','feature_id':'feature-3',
                'op_id':observed['Carrier blank'],'selection':'one_source_body'}
        assert action['action'] == 'browser_allocate' and action['logical_id'] == feature['logical_id']
        node = {'featureType': feature['kind'], 'featureId': f'feature-{index}', 'nodeId': f'node-{index}'}
        if feature['kind'] == 'cPlane':
            node['parameters'] = [{'parameterId': 'entities', 'queries': [{'deterministicIds': [f'query-{index}']}]}]
        backend.state['tree']['children'].append(node)
        backend.state.update(editingFeatureId=node['featureId'], element_microversion=f'{2*index+2:024x}')
        if feature['kind']=='extrude' and feature['stage']['operation_type']=='REMOVE':
            backend.bridge.health_state={}
            with pytest.raises(Unsupported,match='capability'):
                sync(run.apply_staged(path,backend,source,TARGET,journal))
            assert len(calls)==index
            backend.bridge.health_state=good
        assert sync(run.apply_staged(path, backend, source, TARGET, journal))['op_id'] == f'op-{index}'
    assert calls == [f['logical_id'] for f in plan]
    assert sync(run.next_action(path, backend, source, TARGET, journal)) == {
        'action': 'verify_geometry', 'source_features_observed': len(plan), 'geometry_verified': False}
    sync(run.apply_staged(path, backend, source, TARGET, journal))
    assert len(calls) == len(plan)
    if source_name == 'carrier':
        data = json.loads(path.read_text())
        image = path.with_name('measurement.png')
        # Recorder hashes evidence bytes; it deliberately does not interpret pixels.
        image.write_bytes(b'\x89PNG\r\n\x1a\nfixture')
        evidence = dict(target=TARGET.to_dict(), source_sha256=data['source_sha256'],
                        revision=backend.state['element_microversion'], method='browser_mass_properties',
                        parts=2, volume_mm3=45265.304, area_mm2=18677.987, screenshots=[image.name])
        evidence_path = path.with_name('measurements.json')
        for key, value in [('revision','0'*24), ('source_sha256','wrong'), ('target',{}),
                           ('method','invented'), ('parts',True), ('parts',3),
                           ('volume_mm3',float('nan')), ('area_mm2',float('inf')),
                           ('volume_mm3',45200), ('screenshots',[])]:
            evidence_path.write_text(json.dumps({**evidence,key:value}))
            with pytest.raises(Unsupported):
                sync(run.record_measurements(path,backend,source,TARGET,journal,evidence_path))
            assert 'geometry_measurements' not in json.loads(path.read_text())
        evidence_path.write_text(json.dumps(evidence))
        backend.state['editingFeatureId']='draft'
        with pytest.raises(Unsupported,match='saved idle'):
            sync(run.record_measurements(path,backend,source,TARGET,journal,evidence_path))
        backend.state['editingFeatureId']=None
        result=sync(run.record_measurements(path,backend,source,TARGET,journal,evidence_path))
        assert result['geometry_comparison']['status']=='match'
        assert result['geometry_verified'] is False
        assert result['geometry_comparison']['independently_acquired'] is False
        assert sync(run.next_action(path,backend,source,TARGET,journal))['geometry_comparison']['status']=='match'
        backend.state['element_microversion']='e'*24
        assert sync(run.next_action(path,backend,source,TARGET,journal))['geometry_comparison']['status']=='stale'
        image.write_bytes(b'changed')
        assert sync(run.next_action(path,backend,source,TARGET,journal))['geometry_comparison']['status']=='evidence_changed'
        image.unlink()
        assert sync(run.next_action(path,backend,source,TARGET,journal))['geometry_comparison']['status']=='evidence_unavailable'
        assert len(calls)==len(plan)


@pytest.mark.parametrize("fault",["add","missing_body","multi_body"])
def test_unsupported_remove_plan_fails_before_local_build(tmp_path,monkeypatch,fault):
    source=SOURCE.parents[1]/"native/carrier_remove_scope_sample.fs"
    text=source.read_text()
    if fault=="add":text=text.replace("NewBodyOperationType.REMOVE","NewBodyOperationType.ADD")
    if fault=="missing_body":text=text.replace('qCreatedBy(id + "Carrier blank", EntityType.BODY)','qCreatedBy(id + "Missing", EntityType.BODY)')
    if fault=="multi_body":
        start=text.index('    skRectangle(outline,');end=text.index('    skSolve(outline);',start)
        text=text[:start]+'''    skCircle(outline,"a",{"center":vector(10,5)*millimeter,"radius":3*millimeter});
    skCircle(outline,"b",{"center":vector(-10,5)*millimeter,"radius":3*millimeter});
'''+text[end:]
    monkeypatch.setattr(run,"validate_fsgen",lambda text:pytest.fail("unsupported plan reached local validation"))
    journal=Journal(tmp_path/"journal.sqlite")
    try:
        with pytest.raises((Unsupported,FsgenCompileError)):run.initialize_run(tmp_path/"run.json",text,TARGET,journal)
        assert not (tmp_path/"run.json").exists()
    finally:journal.close()

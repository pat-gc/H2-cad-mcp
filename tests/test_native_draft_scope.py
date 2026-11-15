import copy
import json
from pathlib import Path

import pytest
from h2cad.backend import Unsupported, UncertainWrite
from h2cad.native_draft_scope import inspect_draft_body_scope
from test_native_body_scope import scenario

FIXTURE=Path(__file__).parent/'fixtures/native_draft_scope.json'


async def setup(tmp_path, fault=None):
    path,backend,source,target,journal,calls=scenario(tmp_path)
    f=json.loads(FIXTURE.read_text());baseline=f['baseline'];draft=f['draft']
    backend.tab_id=baseline['tab_id']
    for index,node in enumerate(baseline['tree']['children'][:-1]):
        row=journal._db.execute('SELECT intent,observation FROM writes WHERE op_id=?',(f'op-{index}',)).fetchone()
        intent,obs=map(json.loads,row)
        intent['expected_tree']={'children':copy.deepcopy(baseline['tree']['children'][:index+1])}
        obs.update(feature_id=node['featureId'],node_id=node['nodeId'],saved_feature=node)
        journal._db.execute('UPDATE writes SET intent=?,observation=? WHERE op_id=?',
            (json.dumps(intent),json.dumps(obs),f'op-{index}'))
    fresh=next(n for n in draft['tree']['children'] if n.get('featureId')==draft['editingFeatureId'])
    if fault=='suppressed':fresh['suppressed']=True
    if fault=='existing_edit':draft['editingFeatureId']=baseline['tree']['children'][3]['featureId']
    if fault=='baseline_change':draft['tree']['children'][0]['name']='human edit'
    if fault=='nonterminal':draft['tree']['children'].insert(-1,{'featureId':'extra','nodeId':'extra'})
    if fault=='tab':draft['tab_id']+=1
    if fault=='pending':journal.prepare(op_id='pending',target='other',expected_revision='x',action='x',logical_id='x',intent={})
    nreads=0
    async def state(given):
        nonlocal nreads
        nreads+=1
        result=copy.deepcopy(draft)
        if nreads==5 and fault=='revision_race':result['element_microversion']='0'*24
        if nreads==6 and fault=='journal_race':journal._db.execute("UPDATE writes SET state='rejected' WHERE op_id='op-8'")
        return result
    backend.raw_state=state
    nodes=0
    async def command(job):
        nonlocal nodes
        calls.append(copy.deepcopy(job))
        assert job['tab_id']==backend.tab_id and job['target']==target.to_dict()
        if job['kind']=='schema':
            name=job['name']
            if name=='ui.document.GBTUiQueryInsertables':defaults={'targetElementId':'','sourceElementId':'','documentMicroversionId':None,'filter':{}}
            elif name=='bsedit.GBTMIndividualQuery':
                nodes+=1
                defaults={'deterministicIds':[],'hasUserCode':False,'nodeId':f'fresh-{nodes}','queryString':'','sourceParseTreeNodes':{}}
            else:
                assert name=='ui.GBTUiGetQueryDataCall'
                defaults={'elementId':'','messageId':'','queries':[],'qFunction':'','additionalArguments':[],'queryNodeIdToInContextNodeId':{}}
            return {'name':name,'defaults':{'$type':name,**defaults}}
        assert job['kind']=='native'
        if job['command']=='ui.document.GBTUiQueryInsertables':
            assert job['body']['documentMicroversionId']=={'$type':'document.GBTMicroversionId','theId':baseline['microversion']}
            response=copy.deepcopy(f['inventory_response'])
            if fault=='wrong_historical_element':response['result']['contents'][0]['element']['microversion']['theId']=draft['element_microversion']
            return response
        assert job['command']=='ui.GBTUiGetQueryDataCall'
        ident=job['body']['queries'][0]['deterministicIds'][0]
        response=copy.deepcopy(next(r['response'] for r in f['reads'] if r['body_id']==ident))
        row=response['result']['queryData'][0]
        if fault=='missing_body':response['result']['queryData']=[]
        if fault=='foreign_operation':row['evaluationDetails']['fullOperationId']='foreign.boolean.opBoolean'
        if fault=='foreign_creator':row['featureId']='foreign'
        return response
    backend.bridge.command=command
    return path,backend,source,target,journal,baseline,calls


@pytest.mark.asyncio
async def test_actual_saved_split_bodies_resolve_during_fresh_preview_without_writes(tmp_path):
    path,backend,source,target,journal,baseline,calls=await setup(tmp_path)
    initial=path.read_bytes();changes=journal._db.total_changes
    try:
        proof=await inspect_draft_body_scope(path,backend,source,target,journal,'Carrier blank',baseline)
        assert proof['scope_body_ids']==['JQD','JQH']
        assert proof['body_partitions']['Untouched witness']==['JMD']
        assert not proof['single_survivor'] and proof['independently_verified']
        assert not proof['write_ready'] and not proof['ui_scope_selection_verified']
        assert proof['selected_scope_requirement']=={'match':'exact_set','body_ids':['JQD','JQH'],'defaultScope':False}
        assert len(proof['raw_provenance']['reads'])==4
        assert all('MassProp' not in c.get('command','') for c in calls)
        assert path.read_bytes()==initial and journal._db.total_changes==changes
    finally:journal.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('fault',['suppressed','existing_edit','baseline_change','nonterminal','tab','pending',
    'revision_race','journal_race','wrong_historical_element','missing_body','foreign_operation','foreign_creator'])
async def test_fail_closed_draft_history_inventory_and_query_faults(tmp_path,fault):
    path,backend,source,target,journal,baseline,calls=await setup(tmp_path,fault)
    try:
        with pytest.raises((Unsupported,UncertainWrite)):
            await inspect_draft_body_scope(path,backend,source,target,journal,'Carrier blank',baseline)
    finally:journal.close()

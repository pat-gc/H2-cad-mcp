"""Historical snapshot rows and current transport revisions are distinct."""
import json
from pathlib import Path

import pytest

from h2cad.backend import Unsupported
from h2cad.model import Target
from h2cad.native_body_sets import (
    inspect_historical_server_body_inventory,
    inspect_server_body_inventory,
)


def sample(active=False):
    name = 'historical_body_inventory_active' if active else 'historical_body_inventory'
    fixture = json.loads((Path(__file__).parent / 'fixtures' / (name + '.json')).read_text())
    args = {k: fixture[k] for k in ('historical_document_revision',
        'historical_element_revision', 'current_document_revision', 'request', 'response')}
    args['target'] = Target(**fixture['target'])
    return args, fixture


@pytest.mark.parametrize('active', [False, True])
def test_actual_historical_snapshot_does_not_become_current_or_write_authority(active):
    args, fixture = sample(active)
    proof = inspect_historical_server_body_inventory(**args)
    assert proof['body_ids'] == ['JMD', 'JQD', 'JQH']
    assert proof['element_microversion'] == args['historical_element_revision']
    assert proof['historical_document_microversion'] == args['historical_document_revision']
    assert proof['current_document_microversion'] == args['current_document_revision']
    assert 'document_microversion' not in proof
    assert proof['snapshot_mode'] == 'historical'
    assert proof['server_enumeration_verified'] and not proof['write_ready']
    assert not proof['complete']
    if active:
        assert fixture['before_after_unchanged'] and fixture['observed_editing_feature_id']
        assert fixture['observed_active_element_revision'] != proof['element_microversion']


@pytest.mark.parametrize('field', ['historical_document_revision',
    'historical_element_revision', 'current_document_revision'])
def test_each_revision_is_independently_pinned(field):
    args, _ = sample()
    args[field] = '0' * 24
    with pytest.raises(Unsupported):
        inspect_historical_server_body_inventory(**args)


@pytest.mark.parametrize('change', ['null', 'untyped', 'extra_type_field',
    'historical_envelope', 'changed_after', 'stale_child', 'active_element'])
def test_wrong_snapshot_or_transport_contract_rejected(change):
    args, fixture = sample(change != 'historical_envelope')
    if change == 'null': args['request']['documentMicroversionId'] = None
    elif change == 'untyped': args['request']['documentMicroversionId'] = args['historical_document_revision']
    elif change == 'extra_type_field': args['request']['documentMicroversionId']['extra'] = True
    elif change == 'historical_envelope':
        args['response']['microversion_before'] = args['historical_document_revision']
        args['response']['microversion_after'] = args['historical_document_revision']
    elif change == 'changed_after': args['response']['microversion_after'] = '0' * 24
    elif change == 'stale_child':
        args['response']['result']['contents'][0]['children'][0]['element']['microversion']['theId'] = '0' * 24
    elif change == 'active_element': args['historical_element_revision'] = fixture['observed_active_element_revision']
    with pytest.raises(Unsupported):
        inspect_historical_server_body_inventory(**args)


def test_latest_inspector_still_rejects_explicit_historical_request():
    args, _ = sample()
    with pytest.raises(Unsupported):
        inspect_server_body_inventory(target=args['target'],
            element_revision=args['historical_element_revision'],
            document_revision=args['current_document_revision'],
            request=args['request'], response=args['response'])

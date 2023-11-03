# -*- coding: utf-8 -*-


def test_local(pepper_client, session_minion_id):
    assert pepper_client.local('*', 'test.ping')['return'][0][session_minion_id] is True


def test_local_with_tgt_type(pepper_client, session_minion_id):
    assert session_minion_id not in pepper_client.local('*', 'test.ping', tgt_type='list')['return'][0]
    assert pepper_client.local(session_minion_id, 'test.ping', tgt_type='list')['return'][0][session_minion_id] is True


def test_local_with_deprecated_expr_form(pepper_client, session_minion_id):
    assert session_minion_id not in pepper_client.local('*', 'test.ping', expr_form='list')['return'][0]
    r = pepper_client.local(session_minion_id, 'test.ping', expr_form='list')['return'][0][session_minion_id]
    assert r is True

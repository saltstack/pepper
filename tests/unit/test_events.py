import json
from unittest.mock import MagicMock, patch

import pytest

from pepper.exceptions import PepperException
from pepper.libpepper import Pepper, _parse_event_stream

STREAM = """retry: 400

tag: salt/job/1/new
data: {"tag": "salt/job/1/new", "data": {"jid": "1", "minions": ["m1"]}}

tag: salt/job/1/ret/m1
data: {"tag": "salt/job/1/ret/m1", "data": {"jid": "1", "return": true}}

"""


def test_parse_event_stream():
    assert list(_parse_event_stream(STREAM.splitlines())) == [
        {"tag": "salt/job/1/new", "data": {"jid": "1", "minions": ["m1"]}},
        {"tag": "salt/job/1/ret/m1", "data": {"jid": "1", "return": True}},
    ]


def test_parse_event_stream_without_final_blank_line():
    lines = ["tag: t", 'data: {"tag": "t", "data": {}}']
    assert list(_parse_event_stream(lines)) == [{"tag": "t", "data": {}}]


def test_events_closes_stream():
    resp = MagicMock()
    resp.iter_lines.return_value = iter(STREAM.encode().splitlines())
    with patch.object(Pepper, "req_stream", return_value=resp) as req_stream:
        events = Pepper().events()
        first = next(events)
        events.close()
    req_stream.assert_called_once_with("/events")
    resp.iter_lines.assert_called_once_with()
    resp.close.assert_called_once()
    assert first["tag"] == "salt/job/1/new"
    assert json.dumps(first)


def test_events_decode_utf8():
    # Salt dumps events without escaping non-ASCII characters, including line
    # separators that str.splitlines() would break the line at
    data = {
        "tag": "t",
        "data": {"text": "caf\u00e9 \u00c5ngstr\u00f6m a\u2028b\u0085c"},
    }
    body = f"tag: t\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode()
    resp = MagicMock()
    resp.iter_lines.return_value = iter(body.splitlines())
    with patch.object(Pepper, "req_stream", return_value=resp):
        assert list(Pepper().events()) == [data]


def test_invalid_event():
    with pytest.raises(PepperException, match="Unable to parse event"):
        list(_parse_event_stream(["data: {not json", ""]))

import json
import sys
from unittest.mock import MagicMock, patch

import pytest

import pepper.script

LOCAL = {
    "return": [
        {
            "m1": {"jid": "1", "ret": {"key": "value"}, "retcode": 0},
            "m2": {"jid": "1", "ret": [1, 2], "retcode": 0},
        }
    ]
}

RUNNER = {
    "return": [
        {
            "tag": "salt/run/1/ret",
            "data": {"fun": "runner.test.arg", "return": {"args": ["one"]}},
        }
    ]
}


def _run(capsys, monkeypatch, *args, payload=None, has_salt=False):
    monkeypatch.setattr(pepper.script, "HAS_SALT", has_salt)
    sys.argv = ["pepper", *args]
    low = MagicMock(return_value=LOCAL if payload is None else payload)
    with (
        patch("pepper.cli.PepperCli.login", MagicMock()),
        patch("pepper.cli.PepperCli.low", low),
    ):
        exit_code = pepper.script.Pepper()()
    out, err = capsys.readouterr()
    return exit_code, out, err, low


def _documents(text):
    decoder = json.JSONDecoder()
    docs, index = [], 0
    while index < len(text):
        doc, index = decoder.raw_decode(text, index)
        docs.append(doc)
        while index < len(text) and text[index].isspace():
            index += 1
    return docs


def test_json(capsys, monkeypatch):
    _, out, _, _ = _run(capsys, monkeypatch, "--out=json", "*", "test.ping")
    assert _documents(out) == [{"m1": {"key": "value"}}, {"m2": [1, 2]}]


def test_json_runner(capsys, monkeypatch):
    _, out, _, _ = _run(
        capsys,
        monkeypatch,
        "--out=json",
        "--client=runner",
        "test.arg",
        payload=RUNNER,
    )
    assert _documents(out) == [{"args": ["one"]}]


def test_yaml(capsys, monkeypatch):
    pytest.importorskip("yaml")
    _, out, _, _ = _run(capsys, monkeypatch, "--out=yaml", "*", "test.ping")
    assert out == "m1:\n  key: value\nm2:\n- 1\n- 2\n"


def test_output_file(capsys, monkeypatch, tmp_path):
    path = tmp_path / "out"
    _, out, _, _ = _run(
        capsys, monkeypatch, "--out=json", f"--output-file={path}", "*", "test.ping"
    )
    assert out == ""
    assert _documents(path.read_text()) == [{"m1": {"key": "value"}}, {"m2": [1, 2]}]


def test_unavailable_outputter(capsys, monkeypatch):
    exit_code, _, err, low = _run(capsys, monkeypatch, "--out=nested", "*", "test.ping")
    assert exit_code == 1
    assert "--out=nested needs salt installed" in err
    low.assert_not_called()


UNICODE = {
    "return": [
        {
            "m1": {
                "jid": "1",
                "ret": {"name": "caf\u00e9 \u00c5ngstr\u00f6m"},
                "retcode": 0,
            }
        }
    ]
}


EMOJI = {"return": [{"m1": {"jid": "1", "ret": "hi \U0001F600", "retcode": 0}}]}

SCALAR_RUNNER = {
    "return": [
        {
            "tag": "salt/run/1/ret",
            "data": {"fun": "runner.test.echo", "return": "text"},
        }
    ]
}


@pytest.mark.parametrize(
    "payload,client",
    [
        (LOCAL, "local"),
        (UNICODE, "local"),
        (EMOJI, "local"),
        (SCALAR_RUNNER, "runner"),
    ],
    ids=["ascii", "unicode", "emoji", "scalar-runner"],
)
@pytest.mark.parametrize("out", ["json", "yaml"])
def test_same_as_salt(capsys, monkeypatch, out, payload, client):
    pytest.importorskip("salt.output")
    pytest.importorskip("yaml")
    args = [f"--out={out}", f"--client={client}", "*", "test.ping"]
    _, salt_out, _, _ = _run(capsys, monkeypatch, *args, payload=payload, has_salt=True)
    _, fallback_out, _, _ = _run(capsys, monkeypatch, *args, payload=payload)
    assert fallback_out == salt_out

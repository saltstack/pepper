import sys
from unittest.mock import MagicMock, patch

import pytest

import pepper.script
from pepper.retcode import PepperRetcode


def _minions(**retcodes):
    return {
        name: {"jid": "20261105120000000000", "ret": True, "retcode": retcode}
        for name, retcode in retcodes.items()
    }


def _runner(**data):
    return {
        "tag": "salt/run/20261105120000000000/ret",
        "data": {"fun": "runner.state.orchestrate", "success": True, **data},
    }


ORCH_FAILED = _runner(
    **{"return": {"data": {"master": {}}, "outputter": "highstate", "retcode": 1}}
)
ORCH_PASSED = _runner(
    **{"return": {"data": {"master": {}}, "outputter": "highstate", "retcode": 0}}
)

WHEEL_FAILED = {
    "tag": "salt/wheel/20261105120000000000",
    "data": {"fun": "wheel.key.finger", "return": "Error", "success": False},
}
WHEEL_PASSED = {
    "tag": "salt/wheel/20261105120000000000",
    "data": {"fun": "wheel.key.finger", "return": {}, "success": True},
}


@pytest.mark.parametrize(
    "result,expected",
    [
        ([_minions(a=0, b=0)], 0),
        ([_minions(a=0, b=2)], 1),
        ([_minions(a=0), _minions(b=3)], 1),
        ([_minions(a={"state1": 0, "state2": 2})], 1),
        ([ORCH_PASSED], 0),
        ([ORCH_FAILED], 1),
        ([_runner(**{"return": "Exception occurred", "retcode": 1})], 1),
        ([_runner(**{"return": {"retcode": 5}})], 5),
        ([_runner(**{"return": {"data": {"retcode": 6}}})], 6),
        ([_runner(**{"return": ["foo", "bar"]})], 0),
        ([{"minion": "no full_return"}], 0),
        ([{"a": {"ret": True, "retcode": 0}, "b": False}], 1),
        ([{"a": False}], 1),
        ([WHEEL_FAILED], 1),
        ([WHEEL_PASSED], 0),
        ([], 0),
        ("not a list", 0),
    ],
)
def test_validate_salt(result, expected):
    assert PepperRetcode.validate_salt(result) == expected


def test_fail_any_sees_every_chunk():
    assert PepperRetcode.validate_fail_any([_minions(a=0), _minions(b=3)]) == 3


def test_fail_any_sees_runner_retcode():
    assert PepperRetcode.validate_fail_any([ORCH_FAILED]) == 1


def test_fail_all_with_runner():
    assert PepperRetcode.validate_fail_all([ORCH_FAILED, _minions(a=2)]) == 1
    assert PepperRetcode.validate_fail_all([ORCH_FAILED, _minions(a=0)]) == 0


@pytest.mark.parametrize(
    "result,expected,warned",
    [
        ([_minions(a=0, b=2)], 1, True),
        ([_minions(a=0, b=0)], 0, False),
        ([ORCH_FAILED], 1, False),
    ],
)
def test_exit_code_and_warning(capsys, result, expected, warned):
    sys.argv = ["pepper", "minion_id", "request"]
    with (
        patch("pepper.cli.PepperCli.login", MagicMock()),
        patch("pepper.cli.PepperCli.low", MagicMock(return_value={"return": result})),
    ):
        assert pepper.script.Pepper()() == expected
    err = capsys.readouterr().err
    assert ("Minions returned with non-zero exit code" in err) is warned


def test_fail_option_suppresses_warning(capsys):
    sys.argv = ["pepper", "--fail-all", "minion_id", "request"]
    with (
        patch("pepper.cli.PepperCli.login", MagicMock()),
        patch(
            "pepper.cli.PepperCli.low",
            MagicMock(return_value={"return": [_minions(a=0, b=2)]}),
        ),
    ):
        assert pepper.script.Pepper()() == 0
    assert "Minions returned" not in capsys.readouterr().err


def _exit(capsys, result, *args):
    sys.argv = ["pepper", *args, "nomatch", "test.ping"]
    with (
        patch("pepper.cli.PepperCli.login", MagicMock()),
        patch("pepper.cli.PepperCli.low", MagicMock(return_value={"return": result})),
    ):
        exit_code = pepper.script.Pepper()()
    return exit_code, capsys.readouterr().err


@pytest.mark.parametrize("args", [[], ["--client=local_async"]], ids=["local", "async"])
def test_no_minions_matched(capsys, args):
    # salt-api 3007 and 3008 answer a target that matches nothing with {}
    exit_code, err = _exit(capsys, [{}], *args)
    assert exit_code == 2
    assert "No minions matched the target. No command was sent" in err


def test_no_minions_matched_with_fail_option(capsys):
    # The --fail-* options keep their own rules
    exit_code, err = _exit(capsys, [{}], "--fail-any")
    assert exit_code == 0
    assert "No minions matched" not in err


@pytest.mark.parametrize(
    "result", [[{"a": False}], [], [{}, {"a": {"ret": True, "retcode": 0}}]]
)
def test_not_no_minions_matched(result):
    assert not PepperRetcode.no_minions_matched(result)

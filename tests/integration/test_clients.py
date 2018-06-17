# -*- coding: utf-8 -*-
import pytest


def test_bad_opts(pepper_cli):
    with pytest.raises(SystemExit):
        pepper_cli('*')
    with pytest.raises(SystemExit):
        pepper_cli('test.ping')

import json

import pytest

from hochschulstart_cli.errors import CliError
from hochschulstart_cli.json_util import dumps, parse_json_object


def test_dumps_rejects_nan():
    with pytest.raises(ValueError):
        dumps({"v": float("nan")})


def test_parse_json_object_rejects_null():
    with pytest.raises(CliError):
        parse_json_object("null")


def test_parse_json_object_ok():
    assert parse_json_object('{"a": 1}') == {"a": 1}

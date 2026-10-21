import math

import pytest

from hochschulstart_cli import exit_codes as ec
from hochschulstart_cli.errors import CliError
from hochschulstart_cli.validation import (
    parse_date,
    reject_nan_in_json_tree,
    require_application_id,
    require_positive_int,
)


def test_application_id_rejects_empty_and_path_segments():
    with pytest.raises(CliError) as e:
        require_application_id("")
    assert e.value.code == ec.INPUT
    with pytest.raises(CliError) as e:
        require_application_id("../B-1002")
    assert e.value.code == ec.INPUT
    assert require_application_id("B-1001") == "B-1001"


def test_positive_int_rejects_zero_and_negative():
    with pytest.raises(CliError) as e:
        require_positive_int(0)
    assert e.value.code == ec.INPUT
    with pytest.raises(CliError):
        require_positive_int(-3)


def test_parse_date_invalid():
    with pytest.raises(CliError) as e:
        parse_date("not-a-date")
    assert e.value.code == ec.INPUT


def test_reject_nan_in_tree():
    with pytest.raises(CliError):
        reject_nan_in_json_tree({"x": float("nan")})
    with pytest.raises(CliError):
        reject_nan_in_json_tree([float("inf")])
    reject_nan_in_json_tree({"x": 1.0, "y": [2, 3]})

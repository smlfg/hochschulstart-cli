import json

from hochschulstart_cli import exit_codes as ec
from hochschulstart_cli.errors import CliError, run_main


def test_run_main_cli_error_code():
    def fail(_argv):
        raise CliError("nope", code=ec.AUTH)

    assert run_main(fail, []) == ec.AUTH


def test_run_main_json_single_object(capsys):
    def fail(_argv):
        raise CliError("bad input", code=ec.INPUT)

    code = run_main(fail, ["--json"])
    assert code == ec.INPUT
    out = capsys.readouterr().out.strip()
    assert len(out.splitlines()) == 1
    payload = json.loads(out)
    assert payload == {"ok": False, "error": {"code": ec.INPUT, "message": "bad input"}}


def test_run_main_keyboard_interrupt(capsys):
    def boom(_argv):
        raise KeyboardInterrupt

    assert run_main(boom, ["--json"]) == ec.ABORT
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == ec.ABORT

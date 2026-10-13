from hochschulstart_cli import exit_codes as ec


def test_documented_codes():
    assert ec.is_documented(ec.OK)
    assert ec.is_documented(ec.ABORT)
    assert not ec.is_documented(99)


def test_argparse_maps_to_input():
    assert ec.map_argparse_exit(2) == ec.INPUT

"""HTTP-Client-Hilfen (offline)."""

from hochschulstart_cli.http_client import maintenance_redirect


def test_maintenance_redirect_wartung_bw_host():
    assert maintenance_redirect(
        "https://dosv.hochschulstart.de/bewerber",
        "https://wartung-bw.hochschulstart.de/",
    )


def test_maintenance_redirect_same_url_is_false():
    assert not maintenance_redirect(
        "https://dosv.hochschulstart.de/bewerber",
        "https://dosv.hochschulstart.de/bewerber",
    )


def test_maintenance_redirect_unrelated_host_is_false():
    assert not maintenance_redirect(
        "https://dosv.hochschulstart.de/bewerber",
        "https://www.hochschulstart.de/bewerben-beobachten/termine",
    )

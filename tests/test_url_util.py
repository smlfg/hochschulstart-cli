from hochschulstart_cli.url_util import join_preserve_base_path


def test_preserves_api_prefix():
    assert (
        join_preserve_base_path("https://api.example.com/v1", "users")
        == "https://api.example.com/v1/users"
    )


def test_trailing_slash_base():
    assert join_preserve_base_path("https://api.example.com/v1/", "users") == (
        "https://api.example.com/v1/users"
    )

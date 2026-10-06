import pytest

from app.core.ssrf import UnsafeUrlError, assert_public_http_url


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8000/api/v1/admin",
        "http://localhost/",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/spec.json",
        "http://192.168.1.10/spec.json",
        "http://[::1]/spec.json",
        "http://0.0.0.0/",
    ],
)
def test_rejects_internal_addresses(url: str) -> None:
    with pytest.raises(UnsafeUrlError):
        assert_public_http_url(url)


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://8.8.8.8/x", "gopher://8.8.8.8/"])
def test_rejects_non_http_schemes(url: str) -> None:
    with pytest.raises(UnsafeUrlError):
        assert_public_http_url(url)


def test_accepts_a_public_literal_address() -> None:
    assert_public_http_url("https://8.8.8.8/openapi.json")


def test_rejects_url_with_no_host() -> None:
    with pytest.raises(UnsafeUrlError):
        assert_public_http_url("https:///path-only")

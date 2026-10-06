import pytest

from app.core.uploads import sniff_image


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (b"\x89PNG\r\n\x1a\n" + b"\x00" * 16, ("image/png", "png")),
        (b"\xff\xd8\xff\xe0" + b"\x00" * 16, ("image/jpeg", "jpg")),
        (b"GIF89a" + b"\x00" * 16, ("image/gif", "gif")),
        (b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 8, ("image/webp", "webp")),
    ],
)
def test_recognises_supported_image_signatures(raw: bytes, expected: tuple[str, str]) -> None:
    assert sniff_image(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        b"<script>alert(1)</script>",
        b"",
        b"RIFF\x00\x00\x00\x00WAVEfmt ",
        b"\x89PNG-but-not-really",
    ],
)
def test_rejects_everything_else(raw: bytes) -> None:
    assert sniff_image(raw) is None

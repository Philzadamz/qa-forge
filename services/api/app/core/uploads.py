"""Content sniffing for user uploads (PRD §12 "upload type sniffing").

Decides the file type from its leading bytes rather than the client-declared Content-Type or the
filename, both of which the client controls.
"""

_SIGNATURES: tuple[tuple[bytes, str, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "image/png", "png"),
    (b"\xff\xd8\xff", "image/jpeg", "jpg"),
    (b"GIF87a", "image/gif", "gif"),
    (b"GIF89a", "image/gif", "gif"),
)


def sniff_image(raw: bytes) -> tuple[str, str] | None:
    """Returns (content_type, extension) for PNG/JPEG/GIF/WebP bytes, else None."""
    for magic, content_type, extension in _SIGNATURES:
        if raw.startswith(magic):
            return content_type, extension
    if len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "image/webp", "webp"
    return None

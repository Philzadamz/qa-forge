"""Renders a masked request/response log to a monospace-font PNG (PRD §7.6.2 step 5), so it
can sit on the xlsx evidence sheet like a screenshot. Pillow is already a project dependency
(docengine's image handling)."""

from PIL import Image, ImageDraw, ImageFont

_FONT_SIZE = 13
_LINE_HEIGHT = 17
_PADDING = 10
_MAX_LINE_CHARS = 110
_MAX_LINES = 120


def _wrapped_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in text.splitlines() or [""]:
        if not raw_line:
            lines.append("")
            continue
        for i in range(0, len(raw_line), _MAX_LINE_CHARS):
            lines.append(raw_line[i : i + _MAX_LINE_CHARS])
    return lines[:_MAX_LINES]


def render_text_to_png(text: str) -> bytes:
    import io

    lines = _wrapped_lines(text)
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont
    try:
        font = ImageFont.truetype("Courier New.ttf", _FONT_SIZE)
    except OSError:
        font = ImageFont.load_default()

    width = _PADDING * 2 + _MAX_LINE_CHARS * 8
    height = _PADDING * 2 + max(len(lines), 1) * _LINE_HEIGHT
    image = Image.new("RGB", (width, height), color="#1e1e1e")
    draw = ImageDraw.Draw(image)
    for i, line in enumerate(lines):
        draw.text((_PADDING, _PADDING + i * _LINE_HEIGHT), line, font=font, fill="#d4d4d4")

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()

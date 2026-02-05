import base64
import os
from pathlib import Path
from typing import Any


def _mime_from_extension(path: str) -> str | None:
    ext = Path(path).suffix.lower().lstrip(".")
    if ext == "png":
        return "image/png"
    if ext in ("jpg", "jpeg"):
        return "image/jpeg"
    if ext == "svg":
        return "image/svg+xml"
    return None


def _mime_from_bytes(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8"):
        return "image/jpeg"
    head = data[:512].lstrip()
    if head.startswith(b"<"):
        lowered = head.lower()
        if b"<svg" in lowered:
            return "image/svg+xml"
    return None


def _data_url_from_bytes(data: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(data).decode('utf-8')}"


def image_data_url_from_sources(logo_data: Any = None, logo_path: str | None = None) -> str:
    s = (str(logo_data).strip() if logo_data is not None else "").strip()
    if s:
        if s.startswith("data:image"):
            return s
        if s.lstrip().lower().startswith("<svg") or "<svg" in s[:512].lower():
            return _data_url_from_bytes(s.encode("utf-8"), "image/svg+xml")
        try:
            decoded = base64.b64decode(s, validate=False)
            mime = _mime_from_bytes(decoded)
            if mime:
                return _data_url_from_bytes(decoded, mime)
        except Exception:
            pass

    if logo_path:
        try:
            p = str(logo_path).strip()
            if not p or not os.path.exists(p):
                return ""
            with open(p, "rb") as f:
                data = f.read()
            mime = _mime_from_extension(p) or _mime_from_bytes(data)
            if not mime:
                return ""
            return _data_url_from_bytes(data, mime)
        except Exception:
            return ""

    return ""


def print_logo_png_data_url(
    logo_data: Any = None,
    logo_path: str | None = None,
    max_width_px: int = 120,
    max_height_px: int = 40,
) -> str:
    data_url = image_data_url_from_sources(logo_data, logo_path)
    if not data_url or not data_url.startswith("data:") or "," not in data_url:
        return ""

    try:
        meta, payload = data_url.split(",", 1)
        mime = meta[5:].split(";", 1)[0].strip().lower()
        if mime != "image/svg+xml":
            return data_url

        raw = base64.b64decode(payload, validate=False)
        scale = 4
        png = rasterize_svg_to_png_bytes(
            raw, max(1, int(max_width_px)) * scale, max(1, int(max_height_px)) * scale
        )
        if not png:
            return ""
        return _data_url_from_bytes(png, "image/png")
    except Exception:
        return ""


def rasterize_svg_to_png_bytes(svg_bytes: bytes, width_px: int, height_px: int) -> bytes | None:
    try:
        from PyQt6.QtCore import QBuffer, QByteArray, QIODevice
        from PyQt6.QtGui import QImage, QPainter
        from PyQt6.QtSvg import QSvgRenderer
    except Exception:
        return None

    try:
        renderer = QSvgRenderer(QByteArray(svg_bytes))
        if not renderer.isValid():
            return None

        w = max(1, int(width_px))
        h = max(1, int(height_px))
        image = QImage(w, h, QImage.Format.Format_ARGB32)
        image.fill(0)
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()

        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buf, "PNG")
        out = bytes(buf.data())
        buf.close()
        return out
    except Exception:
        return None

from __future__ import annotations


def clamp01(value: float) -> float:
    try:
        v = float(value)
    except Exception:
        return 0.0
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    s = (hex_color or "").strip().lstrip("#")
    if len(s) == 3:
        s = "".join(ch * 2 for ch in s)
    if len(s) != 6:
        return (0, 0, 0)
    try:
        r = int(s[0:2], 16)
        g = int(s[2:4], 16)
        b = int(s[4:6], 16)
        return (r, g, b)
    except Exception:
        return (0, 0, 0)


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    r, g, b = rgb
    r = max(0, min(255, int(r)))
    g = max(0, min(255, int(g)))
    b = max(0, min(255, int(b)))
    return f"#{r:02X}{g:02X}{b:02X}"


def lerp_color_hex(a: str, b: str, t: float) -> str:
    tt = clamp01(t)
    ar, ag, ab = _hex_to_rgb(a)
    br, bg, bb = _hex_to_rgb(b)
    r = round(ar + (br - ar) * tt)
    g = round(ag + (bg - ag) * tt)
    b_ = round(ab + (bb - ab) * tt)
    return _rgb_to_hex((r, g, b_))


def color_for_ratio(ratio_0_to_1: float) -> str:
    return lerp_color_hex("#EF4444", "#10B981", clamp01(ratio_0_to_1))

import os

from core.resource_utils import normalize_windows_path


def test_normalize_windows_path_strips_extended_prefix_on_windows():
    raw_path = r"\\?\D:\blogs\appas\SkyWaveERB\assets\font\Cairo.ttf"
    normalized = normalize_windows_path(raw_path)

    if os.name == "nt":
        assert normalized == r"D:\blogs\appas\SkyWaveERB\assets\font\Cairo.ttf"
    else:
        assert normalized

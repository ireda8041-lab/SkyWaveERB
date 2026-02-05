from __future__ import annotations

from core.color_utils import color_for_ratio


def test_color_for_ratio_endpoints():
    assert color_for_ratio(0.0).upper() == "#EF4444"
    assert color_for_ratio(1.0).upper() == "#10B981"


def test_color_for_ratio_clamps():
    assert color_for_ratio(-10).upper() == "#EF4444"
    assert color_for_ratio(10).upper() == "#10B981"

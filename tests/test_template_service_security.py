import os

import pytest

from services.template_service import TemplateService


def test_sanitize_template_filename_rejects_traversal():
    with pytest.raises(ValueError):
        TemplateService._sanitize_template_filename("../evil")

    with pytest.raises(ValueError):
        TemplateService._sanitize_template_filename("a/b")

    with pytest.raises(ValueError):
        TemplateService._sanitize_template_filename("..")


def test_sanitize_template_filename_produces_html_name():
    assert TemplateService._sanitize_template_filename("فاتورة تجريبية") == "فاتورة_تجريبية.html"


def test_safe_template_path_stays_inside_templates_dir(tmp_path):
    svc = object.__new__(TemplateService)
    svc.templates_dir = str(tmp_path)

    safe = TemplateService._safe_template_path(svc, "ok.html")
    assert os.path.realpath(safe).startswith(os.path.realpath(str(tmp_path)) + os.sep)

    with pytest.raises(ValueError):
        TemplateService._safe_template_path(svc, "../evil.html")

    with pytest.raises(ValueError):
        TemplateService._safe_template_path(svc, "a/b.html")

"""Frontend Integrity and DOM Reference Verification."""

import re
from pathlib import Path


def test_all_app_js_element_ids_exist_in_index_html():
    index_html = Path("frontend/index.html").read_text(encoding="utf-8")
    app_js = Path("frontend/app.js").read_text(encoding="utf-8")

    # Extract all getElementById calls
    id_pattern = re.compile(r'getElementById\s*\(\s*["\']([^"\']+)["\']\s*\)')
    js_ids = set(id_pattern.findall(app_js))

    # Extract all id="..." in index.html
    html_id_pattern = re.compile(r'id\s*=\s*["\']([^"\']+)["\']')
    html_ids = set(html_id_pattern.findall(index_html))

    # Identify any missing IDs
    missing_ids = js_ids - html_ids
    assert len(missing_ids) == 0, f"The following IDs referenced in app.js are missing from index.html: {missing_ids}"


def test_journal_voucher_download_handler():
    app_js = Path("frontend/app.js").read_text(encoding="utf-8")

    assert 'data-draft-act="download"' in app_js
    assert "Blob" in app_js
    assert "createObjectURL" in app_js
    assert "journal_entry.json" in app_js

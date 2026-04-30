import os
import sys
import pytest
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from scheduling_deliver import build_center_html


def _make_result(needs_eng=None, manual_eng=None, good_eng=None,
                 needs_tea=None, manual_tea=None, good_tea=None):
    """Build a minimal result dict with the given rows per center/group."""
    cols = ["Student Name", "Center", "2026-02", "2026-03", "2026-04",
            "Threshold", "ThresholdType", "2026-05", "2026-06", "short_1", "short_2"]

    def rows_to_df(rows):
        if not rows:
            return pd.DataFrame(columns=cols)
        return pd.DataFrame(rows, columns=cols)

    needs_rows = (needs_eng or []) + (needs_tea or [])
    manual_rows = (manual_eng or []) + (manual_tea or [])
    good_rows = (good_eng or []) + (good_tea or [])

    return {
        "needs": rows_to_df(needs_rows),
        "manual": rows_to_df(manual_rows),
        "good": rows_to_df(good_rows),
        "recent_months": ["2026-02", "2026-03", "2026-04"],
        "future_months": ["2026-05", "2026-06"],
        "primary_col": "2026-04",
        "secondary_col": "2026-03",
        "warning_center": None,
    }


ENG_NEEDS_ROW = ["Carol Davis", "Englewood", 4, 7, 5, 8, "inferred", 3, 0, True, True]
ENG_MANUAL_ROW = ["Frank Lee", "Englewood", 1, 2, 3, 4, "manual_check", 1, 2, False, False]
ENG_GOOD_ROW = ["Alice Smith", "Englewood", 5, 7, 8, 8, "confirmed", 8, 8, False, False]


def test_html_contains_center_name():
    result = _make_result(needs_eng=[ENG_NEEDS_ROW])
    html = build_center_html("Englewood", result)
    assert "Englewood" in html


def test_html_contains_needs_section():
    result = _make_result(needs_eng=[ENG_NEEDS_ROW])
    html = build_center_html("Englewood", result)
    assert "Needs Appointments" in html
    assert "Carol Davis" in html


def test_html_contains_manual_section():
    result = _make_result(manual_eng=[ENG_MANUAL_ROW])
    html = build_center_html("Englewood", result)
    assert "Manual Review" in html
    assert "Frank Lee" in html


def test_html_contains_good_section():
    result = _make_result(good_eng=[ENG_GOOD_ROW])
    html = build_center_html("Englewood", result)
    assert "Looks Good" in html
    assert "Alice Smith" in html


def test_html_needs_section_color():
    result = _make_result(needs_eng=[ENG_NEEDS_ROW])
    html = build_center_html("Englewood", result)
    assert "#2E75B6" in html


def test_html_manual_section_color():
    result = _make_result(manual_eng=[ENG_MANUAL_ROW])
    html = build_center_html("Englewood", result)
    assert "#C55A11" in html


def test_html_good_section_color():
    result = _make_result(good_eng=[ENG_GOOD_ROW])
    html = build_center_html("Englewood", result)
    assert "#70AD47" in html


def test_html_red_cell_for_zero_appointments():
    result = _make_result(needs_eng=[ENG_NEEDS_ROW])
    html = build_center_html("Englewood", result)
    # ENG_NEEDS_ROW has Jun=0 → red cell
    assert "#fde8e8" in html


def test_html_yellow_cell_for_partial_appointments():
    result = _make_result(needs_eng=[ENG_NEEDS_ROW])
    html = build_center_html("Englewood", result)
    # ENG_NEEDS_ROW has May=3 (< threshold 8) → yellow cell
    assert "#fef9e7" in html


def test_html_excludes_other_center_students():
    tea_row = ["Bob Jones", "Teaneck", 5, 6, 3, 4, "manual_check", 4, 4, False, False]
    result = _make_result(needs_eng=[ENG_NEEDS_ROW], manual_tea=[tea_row])
    html = build_center_html("Englewood", result)
    assert "Carol Davis" in html
    assert "Bob Jones" not in html


def test_html_skips_empty_section():
    result = _make_result(good_eng=[ENG_GOOD_ROW])
    html = build_center_html("Englewood", result)
    assert "Needs Appointments" not in html
    assert "Manual Review" not in html


def test_html_issue_column_for_needs():
    result = _make_result(needs_eng=[ENG_NEEDS_ROW])
    html = build_center_html("Englewood", result)
    # Carol Davis: May=3 (need 8) | Jun=0 (need 8)
    assert "need 8" in html

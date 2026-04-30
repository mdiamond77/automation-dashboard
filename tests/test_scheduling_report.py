import os
import sys
import pytest
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from scheduling_report import run_scheduling_report


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def workout_plan_file(tmp_path):
    rows = [
        # Alice Smith (Englewood): 8 sessions Apr, 7 Mar, 5 Feb → confirmed threshold 8
        *[{"Student Name": "Alice Smith", "Date": f"04/{d:02d}/2026", "Center": "Englewood"} for d in range(1, 9)],
        *[{"Student Name": "Alice Smith", "Date": f"03/{d:02d}/2026", "Center": "Englewood"} for d in range(1, 8)],
        *[{"Student Name": "Alice Smith", "Date": f"02/{d:02d}/2026", "Center": "Englewood"} for d in range(1, 6)],
        # Bob Jones (Teaneck): 3 sessions Apr → manual_check threshold 4
        *[{"Student Name": "Bob Jones", "Date": f"04/{d:02d}/2026", "Center": "Teaneck"} for d in range(1, 4)],
        *[{"Student Name": "Bob Jones", "Date": f"03/{d:02d}/2026", "Center": "Teaneck"} for d in range(1, 6)],
        # Carol Davis (Englewood): 5 Apr, 7 Mar → inferred threshold 8 (secondary ≥ 6)
        *[{"Student Name": "Carol Davis", "Date": f"04/{d:02d}/2026", "Center": "Englewood"} for d in range(1, 6)],
        *[{"Student Name": "Carol Davis", "Date": f"03/{d:02d}/2026", "Center": "Englewood"} for d in range(1, 8)],
        # Dan Brown (Teaneck): 5 Apr, 4 Mar → inferred threshold 4 (secondary < 6)
        *[{"Student Name": "Dan Brown", "Date": f"04/{d:02d}/2026", "Center": "Teaneck"} for d in range(1, 6)],
        *[{"Student Name": "Dan Brown", "Date": f"03/{d:02d}/2026", "Center": "Teaneck"} for d in range(1, 5)],
        # Eve Wilson (Englewood): only Feb sessions → inactive, must be excluded
        *[{"Student Name": "Eve Wilson", "Date": f"02/{d:02d}/2026", "Center": "Englewood"} for d in range(1, 6)],
        # Frank Lee: "Englewood, Teaneck Virtual" center → must map to Englewood
        {"Student Name": "Frank Lee", "Date": "04/01/2026", "Center": "Englewood, Teaneck Virtual"},
    ]
    df = pd.DataFrame(rows)
    path = tmp_path / "workout_plan.xlsx"
    df.to_excel(path, index=False)
    return path


@pytest.fixture
def appointy_file(tmp_path):
    rows = [
        # Alice: 8 May confirmed + 8 Jun confirmed → looks good (threshold 8)
        *[{"Student Name": "Alice Smith", "Center Name": "Englewood",
           "Appointment Date": f"May {d:02d}, 2026 10:00 AM", "Status": "APPOINTMENT_CONFIRMED"}
          for d in range(1, 9)],
        *[{"Student Name": "Alice Smith", "Center Name": "Englewood",
           "Appointment Date": f"Jun {d:02d}, 2026 10:00 AM", "Status": "APPOINTMENT_CONFIRMED"}
          for d in range(1, 9)],
        # Carol: 3 May confirmed, 0 Jun → needs appointments (threshold 8, short both)
        *[{"Student Name": "Carol Davis", "Center Name": "Englewood",
           "Appointment Date": f"May {d:02d}, 2026 10:00 AM", "Status": "APPOINTMENT_CONFIRMED"}
          for d in range(1, 4)],
        # Bob: 4 May + 4 Jun confirmed → looks good (threshold 4)
        *[{"Student Name": "Bob Jones", "Center Name": "Teaneck",
           "Appointment Date": f"May {d:02d}, 2026 10:00 AM", "Status": "APPOINTMENT_CONFIRMED"}
          for d in range(1, 5)],
        *[{"Student Name": "Bob Jones", "Center Name": "Teaneck",
           "Appointment Date": f"Jun {d:02d}, 2026 10:00 AM", "Status": "APPOINTMENT_CONFIRMED"}
          for d in range(1, 5)],
        # Dan: 2 May confirmed, 0 Jun → needs appointments (threshold 4, short both)
        *[{"Student Name": "Dan Brown", "Center Name": "Teaneck",
           "Appointment Date": f"May {d:02d}, 2026 10:00 AM", "Status": "APPOINTMENT_CONFIRMED"}
          for d in range(1, 3)],
        # Cancelled — must NOT be counted toward Dan's appointments
        {"Student Name": "Dan Brown", "Center Name": "Teaneck",
         "Appointment Date": "May 20, 2026 10:00 AM", "Status": "APPOINTMENT_CANCELLED"},
    ]
    df = pd.DataFrame(rows)
    path = tmp_path / "appointy.csv"
    df.to_csv(path, index=False)
    return path


@pytest.fixture
def result(workout_plan_file, appointy_file):
    return run_scheduling_report(workout_plan_file, appointy_file)


# ── Return shape ──────────────────────────────────────────────────────────────

def test_result_keys(result):
    assert set(result.keys()) >= {"needs", "manual", "good", "recent_months",
                                   "future_months", "primary_col", "secondary_col",
                                   "warning_center"}


def test_recent_months_are_last_three(result):
    assert result["recent_months"] == ["2026-02", "2026-03", "2026-04"]


def test_future_months_are_next_two(result):
    assert result["future_months"] == ["2026-05", "2026-06"]


def test_primary_and_secondary_cols(result):
    assert result["primary_col"] == "2026-04"
    assert result["secondary_col"] == "2026-03"


# ── Center assignment ─────────────────────────────────────────────────────────

def test_englewood_virtual_maps_to_englewood(result):
    all_students = pd.concat([result["needs"], result["manual"], result["good"]])
    frank = all_students[all_students["Student Name"] == "Frank Lee"]
    assert len(frank) == 1
    assert frank.iloc[0]["Center"] == "Englewood"


# ── Active student filter ─────────────────────────────────────────────────────

def test_inactive_student_excluded(result):
    all_students = pd.concat([result["needs"], result["manual"], result["good"]])
    assert "Eve Wilson" not in all_students["Student Name"].values


# ── Threshold classification ──────────────────────────────────────────────────

def test_confirmed_threshold(result):
    all_students = pd.concat([result["needs"], result["manual"], result["good"]])
    alice = all_students[all_students["Student Name"] == "Alice Smith"].iloc[0]
    assert alice["Threshold"] == 8
    assert alice["ThresholdType"] == "confirmed"


def test_manual_check_threshold(result):
    all_students = pd.concat([result["needs"], result["manual"], result["good"]])
    bob = all_students[all_students["Student Name"] == "Bob Jones"].iloc[0]
    assert bob["Threshold"] == 4
    assert bob["ThresholdType"] == "manual_check"


def test_inferred_threshold_8_when_secondary_high(result):
    all_students = pd.concat([result["needs"], result["manual"], result["good"]])
    carol = all_students[all_students["Student Name"] == "Carol Davis"].iloc[0]
    assert carol["Threshold"] == 8
    assert carol["ThresholdType"] == "inferred"


def test_inferred_threshold_4_when_secondary_low(result):
    all_students = pd.concat([result["needs"], result["manual"], result["good"]])
    dan = all_students[all_students["Student Name"] == "Dan Brown"].iloc[0]
    assert dan["Threshold"] == 4
    assert dan["ThresholdType"] == "inferred"


# ── Group assignment ──────────────────────────────────────────────────────────

def test_alice_in_good(result):
    assert "Alice Smith" in result["good"]["Student Name"].values


def test_carol_in_needs(result):
    assert "Carol Davis" in result["needs"]["Student Name"].values


def test_bob_in_manual(result):
    assert "Bob Jones" in result["manual"]["Student Name"].values


def test_dan_in_needs(result):
    assert "Dan Brown" in result["needs"]["Student Name"].values


# ── Appointy filtering ────────────────────────────────────────────────────────

def test_cancelled_appointments_excluded(result):
    all_students = pd.concat([result["needs"], result["manual"], result["good"]])
    dan = all_students[all_students["Student Name"] == "Dan Brown"].iloc[0]
    # Dan has 2 confirmed + 1 cancelled in May. Only 2 should count.
    assert dan["2026-05"] == 2


# ── Warning detection ─────────────────────────────────────────────────────────

def test_no_warning_when_both_centers_present(result):
    assert result["warning_center"] is None


def test_warning_when_one_center_missing(workout_plan_file, tmp_path):
    rows = [
        {"Student Name": "Alice Smith", "Center Name": "Englewood",
         "Appointment Date": "May 01, 2026 10:00 AM", "Status": "APPOINTMENT_CONFIRMED"},
    ]
    df = pd.DataFrame(rows)
    path = tmp_path / "appointy_one_center.csv"
    df.to_csv(path, index=False)
    r = run_scheduling_report(workout_plan_file, path)
    assert r["warning_center"] == "Teaneck"


# ── Sorting ───────────────────────────────────────────────────────────────────

def test_results_sorted_by_center_then_name(result):
    for group in ["needs", "manual", "good"]:
        df = result[group]
        if len(df) > 1:
            pairs = list(zip(df["Center"], df["Student Name"]))
            assert pairs == sorted(pairs)

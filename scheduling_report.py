import pandas as pd


def run_scheduling_report(workout_plan_path, appointy_path) -> dict:
    # ── 1. Load Workout Plan ──────────────────────────────────────────────────
    wp = pd.read_excel(workout_plan_path)
    wp["Date"] = pd.to_datetime(wp["Date"], format="%m/%d/%Y")
    wp["Month"] = wp["Date"].dt.to_period("M")
    wp["Center"] = wp["Center"].apply(
        lambda c: "Englewood" if pd.notna(c) and str(c).startswith("Englewood") else "Teaneck"
    )

    # ── 2. Dynamic month detection ────────────────────────────────────────────
    wp_months = sorted(wp["Month"].unique())
    recent_months = wp_months[-3:]
    primary_month = recent_months[-1]
    secondary_month = recent_months[-2]

    # ── 3. Session counts (row count per student/center/month) ────────────────
    monthly = wp.groupby(["Student Name", "Center", "Month"]).size().unstack(fill_value=0)
    for m in recent_months:
        if m not in monthly.columns:
            monthly[m] = 0
    monthly = monthly[recent_months].reset_index()
    monthly.columns = ["Student Name", "Center"] + [str(m) for m in recent_months]

    primary_col = str(primary_month)
    secondary_col = str(secondary_month)

    # ── 4. Active students: ≥1 session in either of the 2 most recent months ──
    active = monthly[
        (monthly[primary_col] >= 1) | (monthly[secondary_col] >= 1)
    ].copy()

    # ── 5. Threshold classification ───────────────────────────────────────────
    def _classify(row):
        p = row[primary_col]
        s = row[secondary_col]
        if p <= 4:
            return 4, "manual_check"
        elif p >= 6:
            return 8, "confirmed"
        else:  # p == 5
            return (8 if s >= 6 else 4), "inferred"

    active[["Threshold", "ThresholdType"]] = active.apply(
        lambda r: pd.Series(_classify(r)), axis=1
    )

    # ── 6. Load Appointy — confirmed future appointments only ─────────────────
    ap = pd.read_csv(appointy_path)
    ap["Appointment Date"] = pd.to_datetime(
        ap["Appointment Date"], format="%b %d, %Y %I:%M %p"
    )
    ap["Month"] = ap["Appointment Date"].dt.to_period("M")
    ap = ap.rename(columns={"Center Name": "Center"})

    confirmed = ap[ap["Status"] == "APPOINTMENT_CONFIRMED"]
    future_months = sorted(confirmed["Month"].unique())[:2]

    # ── 7. Warning: detect missing center in Appointy ─────────────────────────
    appointy_centers = set(confirmed["Center"].unique())
    expected_centers = {"Englewood", "Teaneck"}
    missing = expected_centers - appointy_centers
    warning_center = missing.pop() if len(missing) == 1 else None

    fc = confirmed.groupby(["Student Name", "Center", "Month"]).size().unstack(fill_value=0)
    for m in future_months:
        if m not in fc.columns:
            fc[m] = 0
    if not future_months:
        future_col_1 = future_col_2 = None
        fc = pd.DataFrame(columns=["Student Name", "Center"])
    elif len(future_months) == 1:
        fc = fc[future_months].reset_index()
        future_col_1 = str(future_months[0])
        future_col_2 = future_col_1
        fc.columns = ["Student Name", "Center", future_col_1]
        fc[future_col_2] = fc[future_col_1]
    else:
        fc = fc[future_months].reset_index()
        future_col_1 = str(future_months[0])
        future_col_2 = str(future_months[1])
        fc.columns = ["Student Name", "Center", future_col_1, future_col_2]

    # ── 8. Merge and flag gaps ────────────────────────────────────────────────
    merged = active.merge(fc, on=["Student Name", "Center"], how="left")
    merged[future_col_1] = merged[future_col_1].fillna(0).astype(int)
    merged[future_col_2] = merged[future_col_2].fillna(0).astype(int)
    merged["short_1"] = merged[future_col_1] < merged["Threshold"]
    merged["short_2"] = merged[future_col_2] < merged["Threshold"]

    # ── 9. Split into three groups ────────────────────────────────────────────
    needs = merged[
        (merged["ThresholdType"].isin(["confirmed", "inferred"])) &
        (merged["short_1"] | merged["short_2"])
    ].copy()

    manual = merged[merged["ThresholdType"] == "manual_check"].copy()

    good = merged[
        (merged["ThresholdType"].isin(["confirmed", "inferred"])) &
        ~(merged["short_1"] | merged["short_2"])
    ].copy()

    for df in [needs, manual, good]:
        df.sort_values(["Center", "Student Name"], inplace=True)

    return {
        "needs": needs,
        "manual": manual,
        "good": good,
        "recent_months": [str(m) for m in recent_months],
        "future_months": [future_col_1, future_col_2],
        "primary_col": primary_col,
        "secondary_col": secondary_col,
        "warning_center": warning_center,
    }

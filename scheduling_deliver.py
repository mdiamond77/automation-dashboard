import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

CENTERS = {
    "Englewood": "englewood@mathnasium.com",
    "Teaneck": "teaneck@mathnasium.com",
}
CC = "matt.diamond@mathnasium.com"

SECTION_COLORS = {
    "needs": "#2E75B6",
    "manual": "#C55A11",
    "good": "#70AD47",
}

SECTION_LABELS = {
    "needs": "Needs Appointments",
    "manual": "Manual Review Recommended",
    "good": "Looks Good",
}


def _fmt_month(period_str: str) -> str:
    """'2026-04' → 'Apr 2026'"""
    dt = datetime.strptime(period_str, "%Y-%m")
    return dt.strftime("%b %Y")


def _cell_bg(count: int, threshold: int) -> str:
    if count == 0:
        return "#fde8e8"
    if count < threshold:
        return "#fef9e7"
    return ""


def _issue_text(row, future_months: list, section: str) -> str:
    if section == "good":
        return ""
    parts = []
    for col in future_months:
        count = int(row[col])
        threshold = int(row["Threshold"])
        if section == "needs" and count < threshold:
            parts.append(f"{_fmt_month(col)}: {count} (need {threshold})")
        elif section == "manual":
            parts.append(f"{_fmt_month(col)}: {count} scheduled")
    return " | ".join(parts)


def _th(text: str) -> str:
    return (
        f"<th style='padding:6px 10px;border:1px solid #ddd;"
        f"background:#f5f5f5;text-align:left;font-size:13px;'>{text}</th>"
    )


def _td(text: str, bg: str = "") -> str:
    style = f"padding:6px 10px;border:1px solid #ddd;font-size:13px;"
    if bg:
        style += f"background:{bg};"
    return f"<td style='{style}'>{text}</td>"


def _section_html(section: str, df, recent_months: list, future_months: list) -> str:
    color = SECTION_COLORS[section]
    label = SECTION_LABELS[section]

    r_labels = [_fmt_month(m) for m in recent_months]
    f_labels = [_fmt_month(m) for m in future_months]

    headers = (
        [_th("Student Name")]
        + [_th(f"{l} Sessions") for l in r_labels]
        + [_th("Required/Month")]
        + [_th(f"{l} Scheduled") for l in f_labels]
        + [_th("Issue")]
    )

    rows_html = ""
    for _, row in df.iterrows():
        threshold = int(row["Threshold"])
        future_tds = "".join(
            _td(str(int(row[m])), _cell_bg(int(row[m]), threshold))
            for m in future_months
        )
        issue = _issue_text(row, future_months, section)
        cells = (
            _td(str(row["Student Name"]))
            + "".join(_td(str(int(row[m]))) for m in recent_months)
            + _td(str(threshold))
            + future_tds
            + _td(issue)
        )
        rows_html += f"<tr>{cells}</tr>"

    table = (
        "<table style='border-collapse:collapse;font-family:Arial,sans-serif;"
        "width:100%;margin-bottom:16px;'>"
        f"<tr>{''.join(headers)}</tr>"
        f"{rows_html}"
        "</table>"
    )

    return (
        f"<h3 style='color:{color};margin:24px 0 8px;font-family:Arial,sans-serif;"
        f"font-size:15px;'>{label}</h3>"
        + table
    )


def build_center_html(center: str, result: dict) -> str:
    recent = result["recent_months"]
    future = result["future_months"]

    sections_html = ""
    for section in ["needs", "manual", "good"]:
        df = result[section]
        center_df = df[df["Center"] == center]
        if center_df.empty:
            continue
        sections_html += _section_html(section, center_df, recent, future)

    divider = "<hr style='border:none;border-top:1px solid #ddd;margin:20px 0;'>"
    body = (
        f"<h2 style='font-family:Arial,sans-serif;font-size:18px;margin:0 0 16px;'>"
        f"{center} — Scheduling Report</h2>"
        "<p style='font-family:Arial,sans-serif;font-size:14px;'>Hi Team,</p>"
        "<p style='font-family:Arial,sans-serif;font-size:14px;'>"
        "Below is the scheduling report for this month. "
        "Please review and book appointments as needed.</p>"
        f"{divider}{sections_html}{divider}"
        "<p style='color:#999;font-size:12px;font-family:Arial,sans-serif;'>"
        "<em>Questions? Contact matt.diamond@mathnasium.com.</em></p>"
    )
    return (
        "<html><body style='max-width:960px;margin:0 auto;padding:20px;'>"
        f"{body}</body></html>"
    )


def send_report(center: str, result: dict) -> None:
    smtp_user = os.environ.get("SMTP_USER")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    if not smtp_user or not smtp_password:
        raise EnvironmentError("SMTP_USER and SMTP_PASSWORD must be set.")

    recipient = CENTERS[center]
    primary_month = _fmt_month(result["primary_col"])

    html = build_center_html(center, result)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Scheduling Report — {center} — {primary_month}"
    msg["From"] = smtp_user
    msg["To"] = recipient
    msg["Cc"] = CC

    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, [recipient, CC], msg.as_string())

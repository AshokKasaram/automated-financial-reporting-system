import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from datetime import datetime


def send_report(filepath: str, recipients: list, month_label: str) -> None:
    """
    Send the generated Excel report via Gmail SMTP.

    Required environment variables:
        SMTP_HOST  — e.g. smtp.gmail.com
        SMTP_PORT  — e.g. 587
        SMTP_FROM  — sender address
        SMTP_USER  — login username (usually same as FROM)
        SMTP_PASS  — Gmail App Password (not your regular password)
                     Generate at: myaccount.google.com/apppasswords
    """
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", 587))
    smtp_from = os.environ["SMTP_FROM"]
    smtp_user = os.environ["SMTP_USER"]
    smtp_pass = os.environ["SMTP_PASS"]

    msg = MIMEMultipart()
    msg["From"]    = smtp_from
    msg["To"]      = ", ".join(recipients)
    msg["Subject"] = f"Financial Report — {month_label}"

    body = f"""Hi team,

Please find attached the automated financial report for {month_label}.

This report includes three sheets:
  • P&L Summary        — total budget vs actuals with status flags
  • Budget vs Actuals  — monthly breakdown per account + bar chart
  • Variance Analysis  — accounts ranked by variance with action items

Generated at {datetime.now().strftime('%Y-%m-%d %H:%M UTC')} by the Financial Reporting Pipeline.

—
Automated Financial Reporter
"""
    msg.attach(MIMEText(body, "plain"))

    filename = os.path.basename(filepath)
    with open(filepath, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
        msg.attach(part)

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.ehlo()
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_from, recipients, msg.as_string())

    print(f"[email] Sent to {recipients} — {filename}")

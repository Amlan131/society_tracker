import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from . import celery, db
from .models import Complaint, User

@celery.task(name="tasks.send_email_async")
def send_email_async(to_email, subject, body_content):
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", 2525))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM_EMAIL", "no-reply@societytracker.com")

    if not all([smtp_host, smtp_user, smtp_pass]):
        print(f"[DEV MODE EMAIL] To: {to_email} | Subject: {subject}\n{body_content}")
        return

    try:
        msg = MIMEMultipart()
        msg["From"] = smtp_from
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body_content, "plain"))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_from, to_email, msg.as_string())
    except Exception as e:
        print(f"Failed to send email to {to_email}: {str(e)}")


@celery.task(name="tasks.check_overdue_complaints")
def check_overdue_complaints():
    """Scheduled task to flag complaints open past the configured threshold."""
    from . import create_app
    app = create_app()
    with app.app_context():
        days_threshold = int(os.getenv("OVERDUE_DAYS_THRESHOLD", 3))
        threshold_date = datetime.utcnow() - timedelta(days=days_threshold)

        # Flag unresolved complaints older than threshold
        overdue_complaints = Complaint.query.filter(
            Complaint.status.in_(["Open", "In Progress"]),
            Complaint.created_at <= threshold_date,
            Complaint.is_overdue == False
        ).all()

        for complaint in overdue_complaints:
            complaint.is_overdue = True
        
        db.session.commit()
        return f"Flagged {len(overdue_complaints)} complaints as overdue."

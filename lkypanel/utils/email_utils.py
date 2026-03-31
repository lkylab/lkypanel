import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from lkypanel.models import SystemSetting

def send_system_email(subject, message, recipient=None):
    """
    Send an email notification using SMTP settings from SystemSetting.
    """
    # Load SMTP settings
    smtp_host = SystemSetting.get_val('smtp_host')
    smtp_port = SystemSetting.get_val('smtp_port', '587')
    smtp_user = SystemSetting.get_val('smtp_user')
    smtp_pass = SystemSetting.get_val('smtp_pass')
    smtp_from = SystemSetting.get_val('smtp_from', 'noreply@lkypanel.local')
    alert_email = recipient or SystemSetting.get_val('alert_recipient')

    if not all([smtp_host, smtp_user, smtp_pass, alert_email]):
        print(f"SMTP not configured. Skipping email: {subject}")
        return False

    try:
        msg = MIMEMultipart()
        msg['From'] = smtp_from
        msg['To'] = alert_email
        msg['Subject'] = subject

        msg.attach(MIMEText(message, 'plain'))

        server = smtplib.SMTP(smtp_host, int(smtp_port))
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False

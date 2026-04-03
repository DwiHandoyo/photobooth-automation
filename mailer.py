import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def verify_smtp(smtp_host, smtp_port, sender, password):
    """Verify SMTP credentials by logging in and immediately closing.

    Raises on failure (auth error, connection error, etc.).
    """
    smtp_port = int(smtp_port)

    if smtp_port == 465:
        with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
            server.login(sender, password)
    else:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(sender, password)


def send_photo_email(smtp_host, smtp_port, sender, password, recipient, subject, body):
    """Send an email with the photo link.

    Args:
        smtp_host: SMTP server hostname (e.g. smtp.gmail.com).
        smtp_port: SMTP port (465 for SSL, 587 for STARTTLS).
        sender: Sender email address.
        password: Sender email password or app password.
        recipient: Recipient email address.
        subject: Email subject line.
        body: Email body text (should contain the Drive URL).
    """
    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    smtp_port = int(smtp_port)

    if smtp_port == 465:
        with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
            server.login(sender, password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)

import smtplib
from email.message import EmailMessage
from app import config # Assuming you have a config module with email settings

def send_email(to_email: str, subject: str, body: str):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = config.EMAIL_USERNAME
    msg["To"] = to_email
    msg.set_content(body)

    try:
        with smtplib.SMTP(config.EMAIL_HOST, config.EMAIL_PORT) as smtp:
            smtp.starttls()
            smtp.login(config.EMAIL_USERNAME, config.EMAIL_PASSWORD)
            smtp.send_message(msg)
        return True
    except Exception as e:
        print("Email failed:", e)
        return False

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header

from services.notifications.email.render_email_body import render_email
from services.string_handlers.string_handler import SMTP_SERVER, SMTP_PORT, SENDER_EMAIL, SENDER_PASSWORD, RECEIVER_EMAIL

def send_email_notification(job_cards):

    # server = None
    try:
        html_content = render_email(job_cards)

        # Create email object
        msg = MIMEMultipart()
        msg['From'] = Header("Mboka Bot", 'utf-8')  # Sender display name
        msg['To'] = Header("Krunch Sensei", 'utf-8') # Recipient display name
        msg['Subject'] = Header("Job Alerts", 'utf-8') # Email subject

        msg.attach(MIMEText(html_content, 'html', 'utf-8'))

        # # Create SMTP object and connect to the server
        # server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        # server.starttls() # Enable TLS encryption (usually required for port 587)

        # # Log in to the mailbox
        # server.login(SENDER_EMAIL, PASSWORD)

        # # Send the email
        # server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())

        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
                # server.connect()
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())

        print("Email sent successfully!")

    except Exception as e:
        print(f"Failed to send email: {e}")
    # finally:
        # server.quit() # Close the connection
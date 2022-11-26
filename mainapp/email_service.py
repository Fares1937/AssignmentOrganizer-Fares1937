import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import threading
from django.core.exceptions import AppRegistryNotReady
import schedule
import time

# setup from https://towardsdatascience.com/e-mails-notification-bot-with-python-4efa227278fb
class EmailService:
    def __init__(self):
        """
        Initializes the email service **only** if the device is running on a deployed server
        """
        self.login()
        t = threading.Thread(target=self.setup_notification_cycle)
        t.setDaemon(True)
        t.start()

    def login(self):
        print("Logging in to email server")
        self.sender_email = "a21assignmentorganizer@gmail.com"
        self.sender_username = "a21assignmentorganizer"
        self.sender_password = os.getenv("EMAIL_PASSWORD")
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587

        self.server = smtplib.SMTP(self.smtp_server, self.smtp_port)
        self.server.starttls()
        self.server.login(self.sender_username, self.sender_password)
        print("Logged into email server")

    def message(self, text, to, subject):
        """
        Sends a message with body=text to recipient=to with subject=subject
        """
        print("Sending email...")
        message = MIMEMultipart("alternative")
        message["From"] = self.sender_email
        message["To"] = to
        message["Subject"] = subject
        message.attach(MIMEText(text, "html"))

        text = message.as_string()

        self.server.sendmail(self.sender_email, to, text)
        print("Mail sent!")

    def setup_notification_cycle(self):
        """
        Initializes the scheduler for the notification cycle
        """
        try:
            from . import tools

            # every day at 1AM update daily assignments and queue messages to be sent
            schedule.every().day.at("01:00:00").do(
                tools.notify_students_of_today_assignments
            )

            # every 10 minutes check for a class assignment change and send messages out
            schedule.every(10).minutes.do(tools.send_all_messages)

            self.notification_cycle()
        except AppRegistryNotReady:
            print(
                "A NON-FATAL error occurred with the email notification cycle, waiting 10 seconds and trying again"
            )
            time.sleep(10)
            self.setup_notification_cycle()

    def notification_cycle(self):
        """
        Sends all notifications in notification models every once and a while
        """
        print("Email notification loop has begun")
        try:
            while True:
                schedule.run_pending()
                time.sleep(10)
        except smtplib.SMTPSenderRefused:
            print(
                "A timeout error occured while attempting to send a message, logging in and trying again"
            )
            time.sleep(5)
            self.login()
            time.sleep(5)
            self.notification_cycle()
        except:
            import traceback

            traceback.print_exc()
            print("A FATAL EXCEPTION OCCURED IN EMAIL NOTIFICATION CYCLE")
            print("Waiting 30 seconds and trying again")
            time.sleep(30)
            self.login()
            time.sleep(5)
            self.notification_cycle()


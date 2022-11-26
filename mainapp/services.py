import os
from google.oauth2 import service_account
import sys
from googleapiclient.discovery import build
from .email_service import EmailService

# structure of this method was replicated from https://cloud.google.com/iam/docs/creating-managing-service-accounts
def initialize_google_calendar_service():
    """
    Initializes the google calendar service
    Requires the placement of client_secret.json in the root directory of project
    """
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "client_secret.json"

    credentials = service_account.Credentials.from_service_account_file(
        filename=os.environ["GOOGLE_APPLICATION_CREDENTIALS"],
        scopes=["https://www.googleapis.com/auth/calendar.app.created"],
    )

    return build("calendar", "v3", credentials=credentials)


def initialize_email_service():
    """
    Initializes the email service
    """
    return EmailService()


class FakeExecutor:
    def execute(*args, **kwargs):
        return {"items": [], "id": 0}


class FakeEventResult:
    def list(*args, **kwargs):
        return FakeExecutor()


class FakeCalendarResult:
    def insert(*args, **kwargs):
        return FakeExecutor()


class FakeCalendarService:
    def events(*args, **kwargs):
        return FakeEventResult()

    def calendars(*args, **kwargs):
        return FakeCalendarResult()


def initialize_services():
    """
    Initializes all services into service library
    """
    global calendar_service
    global email_service
    if "test" in str(sys.argv):
        print("Faking Google Calendar Service for Tests")
        calendar_service = FakeCalendarService()
    else:
        print("Google Calendar Service Initialized")
        calendar_service = initialize_google_calendar_service()

    # temporarily extracting email_service initialization into a seperate dyno
    # email_service = initialize_email_service()
    print("Services initialized")
    print("Using parameters: " + str(sys.argv))


def initialize_services_for_daemon():
    """
    Initializes the services for the seperate daemon
    """
    global email_service
    email_service = initialize_email_service()

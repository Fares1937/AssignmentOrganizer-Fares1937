from datetime import timedelta, datetime
import pytz
from django.contrib.auth.models import User
from . import models
import mockito


def create_date(name="event_summary", year=2000, month=1, day=1):
    """
    Creates a toy date for tests
    """
    dt = pytz.utc.localize(datetime(year=year, month=month, day=day))
    dt2 = dt + timedelta(days=1)
    return {
        "summary": name,
        "id": 1234,
        "start": {"dateTime": dt.isoformat()},
        "end": {"dateTime": dt2.isoformat()},
        "className": None,
        "description": None,
    }


def get_request(worker, page):
    """
    Creates a toy request for tests
    """
    response = get_response(worker, page)
    return response.wsgi_request


def get_response(worker, page):
    """
    Creates a toy response for tests
    """
    return worker.client.get(page)


def login(worker, create_student=True):
    """
    Log in as arbitrary user
    Returns user object
    """
    username = "user"
    password = "pass"
    user = User.objects.create(username=username)
    user.set_password(password)
    user.is_active = True
    user.email = "test@test.com"
    user.save()
    worker.client.login(username=username, password=password)

    if create_student == True:
        models.Student.objects.create(
            userId=user.id, classes=set(), class_colors=dict(), color="#000000"
        )
    return user


def logout(worker, user, destroy_student=True):
    """
    Log out given user
    """
    User.objects.filter(id=user.id).delete()
    worker.client.logout()

    if destroy_student == True:
        models.Student.objects.filter(userId=user.id).delete()

def create_request(userId, className=None):
    class User_With_ID:
        def __init__(self):
            self.id = userId
    class Request:
        def __init__(self):
            self.user = User_With_ID()

        def get_full_path(self):
            return f"classes/{className}/"

    return Request()

class TestFailed(Exception):
    pass

class TestPassed(Exception):
    pass
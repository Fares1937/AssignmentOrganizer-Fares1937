from calendar import c
from django import test
from django.test import TestCase
from django.contrib.auth.models import User
from mockito import when, mock, any
from .test_utils import *
from . import tools, services, views, models, test_utils, context_processors
from .calendar_generator import Calendar
from django.urls import reverse
import builtins

# Create your tests here.
google_calendar_service_events_copy = services.calendar_service.events
google_calendar_service_calendars_copy = services.calendar_service.calendars
prints = print


def print(thing):
    prints(thing)


def unstub():
    from mockito import unstub

    unstub()
    # there is an issue with mockito where sometimes this function is forgetten
    # when calling unstub. This fixes this issue.
    services.calendar_service.events = google_calendar_service_events_copy
    services.calendar_service.calendars = google_calendar_service_calendars_copy

    # major issue if calendar is being created in tests
    # when(builtins).print(any).thenReturn(True)
    # when(builtins).print("Failed to send email to userId 1234").thenRaise(ValueError)
    # when(builtins).print("Creating calendar for new class").thenRaise(ValueError)


class GoogleLogin(TestCase):
    def test_google_login_not_logged_in(self):
        """
        This test makes sure that the google login prompt appears on the home page
        for someone that is not logged in
        """

        # load home page
        response = get_response(self, "")

        # confirm not logged in
        self.assertContains(response, "log-in")

    def test_google_login_logged_in(self):
        """
        This test makes sure a logged-in account will see the prompt confirming they are logged in
        """
        username = "Good username"
        password = "Good password"

        # create existing user
        user = User.objects.create(username=username)
        user.set_password(password)
        user.is_active = True
        user.save()

        # log into existing user
        self.client.login(username=username, password=password)

        # load home page
        response = get_response(self, "")

        # confirm logged in
        self.assertContains(response, f"{username}")

    def test_google_login_failed_login(self):
        """
        This tests makes sure that someone who attempts to login to an unexisting account will
        not be successfully logged in
        """

        username = "Good username"
        password = "Good password"
        fake_password = "Bad password"

        # create existing user
        user = User.objects.create(username=username)
        user.set_password(password)
        user.is_active = True
        user.save()

        # log into non-existing account (should not succeed)
        self.client.login(username=username, password=fake_password)

        # load home page
        response = get_response(self, "")

        # confirm not logged in
        self.assertContains(response, "log-in")


class Initialization(TestCase):
    def test_client_secret_working(self):
        """
        Tests to make sure client secret appears on machine
        The client secret should always be here, after heroku, actions, or local setup
        Since this method is run in __init__, it has already run
        We just need to test that there is stuff in the client secret json
        """
        with open("client_secret.json", "r") as file:
            data = file.read()

        self.assertTrue(len(data) != 0)

    def test_initialize_google_calendar_service(self):
        """
        Tests to make sure the google calendar is already initialized
        initialize services should already have been run, so we just need to make sure
        it exists
        """

        from . import services

        self.assertTrue(services.calendar_service != None)

    def test_initialize_email_service_local(self):
        """
        Tests to make sure the email service is not initialized on local user
        """

        from . import services

        # make sure sender email was never initialized
        self.assertFalse(hasattr(services, "email_service"))


class ViewTests(TestCase):
    def test_calendar_view_one_event(self):
        """
        This test confirms that a calendar event shows when there is one calendar event
        """

        # we use mockito here because we do not want to trigger the api every time
        # we want to run tests
        when(tools).get_events(any, month=any, year=any).thenReturn(
            [create_date(name="good event", day=15)]
        )
        when(tools).get_events(any, month=any, year=any, day=15).thenReturn(
            [create_date(name="good event", day=15)]
        )
        when(tools).calendar_exists(any).thenReturn(True)

        user = test_utils.login(self)
        request = mock({"user": mock({"id": user.id})})

        html = Calendar(year=2000, month=1).formatmonth(request)

        self.assertTrue("good event" in html)

        unstub()
        test_utils.logout(self, user)

    def test_calendar_view_no_event(self):
        """
        This test confirms that a calendar event shows when there is no calendar event
        """

        # we use mockito here because we do not want to trigger the api every time
        # we want to run tests
        when(tools).get_events(any, month=any, year=any).thenReturn([])
        when(tools).get_events(any, month=any, year=any, day=15).thenReturn([])
        when(tools).calendar_exists(any).thenReturn(True)

        html = Calendar(year=2000, month=1).formatmonth(None)

        # each event has itself a checkbox. If there are no checkboxes, there are no events.
        self.assertTrue(html.count("checkbox") == 0)

        unstub()

    def test_add_event_valid_input(self):
        """
        Tests the add event form to make sure it attempts to add an event given valid inputs
        """

        class TestWorked(Exception):
            pass

        user = login(self)
        assignment_name = "Good assignment name"
        assignment_length = 10
        assignment_date_string = "2000-01-01"
        # submit valid assignment on the form

        when(tools).create_event(
            any,
            assignment_name,
            datetime.fromisoformat(assignment_date_string),
            className=None,
            isPersonal=any,
        ).thenRaise(TestWorked)

        try:
            response = self.client.post(
                reverse("add_assignment"),
                data={
                    "summary": assignment_name,
                    "calendar": "None",
                    "time": "2000-01-01",
                },
            )
        except TestWorked:
            # we passed
            unstub()
            logout(self, user)
            return
        unstub()
        logout(self, user)
        self.assertTrue(False)

    def test_add_event_valid_input_sends_notif(self):
        """
        Tests the add event form to make sure it will send a notification on assignment creation
        """
        assignment_name = "Good assignment name"
        assignment_length = 10
        assignment_date_string = "2000-01-01"
        # submit valid assignment on the form

        when(tools).create_event(
            any,
            assignment_name,
            datetime.fromisoformat(assignment_date_string),
            className=None,
        ).thenReturn(False)

        user = test_utils.login(self, create_student=False)
        clazz = models.Class.objects.create(
            calendarId=1, className="class name", professorId=0
        )
        student = models.Student.objects.create(
            userId=user.id,
            calendarId=1,
            classes={clazz},
            professor=True,
            class_colors=dict(),
            color="#000000",
        )

        try:
            response = self.client.post(
                reverse("add_assignment"),
                data={
                    "summary": assignment_name,
                    "est_time": assignment_length,
                    "time": assignment_date_string,
                    "calendar": "class name",
                },
            )
            self.assertTrue(0 != models.Notification.objects.all().count())
        finally:
            # we passed
            unstub()
            logout(self, user)
            models.Student.objects.all().delete()
            models.Notification.objects.all().delete()
            models.Class.objects.all().delete()
            return

    def test_add_event_invalid_length(self):
        """
        Tests the add event form to make sure it does not attempt to add given invalid assignment length
        """

        class TestFailed(Exception):
            pass

        assignment_name = "Good assignment name"
        assignment_length = 1.5
        assignment_date_string = "2000-01-01"
        # submit valid assignment on the form

        when(tools).create_event(
            any,
            assignment_name,
            str(assignment_length),
            datetime.fromisoformat(assignment_date_string),
        ).thenRaise(TestFailed)

        try:
            response = self.client.post(
                reverse("add_assignment"),
                data={
                    "summary": assignment_name,
                    "est_time": assignment_length,
                    "time": assignment_date_string,
                },
            )
        except TestFailed:
            # we failed
            unstub()
            self.assertTrue(False)

        # we passed
        unstub()
        return

    def test_add_event_multiple_invalid_assignment_name(self):
        """
        Tests the add event form to make sure it does not attempt to add invalid assignment name with multiple non-alphanumeric characters
        """

        class TestFailed(Exception):
            pass

        assignment_name = "*&^@)Bad"
        assignment_length = 1
        assignment_date_string = "2021-11-29"

        # submit valid assignment on the form
        when(tools).create_event(
            any,
            assignment_name,
            str(assignment_length),
            datetime.fromisoformat(assignment_date_string),
        ).thenRaise(TestFailed)

        try:
            response = self.client.post(
                reverse("add_assignment"),
                data={
                    "summary": assignment_name,
                    "est_time": assignment_length,
                    "time": assignment_date_string,
                },
            )
        except TestFailed:
            # we failed
            unstub()
            self.assertTrue(False)

        # we passed
        unstub()
        return

    def test_add_event_single_invalid_assignment_name(self):
        """
        Tests the add event form to make sure it does not attempt to add invalid assignment name with a single non-alphanumeric character
        """

        class TestFailed(Exception):
            pass

        assignment_name = "@Bad"
        assignment_length = 1
        assignment_date_string = "2021-11-29"

        # submit valid assignment on the form
        when(tools).create_event(
            any,
            assignment_name,
            str(assignment_length),
            datetime.fromisoformat(assignment_date_string),
        ).thenRaise(TestFailed)

        try:
            response = self.client.post(
                reverse("add_assignment"),
                data={
                    "summary": assignment_name,
                    "est_time": assignment_length,
                    "time": assignment_date_string,
                },
            )
        except TestFailed:
            # we failed
            unstub()
            self.assertTrue(False)

        # we passed
        unstub()
        return

    def test_add_class_duplicate_name(self):
        """Tests to make sure that a user cannot add a class with a duplicate name"""

        clazz = models.Class.objects.create(className="class1", professorId=0)
        when(tools).create_class(any, any, any).thenRaise(TestFailed)

        try:
            response = self.client.post(
                reverse("create_class"),
                data={
                    "name": "class1",
                    "description": "description",
                },
            )
        finally:
            models.Class.objects.all().delete()

    def test_add_event_invalid_date(self):
        """
        Tests the add event form to make sure it does not attempt to add given invalid assignment date
        """

        class TestFailed(Exception):
            pass

        assignment_name = "Good assignment name"
        assignment_length = 1
        assignment_date_string = "01-01-2000"

        # submit valid assignment on the form
        when(tools).create_event(
            any, assignment_name, str(assignment_length), any,
        ).thenRaise(TestFailed)

        try:
            response = self.client.post(
                reverse("add_assignment"),
                data={
                    "summary": assignment_name,
                    "est_time": assignment_length,
                    "time": assignment_date_string,
                },
            )
        except TestFailed:
            # we failed
            unstub()
            self.assertTrue(False)

        # we passed
        unstub()
        return

    def test_classes_null_user(self):
        """
        Tests the classes view for the null user
        """
        response = get_response(self, "/classes/")
        # make sure it went to the home page
        self.assertContains(response, "Start your day right.")

    def test_classes(self):
        """
        Tests the classes view for a user with a class
        """

        user = login(self, create_student=False)

        clazz = models.Class.objects.create(className="class1", professorId=0)
        models.Student.objects.create(
            userId=user.id, classes={clazz}, class_colors=dict(), color="#000000"
        )

        # load home page
        response = get_response(self, "/classes/")

        try:
            # make sure class1 appeared
            self.assertContains(response, "class1")
        finally:
            models.Class.objects.filter(className="class1").delete()
            logout(self, user)

    def test_remove_classes_null_user(self):
        """
        Tests the remove classes functionality for the null user
        """
        response = get_response(self, "/classes/fakeClassName/remove_classes/")
        # make sure it went to the home page
        self.assertContains(response, "Start your day right.")

    def test_remove_classes_class_chosen(self):
        """
        Tests the remove classes functionality given that a class was chosen to be removed
        """
        # log in as a user with one class, class1
        user = login(self, create_student=False)
        clazz = models.Class.objects.create(className="class1", professorId=0)
        models.Student.objects.create(
            userId=user.id, classes={clazz}, class_colors=dict(), color="color"
        )

        # send in a request to remove no classes
        response = self.client.post(
            reverse("remove_classes", kwargs={"className": "class1"}),
        )

        try:
            self.assertTrue(
                len(models.Student.objects.filter(userId=user.id).first().classes) == 0
            )
        finally:
            logout(self, user)
            models.Class.objects.filter(className="class1").delete()

    def test_all_classes_null_user(self):
        """
        Tests the all classes view to make sure null user cannot see it
        """

        response = get_response(self, "/all_classes/")
        # make sure it went to the home page
        self.assertContains(response, "Start your day right.")

    def test_all_classes(self):
        """
        Tests the all classes view to make sure the page shows a class when it is there
        """

        user = login(self)
        models.Class.objects.create(className="class1", professorId=0)

        response = get_response(self, "/all_classes/")

        try:
            self.assertContains(response, "class1")
        finally:
            models.Class.objects.filter(className="class1").delete()
            logout(self, user)

    def test_add_classes_null_user(self):
        """
        Tests add classes view to make sure null user cannot access it
        """
        response = get_response(
            self, reverse("add_classes", kwargs={"className": "fake"})
        )
        # make sure it went to the home page
        self.assertContains(response, "Start your day right.")

    def test_add_classes_classes_chosen(self):
        """
        Tests the add classes view in the event that classes were chosen
        """
        # log in as a user with no classes
        user = login(self)
        clazz = models.Class.objects.create(className="class1", professorId=0)

        # send in a request to add a class
        response = self.client.post(
            reverse("add_classes", kwargs={"className": "class1"}),
        )

        try:
            self.assertTrue(
                models.Student.objects.filter(userId=user.id).first().classes == {clazz}
            )
        finally:
            logout(self, user)
            models.Class.objects.filter(className="class1").delete()

    def test_add_assignment_null_user(self):
        """
        Tests the add assignment view for a null user
        """
        response = get_response(self, reverse("add_assignment"))
        # make sure it went to the home page
        self.assertContains(response, "Start your day right.")

    def test_create_class_null_user(self):
        """
        Tests to make sure null user cannot create a class
        """
        response = get_response(self, reverse("create_class"))
        # make sure it went to the home page
        self.assertContains(response, "Start your day right.")

    def test_create_class_non_professor(self):
        """
        Tests to make sure non professor cannot see create class page
        """
        user = login(self)
        response = str(get_response(self, reverse("create_class")))

        try:
            self.assertTrue(
                "HttpResponseRedirect" in response and 'url="/"' in response
            )
        finally:
            logout(self, user)

    def test_create_class_professor(self):
        """
        Tests to make sure a class is created when information is entered by a professor in
        the create_class view
        Blocks calendar creation
        """

        class TestPassed(Exception):
            pass

        # if we try to create a calendar, we passed
        when(services.calendar_service).calendars().thenRaise(TestPassed)
        user = login(self)

        # assume the user is a professor
        when(tools).is_professor(any).thenReturn(True)

        try:
            response = self.client.post(
                reverse("create_class"),
                data={"name": "class name", "description": "new class description"},
            )
        except TestPassed:
            # we ran the calendar creation... class exists
            return
        finally:
            unstub()
            logout(self, user)
            models.Class.objects.filter(className="class name").delete()
        # we failed
        self.assertTrue(False)

    def test_create_class_invalid_name_too_short(self):
        """
        Tests to make sure a class is not created when information is entered by a professor in
        the create_class view, for too short class name
        Blocks calendar creation
        """

        class TestFailed(Exception):
            pass

        # if we try to create a calendar, we passed
        when(services.calendar_service).calendars().thenRaise(TestFailed)
        user = login(self)

        # assume the user is a professor
        when(tools).is_professor(any).thenReturn(True)

        too_short = "h"
        try:
            response = self.client.post(
                reverse("create_class"), data={"name": too_short},
            )
        except TestFailed:
            # we ran the calendar creation... we shouldnt have made a class
            self.assertTrue(False)
        finally:
            unstub()
            logout(self, user)
            models.Class.objects.filter(className="class name").delete()
        # we passed

    def test_create_class_invalid_name_invalid_character(self):
        """
        Tests to make sure a class is not created when information is entered by a professor in
        the create_class view, for class name with invalid character
        Blocks calendar creation
        """

        class TestFailed(Exception):
            pass

        # if we try to create a calendar, we passed
        when(services.calendar_service).calendars().thenRaise(TestFailed)
        user = login(self)

        # assume the user is a professor
        when(tools).is_professor(any).thenReturn(True)

        bad_name = "this is a / class name"
        try:
            response = self.client.post(
                reverse("create_class"), data={"name": bad_name},
            )
        except TestFailed:
            # we ran the calendar creation... we shouldnt have made a class
            self.assertTrue(False)
        finally:
            unstub()
            logout(self, user)
            models.Class.objects.filter(className="class name").delete()
        # we passed


class TestTools(TestCase):
    def test_class_exists_for_student_null_student(self):
        """
        Tests the 'class exists for student' method on the null student
        """
        request = create_request(0)

        clazz = models.Class.objects.create(className="example", professorId=0)

        try:
            self.assertFalse(tools.class_exists_for_student(request, "example"))
        finally:
            models.Class.objects.all().delete()

    def test_class_exists_for_student_doesnt_exist(self):
        """
        Tests the 'class exists for student' method on a student that doesnt have the class
        """
        request = create_request(0)

        clazz = models.Class.objects.create(className="example", professorId=0)
        user = login(self, create_student=False)
        student = models.Student.objects.create(userId=user.id,
            calendarId=1,
            classes=set(),
            color="#000000",
            class_colors=dict(),)

        try:
            self.assertFalse(tools.class_exists_for_student(request, "example"))
        finally:
            models.Class.objects.all().delete()
            models.Student.objects.all().delete()
            logout(self, user, destroy_student=False)

    def test_class_exists_for_student_does_exist(self):
        """
        Tests the 'class exists for student' method on a student that does have the class
        """
        request = create_request(0)

        clazz = models.Class.objects.create(className="example", professorId=0)
        user = login(self, create_student=False)
        student = models.Student.objects.create(userId=user.id,
            calendarId=1,
            classes={clazz},
            color="#000000",
            class_colors=dict(),)

        try:
            self.assertFalse(tools.class_exists_for_student(request, "example"))
        finally:
            models.Class.objects.all().delete()
            models.Student.objects.all().delete()
            logout(self, user, destroy_student=False)

    def test_is_admin_of_event_null_user(self):
        """
        Tests the is admin of event given a null user
        """
        event = {'className' : "example", 'organizer' : {'email' : "email@email.com"}}

        request = create_request(0)

        try:
            self.assertFalse(tools.is_admin_of_event(request, event))
        finally:
            # no cleanup needs to be done here
            pass

    def test_is_admin_of_event_not_creator(self):
        """
        Tests the is admin of event given a user that is not a creator of an assignment
        """
        event = {'className' : "example", 'organizer' : {'email' : "email@email.com"}}
        user = login(self, create_student=False)
        student = models.Student.objects.create(userId=user.id,
            calendarId=1,
            classes=set(),
            color="#000000",
            class_colors=dict(),)
        request = create_request(user.id)

        try:
            self.assertFalse(tools.is_admin_of_event(request, event))
        finally:
            logout(self, user, destroy_student=False)
            models.Student.objects.all().delete()
   
    def test_is_admin_of_event_creator(self):
        """
        Tests the is admin of event given a user that is a creator of an assignment
        """
        event = {'className' : "example", 'organizer' : {'email' : "email@email.com"}}
        user = login(self, create_student=False)
        user.email = "email@email.com"
        user.save()
        student = models.Student.objects.create(userId=user.id,
            classes=set(),
            color="#000000",
            class_colors=dict(),
            calendarId=user.email)
        request = create_request(user.id)

        try:
            self.assertTrue(tools.is_admin_of_event(request, event))
        finally:
            logout(self, user, destroy_student=False)
            models.Student.objects.all().delete()

    def test_get_all_events_null_user(self):
        """
        Tests getting all events from null user's calendar
        """

        request = create_request(0)

        self.assertEquals([], tools.get_all_events(request))

    def test_get_all_events_normal_user_no_classes(self):
        """
        Tests getting all events for a user with no classes
        """
        user = login(self, create_student=False)
        student = models.Student.objects.create(
            userId=user.id,
            calendarId=1234,
            classes=set(),
            color="#000000",
            class_colors=dict(),
        )
        request = create_request(user.id)

        # make sure user calendar is queried
        when(tools).get_all_events_from_calendar('1234', any).thenRaise(TestPassed)

        try:
            self.assertEquals([], tools.get_all_events(request))
        except TestPassed:
            return
        finally:
            logout(self, user, destroy_student=False)
            models.Student.objects.all().delete()
        self.assertTrue(False)

    def test_get_all_events_normal_user_has_classes(self):
        """
        Tests getting all events for a user with a class
        """
        user = login(self, create_student=False)
        clazz = models.Class.objects.create(
            calendarId='1020', className="New class", professorId=0
        )
        student = models.Student.objects.create(
            userId=user.id,
            calendarId='1234',
            classes={clazz},
            color="#000000",
            class_colors=dict(),
        )
        request = create_request(user.id)

        # make sure user calendar is queried
        when(tools).get_all_events_from_calendar('1020', any).thenRaise(TestPassed)

        # do nothing if the user calendar is queried. We already know from another test this works
        when(tools).get_all_events_from_calendar('1234', any).thenReturn([])


        try:
            self.assertEquals([], tools.get_all_events(request))
        except TestPassed:
            return
        finally:
            logout(self, user, destroy_student=False)
            models.Student.objects.all().delete()
        self.assertTrue(False)

    def test_get_all_events_normal_user_has_multiple_classes(self):
        """
        Tests getting all events for a user with multiple classes
        """
        user = login(self, create_student=False)
        clazz = models.Class.objects.create(
            calendarId='1020', className="New class", professorId=0
        )
        second_clazz = models.Class.objects.create(
            calendarId='2020', className="Another class", professorId=0
        )
        student = models.Student.objects.create(
            userId=user.id,
            calendarId='1234',
            classes={clazz, second_clazz},
            color="#000000",
            class_colors=dict(),
        )
        request = create_request(user.id)

        # make sure user calendar is queried
        when(tools).get_all_events_from_calendar('1020', any).thenRaise(TestPassed)

        # do nothing if the user calendar is queried. We already know from another test this works
        when(tools).get_all_events_from_calendar('1234', any).thenReturn([])


        try:
            self.assertEquals([], tools.get_all_events(request))
        except TestPassed:
            return
        finally:
            logout(self, user, destroy_student=False)
            models.Student.objects.all().delete()
        self.assertTrue(False)

    def test_set_class_color_no_class(self):
        """
        Tests setting a user color
        """
        user = login(self, create_student=False)
        clazz = models.Class.objects.create(
            calendarId='1020', className="New class", professorId=0
        )
        student = models.Student.objects.create(
            userId=user.id,
            calendarId='1234',
            classes={clazz},
            color="#000000",
            class_colors=dict(),
        )
        request = create_request(user.id)

        tools.set_class_color(request, None, "#111111")

        try:
            self.assertEquals("#111111", tools.get_color(request))
        finally:
            logout(self, user, destroy_student=False)
            models.Student.objects.all().delete()

    def test_set_class_color(self):
        """
        Tests setting a class color for a user
        """
        user = login(self, create_student=False)
        clazz = models.Class.objects.create(
            calendarId='1020', className="New class", professorId=0
        )
        student = models.Student.objects.create(
            userId=user.id,
            calendarId='1234',
            classes={clazz},
            color="#000000",
            class_colors=dict(),
        )
        request = create_request(user.id)

        tools.set_class_color(request, 'New class', "#111111")

        try:
            self.assertEquals("#111111", tools.get_color(request, 'New class'))
        finally:
            logout(self, user, destroy_student=False)
            models.Student.objects.all().delete()

    def test_check_off_unchecked_assignment(self):
        """
        Tests checking off an unchecked assignment to make sure it checks off
        """

        event = {'className': 'example', 'id': 'eventId'}
        user = login(self, create_student=False)
        student = models.Student.objects.create(
            userId=user.id,
            calendarId=1,
            classes=set(),
            color="#000000",
            class_colors=dict(),
        )

        request = create_request(user.id)

        tools.check_off(request, event['id'], event['className'])

        try:
            self.assertTrue(tools.is_checked_off(request, event))
        finally:
            logout(self, user, destroy_student=False)
            models.Student.objects.all().delete()

    def test_check_off_checked_assignment(self):
        """
        Tests checking off a checked assignment to make sure it unchecks
        """

        event = {'className': 'example', 'id': 'eventId'}
        user = login(self, create_student=False)
        student = models.Student.objects.create(
            userId=user.id,
            calendarId=1,
            classes=set(),
            color="#000000",
            class_colors=dict(),
        )

        request = create_request(user.id)

        # check and uncheck. There is already a test that does this once, so this should test the other case
        tools.check_off(request, event['id'], event['className'])
        tools.check_off(request, event['id'], event['className'])

        try:
            self.assertFalse(tools.is_checked_off(request, event))
        finally:
            logout(self, user, destroy_student=False)
            models.Student.objects.all().delete()

    def test_list_members_of_class_no_members(self):
        """
        Tests getting a list of all members for a classname with no members
        """
        clazz = models.Class.objects.create(
            calendarId='1020', className="New class", professorId=0
        )

        try:
            self.assertEquals([], tools.list_members_of_class("New class"))
        finally:
            models.Class.objects.all().delete()

    
    def test_list_members_of_class_two_members(self):
        """
        Tests getting a list of all members for a classname with two members
        """
        clazz = models.Class.objects.create(
            calendarId='1020', className="New class", professorId=0
        )
        student1 = models.Student.objects.create(
            userId=1,
            calendarId=1,
            classes={clazz},
            color="#000000",
            class_colors=dict(),
        )
        student2 = models.Student.objects.create(
            userId=1234,
            calendarId=1,
            classes={clazz},
            color="#000000",
            class_colors=dict(),
        )

        try:
            self.assertEquals([student1, student2], tools.list_members_of_class("New class"))
        finally:
            models.Class.objects.all().delete()
            models.Student.objects.all().delete()

    def test_get_user_with_id_student_exists(self):
        """
        Tests the get user with id method in the case where the student exists
        """
        student = models.Student.objects.create(
            userId=1,
            calendarId=1,
            classes=set(),
            color="#000000",
            class_colors=dict(),
        )

        try:
            self.assertEquals(student, tools.get_user_with_id(1))
        finally:
            models.Student.objects.all().delete()

    def test_get_user_with_id_student_does_not(self):
        """
        Tests the get user with id method in the case where the student does not exist
        """
        student = models.Student.objects.create(
            userId=1,
            calendarId=1,
            classes=set(),
            color="#000000",
            class_colors=dict(),
        )

        try:
            self.assertEquals(None, tools.get_user_with_id(2))
        finally:
            models.Student.objects.all().delete()

    def test_parse_description_to_text_left_inverse(self):
        """
        Tests to make sure applying parse description to text is the left inverse of parse description to html
        """

        desc = "email:email@email.com\nphone:phone_number"

        self.assertEquals(desc, tools.parse_description_to_text(tools.parse_description_to_html(desc)))


    def test_send_message_no_user(self):
        """
        Tests sending a message to a user that is not registered, should do nothing
        """

        tools.send_message(1234, "Message here!")

        self.assertTrue(0 == models.Notification.objects.all().count())

    def test_send_message_with_user(self):
        """
        Tests sending a message to a user that is registered, should add to notifications queue
        """

        user = test_utils.login(self, create_student=True)

        tools.send_message(user.id, "Message text")
        try:
            notif = models.Notification.objects.first()
            self.assertTrue(notif.text == "Message text")
        finally:
            test_utils.logout(self, user, destroy_student=True)
            models.Notification.objects.all().delete()

    def test_send_all_messages_no_messages(self):
        """
        Tests sending messages given there are no messages
        """

        class TestFailed(Exception):
            pass

        class Mocked_Email_Service:
            def message(self, text, to, subject):
                """
                Fake method to populate services email service
                """

        needs_service_reset = False
        if hasattr(services, "email_service"):
            temp_email_service = services.email_service
            needs_service_reset = True

        services.email_service = Mocked_Email_Service()

        when(services.email_service).message(text=any, to=any, subject=any).thenRaise(
            TestFailed
        )

        try:
            tools.send_all_messages()
        except TestFailed:
            # we failed
            self.assertTrue(False)
        finally:
            unstub()
            if needs_service_reset:
                services.email_service = temp_email_service

    def test_send_all_messages_with_messages(self):
        """
        Tests sending messages given there is a message
        """

        class TestPassed(Exception):
            pass

        notif = models.Notification.objects.create(
            email="test@test.com", text="Example text"
        )

        class Mocked_Email_Service:
            def message(self, text, to, subject):
                """
                Fake method to populate services email service
                """

        if hasattr(services, "email_service"):
            temp_email_service = services.email_service

        services.email_service = Mocked_Email_Service()

        when(services.email_service).message(
            text="Example text", to="test@test.com", subject=any
        ).thenRaise(TestPassed)

        try:
            tools.send_all_messages()
        except TestPassed:
            # we passed
            return
        finally:
            unstub()
            models.Notification.objects.all().delete()
            if hasattr(services, "email_service"):
                services.email_service = temp_email_service

        self.assertTrue(False)

    def test_get_all_students_no_class(self):
        """
        Tests get all students given there is no class with a certain class name
        """

        student = models.Student.objects.create(
            userId=1234,
            calendarId=1,
            classes=set(),
            color="#000000",
            class_colors=dict(),
        )

        try:
            self.assertTrue([] == tools.get_all_students("No class"))
        finally:
            models.Student.objects.all().delete()

    def test_get_all_students_class_no_pairs(self):
        """
        Tests get all students given there is a class with that name, but no student is signed up for it
        """

        student = models.Student.objects.create(
            userId=1234, calendarId=1, classes=set()
        )

        clazz = models.Class.objects.create(calendarId=1020, className="New class")

        try:
            self.assertTrue([] == tools.get_all_students("New class"))
        finally:
            models.Student.objects.all().delete()

    def test_get_all_students_class_no_pairs(self):
        """
        Tests get all students given there is a class with that name, but no student is signed up for it
        """

        student = models.Student.objects.create(
            userId=1234,
            calendarId=1,
            classes=set(),
            color="#000000",
            class_colors=dict(),
        )

        clazz = models.Class.objects.create(
            calendarId=1020, className="New class", professorId=0
        )

        try:
            self.assertTrue([] == tools.get_all_students("New class"))
        finally:
            models.Student.objects.all().delete()
            models.Class.objects.all().delete()

    def test_get_all_students_class_matching(self):
        """
        Tests get all students given there is a class with that name
        """

        clazz = models.Class.objects.create(
            calendarId=1020, className="New class", professorId=0
        )

        student = models.Student.objects.create(
            userId=1234,
            calendarId=1,
            classes={clazz},
            color="#000000",
            class_colors=dict(),
        )

        try:
            self.assertTrue([student] == tools.get_all_students("New class"))
        finally:
            models.Student.objects.all().delete()
            models.Class.objects.all().delete()

    def test_notify_students_of_change(self):
        """
        Tests notifying all students of a change
        """

        clazz = models.Class.objects.create(
            calendarId=1020, className="New class", professorId=0
        )

        user = test_utils.login(self, create_student=False)

        student = models.Student.objects.create(
            userId=user.id,
            calendarId=1,
            classes={clazz},
            color="#000000",
            class_colors=dict(),
        )

        tools.notify_students_of_change("New class", "Assg", "change")
        try:
            self.assertTrue(models.Notification.objects.all().count() == 1)
        finally:
            models.Student.objects.all().delete()
            models.Class.objects.all().delete()
            models.Notification.objects.all().delete()
            test_utils.logout(self, user, destroy_student=False)

    def test_notify_students_of_today_assignments_no_today_assignments(self):
        """
        Tets notify students of today assignments given no assignments for today
        """
        later = datetime.now(tz=pytz.UTC) + timedelta(days=4)
        user = test_utils.login(self, create_student=True)

        when(tools).get_events_from_calendar_all_classes(
            any, day=any, month=any, year=any
        ).thenReturn([])

        when(tools).get_events_from_calendar_all_classes(
            any, day=later.day, month=later.month, year=later.year
        ).thenReturn([create_date(year=later.year, month=later.month, day=later.day)])

        tools.notify_students_of_today_assignments()

        try:
            self.assertTrue(models.Notification.objects.all().count() == 0)
        finally:
            unstub()
            test_utils.logout(self, user)

    def test_notify_students_of_today_assignments_today_assignment(self):
        """
        Tets notify students of today assignments given a today assignment
        """
        user = test_utils.login(self)

        # this is to fix the weird date offset
        now = datetime.now(tz=pytz.UTC) - timedelta(days=1)

        when(tools).get_events_from_calendar_all_classes(
            any, day=any, month=any, year=any
        ).thenReturn([])

        when(tools).get_events_from_calendar_all_classes(
            any, day=now.day, month=now.month, year=now.year
        ).thenReturn([create_date(year=now.year, month=now.month, day=now.day)])

        tools.notify_students_of_today_assignments()

        print(models.Notification.objects.all().count())
        try:
            self.assertTrue(models.Notification.objects.all().count() == 1)
        finally:
            unstub()
            test_utils.logout(self, user)

    def test_get_events_from_calendar_all_classes_no_classes(self):
        """
        Tests the get events from calendar all classes method when the given student has no classes, no personal events
        """

        student = models.Student.objects.create(
            userId=0,
            classes=set(),
            calendarId=1234,
            color="#000000",
            class_colors=dict(),
        )

        when(tools).get_events_from_calendar(
            1234, day=None, month=None, year=None
        ).thenReturn([])

        try:
            self.assertEquals([], tools.get_events_from_calendar_all_classes(student))
        finally:
            unstub()
            models.Student.objects.all().delete()

    def test_get_events_from_calendar_all_classes_no_classes_personal_event(self):
        """
        Tests the get events from calendar all classes method when the given student has no classes, one personal event
        """

        student = models.Student.objects.create(
            userId=0,
            classes=set(),
            calendarId=1234,
            color="#000000",
            class_colors=dict(),
        )

        simulated_event = "Simulated event"

        when(tools).get_events_from_calendar(
            1234, day=None, month=None, year=None
        ).thenReturn([simulated_event])

        try:
            self.assertEquals(
                [simulated_event], tools.get_events_from_calendar_all_classes(student)
            )
        finally:
            unstub()
            models.Student.objects.all().delete()

    def test_get_events_from_calendar_all_classes(self):
        """
        Tests the get events from calendar all classes method when the given student has a class and a personal event
        """

        clazz = models.Class.objects.create(
            calendarId=5678, className="Class name", professorId=0
        )
        student = models.Student.objects.create(
            userId=0,
            classes={clazz},
            calendarId=1234,
            color="#000000",
            class_colors=dict(),
        )

        personal_event = "personal event"
        class_event = "class event"

        when(tools).get_events_from_calendar(
            1234, day=None, month=None, year=None
        ).thenReturn([personal_event])

        when(tools).get_events_from_calendar(
            5678, day=None, month=None, year=None, className="Class name"
        ).thenReturn([class_event])

        try:
            self.assertEquals(
                [personal_event, class_event],
                tools.get_events_from_calendar_all_classes(student),
            )
        finally:
            unstub()
            models.Student.objects.all().delete()
            models.Class.objects.all().delete()

    def test_create_event_calendar_exists(self):
        """
        Tests to make sure code queries google api to create correct event
        when calendar exists
        """

        summary = "good summary"

        when(tools).calendar_exists(any).thenReturn(True)

        # do not allow calendar creation
        when(tools).create_calendar(any).thenReturn(True)

        class TestPassed(Exception):
            pass

        when(services.calendar_service).events().thenRaise(TestPassed)

        request = mock({"user": mock({"id": 0})})

        when(tools).get_student(any).thenReturn(
            mock({"calendarId": 0, "classes": set()})
        )
        try:
            tools.create_event(
                request, summary, datetime.fromisoformat("2000-01-01"), isPersonal=True
            )
        except TestPassed:
            # we passed
            unstub()
            return
        unstub()
        self.assertTrue(False)

    def test_create_event_calendar_doesnt_exist_make_calendar(self):
        """
        Tests to make sure that, when a calendar doesnt exist, the code tries to make a calendar
        """
        from . import services

        summary = "good summary"

        when(tools).calendar_exists(any).thenReturn(False)

        class TestPassed(Exception):
            pass

        when(tools).create_calendar(any).thenRaise(TestPassed)

        try:
            tools.create_event(
                None, summary, None, (datetime.fromisoformat("2000-01-01"))
            )
        except TestPassed:
            # we passed
            unstub()
            return
        unstub()
        self.assertTrue(False)

    def test_create_event_for_class_calendar_exists(self):
        """
        Tests create event for the case where a class is supplied, and that class exists
        Should add event to that class calendar
        """

        summary = "good summary"
        className = "class"

        when(tools).calendar_exists(any).thenReturn(True)

        # do not allow calendar creation
        when(tools).create_calendar(any).thenReturn(True)

        class TestPassed(Exception):
            pass

        when(tools).get_class(className).thenReturn(mock({"calendarId": 1234}))

        # an instance of this will be returned when calling services.calendar_service.events()
        # that way, .events().insert will throw a TestPassed ONLY when called with the expected calendarId
        class Placeholder:
            def insert(*args, **kwargs):
                if kwargs["calendarId"] == 1234:
                    raise TestPassed

        when(services.calendar_service).events().thenReturn(Placeholder())

        request = mock({"user": mock({"id": 0})})

        when(tools).get_student(any).thenReturn(
            mock({"calendarId": 0, "classes": set()})
        )
        try:
            tools.create_event(
                request,
                summary,
                (datetime.fromisoformat("2000-01-01")),
                className=className,
            )
        except TestPassed:
            # we passed
            unstub()
            return
        unstub()
        self.assertTrue(False)

    def test_delete_event_calendar_exists(self):
        """
        Tests deleting an event in the case that the calendar exists. Makes sure delete is called
        """
        summary = "good summary"

        when(tools).calendar_exists(any).thenReturn(True)

        when(tools).get_student(any).thenReturn(mock({"calendarId": 1234}))

        # do not allow calendar creation
        when(tools).create_calendar(any).thenReturn(True)

        class TestPassed(Exception):
            pass

        when(services.calendar_service).events().thenRaise(TestPassed)

        try:
            # note, when we call delete event, the **string** none is what determines if it is no class
            # this is technically okay, since the minimum class name length is 5 characters
            # I dont like this but its 4 AM
            tools.delete_event(None, 1234, "None")
        except TestPassed:
            # we passed
            unstub()
            return
        unstub()
        self.assertTrue(False)

    def test_delete_event_class_calendar_exists_is_professor(self):
        """
        Tests deleting an event from a class in the case that the calendar exists. Makes sure delete is called
        Student is a professor
        """
        summary = "good summary"

        when(tools).calendar_exists(any).thenReturn(True)

        when(tools).get_student(any).thenReturn(mock({"calendarId": 1234}))

        when(tools).is_professor(any).thenReturn(True)

        clazz = models.Class.objects.create(
            className="name", calendarId=123, professorId=0
        )

        # do not allow calendar creation
        when(tools).create_calendar(any).thenReturn(True)

        class TestPassed(Exception):
            pass

        class Placeholder:
            def delete(*args, **kwargs):
                if kwargs["calendarId"] == "123":
                    raise TestPassed
                return None

        when(services.calendar_service).events().thenReturn(Placeholder())

        try:
            tools.delete_event(None, 1234, "name")
        except TestPassed:
            # we passed
            unstub()
            return
        unstub()
        self.assertTrue(False)

    def test_delete_event_class_calendar_exists_not_professor(self):
        """
        Tests deleting an event from a class in the case that the calendar exists. Makes sure delete is not called
        Student is a not a professor
        """
        summary = "good summary"

        when(tools).calendar_exists(any).thenReturn(True)

        when(tools).get_student(any).thenReturn(mock({"calendarId": 1234}))

        when(tools).is_professor(any).thenReturn(False)

        clazz = models.Class.objects.create(
            className="name", calendarId=123, professorId=0
        )

        # do not allow calendar creation
        when(tools).create_calendar(any).thenReturn(True)

        class TestFailed(Exception):
            pass

        class Placeholder:
            def delete(*args, **kwargs):
                if kwargs["calendarId"] == "123":
                    raise TestFailed
                return None

        when(services.calendar_service).events().thenReturn(Placeholder())

        try:
            tools.delete_event(None, 1234, "name")
        except TestFailed:
            # we failed
            self.assertTrue(False)
        finally:
            unstub()
            models.Class.objects.filter(className="name").delete()

    def test_delete_event_calendar_doesnt_exist(self):
        """
        Tests deleting an event in the case that the calendar doesnt exist exists. Makes sure api is never called
        """
        summary = "good summary"

        when(tools).calendar_exists(any).thenReturn(False)

        when(tools).get_student(any).thenReturn(mock({"calendarId": 1234}))

        # do not allow calendar creation
        when(tools).create_calendar(any).thenReturn(True)

        class TestFailed(Exception):
            pass

        when(services.calendar_service).events().thenRaise(TestFailed)

        try:
            tools.delete_event(None, 1234, None)
        except TestFailed:
            # we failed
            unstub()
            self.assertTrue(False)

        # we passed
        unstub()
        return

    def test_create_calendar_calendar_exists(self):
        """
        Tests the create_calendar method in the case where a calendar already exists
        Should not allow calendar creation
        """
        when(tools).calendar_exists(any).thenReturn(True)

        class TestFailed(Exception):
            pass

        when(services.calendar_service).calendars().thenRaise(TestFailed)

        try:
            tools.create_calendar(None)
        except TestFailed:
            # we failed
            unstub()
            self.assertTrue(False)

        # we passed
        unstub()
        return

    def test_create_calendar_calendar_doesnt_exist(self):
        """
        Tests the create_calendar method in the case where a calendar doesnt exist
        Should create calendar
        """
        when(tools).calendar_exists(any).thenReturn(False)

        class TestPassed(Exception):
            pass

        request = mock({"user": mock({"id": 0})})

        when(services.calendar_service).calendars().thenRaise(TestPassed)

        try:
            tools.create_calendar(request)
        except TestPassed:
            # we passed
            unstub()
            return
        unstub()
        self.assertTrue(False)

    def test_create_calendar_calendar_doesnt_exist_null_user(self):
        """
        Tests the create_calendar method in the case where a calendar doesnt exist
        AND the user is null
        Should not create calendar
        """
        when(tools).calendar_exists(any).thenReturn(False)

        class TestFailed(Exception):
            pass

        request = mock({"user": mock({"id": None})})

        when(services.calendar_service).calendars().thenRaise(TestFailed)

        try:
            tools.create_calendar(request)
        except TestFailed:
            # we failed
            unstub()
            self.assertTrue(False)

        # we passed
        unstub()
        return

    def test_get_event_calendar_exists(self):
        """
        Tests getting an event in the case that the calendar exists. Makes sure events is called
        """
        summary = "good summary"

        when(tools).calendar_exists(any).thenReturn(True)

        # do not allow calendar creation
        when(tools).create_calendar(any).thenReturn(True)

        when(tools).student_exists(any).thenReturn(True)

        class TestPassed(Exception):
            pass

        when(services.calendar_service).events().thenRaise(TestPassed)

        request = mock({"user": mock({"id": 0})})

        when(tools).get_student(any).thenReturn(
            mock({"calendarId": 0, "classes": set()})
        )

        try:
            tools.get_events(request)
        except TestPassed:
            # we passed
            unstub()
            return
        unstub()
        self.assertTrue(False)

    def test_get_event_calendar_doesnt_exist(self):
        """
        Tests getting an event in the case that the calendar doesnt exist exists. Makes sure api is never called
        """
        summary = "good summary"

        when(tools).calendar_exists(any).thenReturn(False)

        when(tools).get_student(any).thenReturn(mock({"calendarId": 1234}))

        # do not allow calendar creation
        when(tools).create_calendar(any).thenReturn(True)

        class TestFailed(Exception):
            pass

        when(services.calendar_service).events().thenRaise(TestFailed)

        request = mock({"user": mock({"id": 0})})

        when(tools).get_student(any).thenReturn(mock({"calendarId": 0}))

        try:
            tools.get_events(request, 1234)
        except TestFailed:
            # we failed
            unstub()
            self.assertTrue(False)

        # we passed
        unstub()
        return

    def test_get_date(self):
        """
        Tests getting the date for a request
        """

        request = get_request(self, "")

        # make sure the acquired dates are close
        self.assertTrue(
            datetime.now(tz=pytz.utc) - tools.get_date(request) < timedelta(seconds=1)
            and tools.get_date(request) - datetime.now(tz=pytz.utc)
            < timedelta(seconds=1)
        )

    def test_get_class_class_exists(self):
        """
        Tests the get class method in the case where a class exists
        """
        className = "good class name"
        clazz = models.Class.objects.create(className=className, professorId=0)

        try:
            self.assertEquals(tools.get_class(className), clazz)
        finally:
            models.Class.objects.filter(className=className).delete()

    def test_get_class_class_doesnt_exist(self):
        """
        Tests the get class method when the class does not exist
        Should return null
        """
        className = "good class name"
        self.assertEquals(tools.get_class(className), None)

    def test_get_student_student_is_none(self):
        """
        Tests the get student method when the user is the null user
        """

        request = mock({"user": mock({"id": None})})

        self.assertEquals(tools.get_student(request), None)

    def test_get_student_student_doesnt_exist(self):
        """
        Tests the get student method when the student for the given request is not registered
        """

        models.Student.objects.create(
            userId=0, classes=set(), color="#000000", class_colors=dict()
        )

        request = mock({"user": mock({"id": 1})})

        try:
            self.assertEquals(tools.get_student(request), None)
        finally:
            models.Student.objects.filter(userId=0).delete()

    def test_get_student_student_exists(self):
        """
        Tests the get_student method in the event that the student exists
        """

        student = models.Student.objects.create(
            userId=0, classes=set(), color="#000000", class_colors=dict()
        )

        request = mock({"user": mock({"id": 0})})

        try:
            self.assertEquals(tools.get_student(request), student)
        finally:
            models.Student.objects.filter(userId=0).delete()

    def test_student_exists_null_user(self):
        """
        Tests student_exists when user is the null user
        Should return false
        """

        request = mock({"user": mock({"id": None})})

        self.assertFalse(tools.student_exists(request))

    def test_student_exists_user_doesnt_exist(self):
        """
        Tests student_exists in the case where they do not exist
        """

        request = mock({"user": mock({"id": 0})})

        self.assertFalse(tools.student_exists(request))

    def test_student_exists_user_exists(self):
        """
        Tests student_exists when they do exist
        """

        student = models.Student.objects.create(
            userId=0, classes=set(), color="#000000", class_colors=dict()
        )

        request = mock({"user": mock({"id": 0})})

        try:
            self.assertTrue(tools.student_exists(request))
        finally:
            models.Student.objects.filter(userId=0).delete()

    def test_initialize_user_on_null_user(self):
        """
        Tests initialize user on the null user
        Should not initialize user
        """

        class TestFailed(Exception):
            pass

        when(models.Student.objects).create(userId=any, classes=any).thenRaise(
            TestFailed
        )

        request = mock({"user": mock({"id": None})})

        try:
            tools.initialize_user(request)
        except TestFailed:
            # we failed
            unstub()
            self.assertTrue(False)
        # we passed
        unstub()

    def test_initialize_user_on_new_user(self):
        """
        Tests initialize user on new user
        Should initialize user
        """

        class TestPassed(Exception):
            pass

        when(models.Student.objects).create(
            userId=0, classes=any, name=any, class_colors=any, description=any, mood=any,
        ).thenRaise(TestPassed)

        request = mock({"user": mock({"id": 0})})

        try:
            tools.initialize_user(request)
        except TestPassed:
            # we passed
            unstub()
            return
        # we failed
        unstub()
        self.assertTrue(False)

    def test_initialize_user_on_old_user(self):
        """
        Tests initialize user on an old user
        Should not initialize user
        """

        class TestFailed(Exception):
            pass

        # create a user so the student already exists
        models.Student.objects.create(
            userId=0, classes=set(), color="#000000", class_colors=dict()
        )

        when(models.Student.objects).create(userId=any, classes=any).thenRaise(
            TestFailed
        )

        request = mock({"user": mock({"id": 0})})

        try:
            tools.initialize_user(request)
        except TestFailed:
            # we failed
            unstub()
            # remove created user
            models.Student.objects.filter(userId=0).delete()
            self.assertTrue(False)
        # we passed
        unstub()
        # remove created user
        models.Student.objects.filter(userId=0).delete()

    def test_get_events_from_calendar_empty_calendar(self):
        """
        Tests the get events from calendar method in the case where the calendar is empty
        event list execute can be assumed to return a dicionary, dict['items'] = []
        """
        calendarId = 0

        # allows us to run .list(calendarId=calendarId).execute() and get an empty list
        class NestedPlaceholder:
            def execute(*args, **kwargs):
                return {"items": []}

        class Placeholder:
            def list(*args, **kwargs):
                if kwargs["calendarId"] == calendarId:
                    return NestedPlaceholder()
                return None

        when(services.calendar_service).events().thenReturn(Placeholder())

        try:
            self.assertEquals(tools.get_events_from_calendar(calendarId), [])
        finally:
            unstub()

    def test_get_events_from_calendar_empty_calendar(self):
        """
        Tests the get events from calendar method in the case where the calendar is empty
        event list execute can be assumed to return a dicionary, dict['items'] = []
        """
        calendarId = 0

        # allows us to run .list(calendarId=calendarId).execute() and get an empty list
        class NestedPlaceholder:
            def execute(*args, **kwargs):
                return {"items": []}

        class Placeholder:
            def list(*args, **kwargs):
                if kwargs["calendarId"] == calendarId:
                    return NestedPlaceholder()
                return None

        when(services.calendar_service).events().thenReturn(Placeholder())

        try:
            self.assertEquals(tools.get_events_from_calendar(calendarId), [])
        finally:
            unstub()

    def test_get_events_from_calendar_populated_calendar(self):
        """
        Tests the get events from calendar method in the case where the calendar has some events
        """
        calendarId = 0

        # allows us to run .list(calendarId=calendarId).execute() and get an empty list
        events = [
            {"start": {"dateTime": "2000-10-20"}, "end": {"dateTime": "2000-10-20"},},
            {"start": {"dateTime": "2001-10-20"}, "end": {"dateTime": "2001-10-20"},},
            {"start": {"dateTime": "2000-11-20"}, "end": {"dateTime": "2000-11-20"},},
        ]

        class NestedPlaceholder:
            def execute(*args, **kwargs):
                return {"items": events}

        class Placeholder:
            def list(*args, **kwargs):
                if kwargs["calendarId"] == calendarId:
                    return NestedPlaceholder()
                return None

        when(services.calendar_service).events().thenReturn(Placeholder())

        try:
            self.assertEquals(tools.get_events_from_calendar(calendarId), events)
        finally:
            unstub()

    def test_get_events_from_calendar_populated_calendar_with_time_filter(self):
        """
        Tests the get events from calendar method in the case where the calendar has some events
        Also filters events by year
        """
        calendarId = 0

        # allows us to run .list(calendarId=calendarId).execute() and get an empty list
        events = [
            {"start": {"dateTime": "2000-10-20"}, "end": {"dateTime": "2000-10-20"},},
            {"start": {"dateTime": "2001-10-20"}, "end": {"dateTime": "2001-10-20"},},
            {"start": {"dateTime": "2000-11-20"}, "end": {"dateTime": "2000-11-20"},},
        ]

        # filter events so year is 2000
        # also adds given class name, which, in this case, is None
        filtered_events = [
            {
                "start": {"dateTime": "2000-10-20"},
                "end": {"dateTime": "2000-10-20"},
                "className": None,
            },
            {
                "start": {"dateTime": "2000-11-20"},
                "end": {"dateTime": "2000-11-20"},
                "className": None,
            },
        ]

        class NestedPlaceholder:
            def execute(*args, **kwargs):
                return {"items": events}

        class Placeholder:
            def list(*args, **kwargs):
                if kwargs["calendarId"] == calendarId:
                    return NestedPlaceholder()
                return None

        when(services.calendar_service).events().thenReturn(Placeholder())

        try:
            self.assertEquals(
                tools.get_events_from_calendar(calendarId, year=2000), filtered_events
            )
        finally:
            unstub()

    def test_get_events_has_class(self):
        """
        Tests the get_events method in the case where the user with the request has classes
        """
        clazz = models.Class.objects.create(
            className="class1", calendarId="1", professorId=0,
        )
        classes = {clazz}
        models.Student.objects.create(
            userId=0,
            classes=classes,
            calendarId="0",
            color="#000000",
            class_colors=dict(),
        )
        # request for the new user
        request = mock({"user": mock({"id": 0})})

        class_events = [
            {"start": {"dateTime": "2000-10-20"}, "end": {"dateTime": "2000-10-20"},},
            {"start": {"dateTime": "2001-10-20"}, "end": {"dateTime": "2001-10-20"},},
            {"start": {"dateTime": "2000-11-20"}, "end": {"dateTime": "2000-11-20"},},
        ]

        student_events = [
            {"start": {"dateTime": "2002-10-20"}, "end": {"dateTime": "2002-10-20"},},
            {"start": {"dateTime": "2003-10-20"}, "end": {"dateTime": "2003-10-20"},},
        ]

        all_events = [
            {
                "start": {"dateTime": "2002-10-20"},
                "end": {"dateTime": "2002-10-20"},
                "className": None,
            },
            {
                "start": {"dateTime": "2003-10-20"},
                "end": {"dateTime": "2003-10-20"},
                "className": None,
            },
            {
                "start": {"dateTime": "2000-10-20"},
                "end": {"dateTime": "2000-10-20"},
                "className": "class1",
            },
            {
                "start": {"dateTime": "2001-10-20"},
                "end": {"dateTime": "2001-10-20"},
                "className": "class1",
            },
            {
                "start": {"dateTime": "2000-11-20"},
                "end": {"dateTime": "2000-11-20"},
                "className": "class1",
            },
        ]

        # this class is returned when querying for the class calendar id
        # will return class events
        class NestedPlaceholderClass:
            def execute(*args, **kwargs):
                return {"items": class_events}

        # this class is returned when querying for the student calendar id
        # will return student events
        class NestedPlaceholderStudent:
            def execute(*args, **kwargs):
                return {"items": student_events}

        class Placeholder:
            def list(*args, **kwargs):
                if kwargs["calendarId"] == "0":
                    return NestedPlaceholderStudent()
                elif kwargs["calendarId"] == "1":
                    return NestedPlaceholderClass()
                return None

        when(services.calendar_service).events().thenReturn(Placeholder())

        try:
            self.assertEquals(list(tools.get_events(request)), all_events)
        finally:
            unstub()
            models.Student.objects.filter(userId=0,).delete()
            models.Class.objects.filter(className="class1").delete()

    def test_add_class_null_user(self):
        """
        Tests adding a class to null user
        should not add class... if it tries, it will get a NoneType error
        So, this really just tests to make sure this method doesnt crash given a null user
        """

        request = mock({"user": mock({"id": None})})

        tools.add_class(request, "class name")

    def test_add_class_new_user(self):
        """
        Tests adding a class to an unregistered user
        Should not crash, should not add user
        """

        class TestFailed(Exception):
            pass

        request = mock({"user": mock({"id": 0})})

        # fail if we get to class addition section
        when(tools).get_student(request).thenRaise(TestFailed)

        try:
            tools.add_class(request, "class name")
        finally:
            unstub()

    def test_add_class_old_user(self):
        """
        Tests adding a class to a registered user
        Class should add successfully
        """

        clazz = models.Class.objects.create(className="class1", professorId=0)
        models.Student.objects.create(
            userId=0, classes=set(), color="#000000", class_colors=dict()
        )
        request = mock({"user": mock({"id": 0})})

        try:
            tools.add_class(request, "class1")

            # make sure the class was added
            self.assertTrue(clazz in tools.get_student(request).classes)
        finally:
            models.Student.objects.filter(userId=0).delete()
            models.Class.objects.filter(className="class1").delete()

    def test_remove_class_null_user(self):
        """
        Tests removing a class to null user
        should not remove class... if it tries, it will get a NoneType error
        So, this really just tests to make sure this method doesnt crash given a null user
        """

        request = mock({"user": mock({"id": None})})

        tools.remove_class(request, "class name")

    def test_remove_class_new_user(self):
        """
        Tests removing a class to an unregistered user
        Should not crash, should not remove class
        """

        class TestFailed(Exception):
            pass

        request = mock({"user": mock({"id": 0})})

        # fail if we get to class addition section
        when(tools).get_student(request).thenRaise(TestFailed)

        try:
            tools.remove_class(request, "class name")
        finally:
            unstub()

    def test_remove_class_old_user(self):
        """
        Tests removing a class to a registered user
        Class should remove successfully
        """

        clazz = models.Class.objects.create(className="class1", professorId=0)
        models.Student.objects.create(
            userId=0, classes={clazz}, color="#000000", class_colors=dict()
        )
        request = mock({"user": mock({"id": 0})})

        try:
            tools.remove_class(request, "class1")

            # make sure no class remains
            self.assertTrue(len(tools.get_student(request).classes) == 0)
        finally:
            models.Student.objects.filter(userId=0).delete()
            models.Class.objects.filter(className="class1").delete()

    def test_is_professor_null_user(self):
        """
        Tests the is professor method for the null user
        """

        request = mock({"user": mock({"id": None})})

        self.assertFalse(tools.is_professor(request))

    def test_is_professor_non_professor(self):
        """
        Tests the is professor method for a non professor
        """

        request = mock({"user": mock({"id": 0})})
        models.Student.objects.create(
            userId=0, classes=set(), color="#000000", class_colors=dict()
        )

        try:
            self.assertFalse(tools.is_professor(request))
        finally:
            models.Student.objects.filter(userId=0).delete()

    def test_is_professor_professor(self):
        """
        Tests the is professor method on a professor
        """

        request = mock({"user": mock({"id": 0})})
        models.Student.objects.create(
            userId=0,
            classes=set(),
            professor=True,
            color="#000000",
            class_colors=dict(),
        )

        try:
            self.assertTrue(tools.is_professor(request))
        finally:
            models.Student.objects.filter(userId=0).delete()

    def test_create_class_null_user(self):
        """
        Tests the create class method on the null user
        should not create a class
        """

        request = mock({"user": mock({"id": None})})

        class TestFailed(Exception):
            pass

        # if we even get to the point where we check if the class exists, then we failed
        when(models.Class.objects).filter(className=any).thenRaise(TestFailed)

        try:
            tools.create_class(request, "name", "basic class description")
        finally:
            unstub()

    def test_create_class_non_registered_user(self):
        """
        Tests the create class method on a non-registered user
        """

        request = mock({"user": mock({"id": 0})})

        class TestFailed(Exception):
            pass

        # if we even get to the point where we check if the class exists, then we failed
        when(models.Class.objects).filter(className=any).thenRaise(TestFailed)

        try:
            tools.create_class(request, "name", "basic class description")
        finally:
            unstub()

    def test_create_class_non_professor(self):
        """
        Tests the create class method on a non-professor
        """

        request = mock({"user": mock({"id": 0})})
        models.Student.objects.create(
            userId=0, classes=set(), color="#000000", class_colors=dict()
        )

        class TestFailed(Exception):
            pass

        # if we even get to the point where we check if the class exists, then we failed
        when(models.Class.objects).filter(className=any).thenRaise(TestFailed)

        try:
            tools.create_class(request, "name", "basic class description")
        finally:
            unstub()
            models.Student.objects.filter(userId=0).delete()

    def test_create_class_professor_class_exists(self):
        """
        Tests the create class method on a professor, when the class already exists
        """

        request = mock({"user": mock({"id": 0})})
        models.Student.objects.create(
            userId=0, classes=set(), color="#000000", class_colors=dict()
        )
        models.Class.objects.create(className="name", professorId=0)

        class TestFailed(Exception):
            pass

        # if we even get to the point where we create a calendar, then we failed
        when(services.calendar_service).calendars().thenRaise(TestFailed)

        try:
            tools.create_class(request, "name", "basic class description")
        finally:
            unstub()
            models.Student.objects.filter(userId=0).delete()
            models.Class.objects.filter(className="name").delete()

    def test_create_class_professor_class_doesnt_exist(self):
        """
        Tests the create class method on a professor, when the class doesnt exist
        Should successfully create class
        """

        request = mock({"user": mock({"id": 0})})
        models.Student.objects.create(
            userId=0, classes=set(), color="#000000", class_colors=dict()
        )

        class TestPassed(Exception):
            pass

        # if we create a calendar, then we passed
        when(services.calendar_service).calendars().thenRaise(TestPassed)

        # assume this student is a professor
        when(tools).is_professor(request).thenReturn(True)

        try:
            tools.create_class(request, "name", "basic class description")
        except TestPassed:
            # we passed
            return
        finally:
            unstub()
            models.Student.objects.filter(userId=0).delete()

        # we failed, we never tried creating a calendar
        self.assertTrue(False)

class ContextProcessorTests(TestCase):

    def test_is_professor_given_professor(self):
        """
        Tests the is_professor context given a professor request
        """

        user = test_utils.login(self, False)
        student = models.Student.objects.create(userId=user.id,
            calendarId=1,
            classes=set(),
            professor=True,
            class_colors=dict(),
            color="#000000")

        request = mock({'user': mock({'id': user.id})})

        try:
            self.assertTrue(context_processors.is_professor(request)['USER_IS_PROFESSOR'])
        finally:
            models.Student.objects.all().delete()
            test_utils.logout(self, user, False)

    def test_is_professor_given_no_professor(self):
        """
        Tests the is_professor context given a non-professor request
        """

        user = test_utils.login(self, False)
        student = models.Student.objects.create(userId=user.id,
            calendarId=1,
            classes=set(),
            class_colors=dict(),
            color="#000000",
            professor=False)

        request = mock({'user': mock({'id': user.id})})

        try:
            self.assertFalse(context_processors.is_professor(request)['USER_IS_PROFESSOR'])
        finally:
            models.Student.objects.all().delete()
            test_utils.logout(self, user, False)

    def test_is_professor_given_no_student(self):
        """
        Tests the is_professor context given a non-registered request
        """

        request = mock({'user': mock({'id': 0})})

        self.assertFalse(context_processors.is_professor(request)['USER_IS_PROFESSOR'])

    def test_get_class_color_null_user(self):
        """
        Tests getting a class color on the null user
        """

        request = test_utils.create_request(0)

        self.assertEquals("#0052bd", context_processors.get_class_color(request)['CLASS_COLOR'])

    def test_get_class_color_class(self):
        """
        Tests getting class color for a user with a class
        """

        user = login(self, create_student=False)
        clazz = models.Class.objects.create(calendarId=1, className="example", professorId=0)
        student = models.Student.objects.create(userId=user.id, classes={clazz}, class_colors={clazz: "#000000"})

        request = test_utils.create_request(user.id, className="example")

        try:
            self.assertEquals("#000000", context_processors.get_class_color(request)['CLASS_COLOR'])
        finally:
            models.Class.objects.all().delete()
            models.Student.objects.all().delete()
            logout(self, user, destroy_student=False)

    def test_is_assigned_professor_null_user(self):
        """
        Tests the is assigned professor context on the null user (cannot be a professor for a class)
        """

        clazz = models.Class.objects.create(calendarId=1, className="example", professorId=0)

        request = test_utils.create_request(0, className="example")

        try:
            self.assertFalse(context_processors.is_assigned_professor(request)['IS_ASSIGNED_PROFESSOR'])
        finally:
            models.Class.objects.all().delete()

    def test_is_assigned_professor_real_user_not_professor(self):
        """
        Tests checking if the current user is the assigned professor for a class when they are not
        """

        user = login(self, create_student=False)
        # make sure the professorId we choose is not the same as the user id
        professorId = 0
        if professorId == user.id:
            professorId = 1
        clazz = models.Class.objects.create(calendarId=1, className="example", professorId=professorId)
        student = models.Student.objects.create(userId=user.id, classes={clazz}, class_colors=dict(), professor=True)

        request = test_utils.create_request(user.id, className="example")

        try:
            self.assertFalse(context_processors.is_assigned_professor(request)['IS_ASSIGNED_PROFESSOR'])
        finally:
            models.Class.objects.all().delete()
            models.Student.objects.all().delete()
            logout(self, user, destroy_student=False)

    def test_is_assigned_professor_real_user_professor(self):
        """
        Tests checking if the current user is the assigned professor for a class when they are
        """

        user = login(self, create_student=False)
        # make sure the professorId we choose is the same as the user id
        professorId = user.id
        clazz = models.Class.objects.create(calendarId=1, className="example", professorId=professorId)
        student = models.Student.objects.create(userId=user.id, classes={clazz}, class_colors=dict(), professor=True)

        request = test_utils.create_request(user.id, className="example")

        try:
            self.assertTrue(context_processors.is_assigned_professor(request)['IS_ASSIGNED_PROFESSOR'])
        finally:
            models.Class.objects.all().delete()
            models.Student.objects.all().delete()
            logout(self, user, destroy_student=False)

    def test_is_my_class_null_user(self):
        """
        Tests checking if the current class belongs to the null user (it should not)
        """

        # make sure the professorId we choose is not the same as the user id
        professorId = 0
        clazz = models.Class.objects.create(calendarId=1, className="example", professorId=professorId)

        request = test_utils.create_request(0, className="example")

        try:
            self.assertFalse(context_processors.is_my_class(request)['IS_MY_CLASS'])
        finally:
            models.Class.objects.all().delete()

    def test_is_my_class_user_doesnt_belong(self):
        """
        Tests checking if the current class belongs to a user that does not have the current class
        """

        user = login(self, create_student=False)
        # make sure the professorId we choose is not the same as the user id
        professorId = 0
        if professorId == user.id:
            professorId = 1
        clazz = models.Class.objects.create(calendarId=1, className="example", professorId=professorId)
        student = models.Student.objects.create(userId=user.id, classes={}, class_colors=dict(), professor=True)

        request = test_utils.create_request(user.id, className="example")

        try:
            self.assertFalse(context_processors.is_my_class(request)['IS_MY_CLASS'])
        finally:
            models.Class.objects.all().delete()
            models.Student.objects.all().delete()
            logout(self, user, destroy_student=False)


    def test_is_my_class_user_does_belong(self):
        """
        Tests checking if the current class belongs to a user that does have the current class
        """

        user = login(self, create_student=False)
        # make sure the professorId we choose is not the same as the user id
        professorId = 0
        if professorId == user.id:
            professorId = 1
        clazz = models.Class.objects.create(calendarId=1, className="example", professorId=professorId)
        student = models.Student.objects.create(userId=user.id, classes={clazz}, class_colors=dict(), professor=True)

        request = test_utils.create_request(user.id, className="example")

        try:
            self.assertTrue(context_processors.is_my_class(request)['IS_MY_CLASS'])
        finally:
            models.Class.objects.all().delete()
            models.Student.objects.all().delete()
            logout(self, user, destroy_student=False)
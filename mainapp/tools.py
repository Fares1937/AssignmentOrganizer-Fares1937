import pytz
from . import services
from . import models
import datetime
import logging
from django.contrib.auth.models import User
from django.template import Context, Template

# calendar api query documentation : https://developers.google.com/calendar/api

logger = logging.getLogger(__name__)


def get_student(request):
    """
    Gets the student model that corresponds to the user id for the current request
    """
    return models.Student.objects.filter(userId=request.user.id).first()


def get_class(className):
    """
    Gets the class that corresponds to the class name
    """
    return models.Class.objects.filter(className=className).first()


def class_exists(className):
    """
    Returns whether or not a class exists with a certain class name
    """
    return 0 != models.Class.objects.filter(className=className).count()


def class_exists_for_student(request, className):
    """
    Returns whether or not a class exists with a certain class name
    """
    if not student_exists(request):
        return False
    if not class_exists(className):
        return False
    return get_class(className) in get_student(request).classes


def is_professor_for_class(request, className):
    """
    Returns whether or not the corresponding request owner is the professor for a class with classname className
    """
    if not student_exists(request):
        return False
    # if this is a personal calendar, we have full rights on it
    if str(className) == "None":
        return True
    if not class_exists(className):
        return False
    student = get_student(request)
    return get_class(className).professorId == student.userId

def is_admin_of_event(request, event):
    """
    Returns whether or not the corresponding request owner is the creator of some event
    """
    if not student_exists(request):
        return False
    
    if is_professor_for_class(request, event['className']):
        return True

    if event['organizer']['email'] == get_student(request).calendarId:
        return True

    return False


def student_exists(request):
    """
    Determines if there is a student with an id tied to this request
    """
    return (
        request.user.id != None
        and models.Student.objects.filter(userId=request.user.id).count() != 0
    )


def initialize_user(request):
    """
    Initializes the current user if they are not currently initialized
    """
    if not request.user.id == None and not student_exists(request):
        models.Student.objects.create(
            userId=request.user.id,
            classes=set(),
            name=request.user.username,
            class_colors=dict(),
            description=default_description(request.user.email),
            mood = "UVA Student",
        )
        print("Initialized new student")
    else:
        print(
            "Student is either already addressed with system or they are the null user"
        )


def create_event(request, summary, time, className=None, isPersonal=False):
    """
    NOTE: We keep description as a parameter temporarily, until the time-length has been phased to classname
    Creates an event for the current users calendar given a summary (string) description (string representation of an int) and time (datetime object, not localized)
    If calendar does not exist, do nothing
    """
    create_calendar(request)
    time = pytz.utc.localize(time)
    if not calendar_exists(request):
        print("Invalid user to create event")
        return
    if isPersonal:
        print("Creating personal event")
    else:
        print("Creating public event for", className)

    if isPersonal:
        calendarId = get_student(request).calendarId
    else:
        calendarId = get_class(className).calendarId

    event = (
        services.calendar_service.events()
        .insert(
            calendarId=calendarId,
            body={
                "summary": summary,
                "description": str(className),
                "start": {"dateTime": time.isoformat()},
                "end": {"dateTime": (time + datetime.timedelta(days=1)).isoformat()},
            },
        )
        .execute()
    )
    print("Event created for user")


def delete_event(request, id, clazz):
    """
    Deletes an event from current users calendar given id
    If calendar does not exist, do nothing
    If clazz is the string "None" then this is for the personal calendar
    FIXME
    I don't like this, but its kindof the only option I can think of right now
    """
    if not calendar_exists(request):
        print("Cannot delete event for user with no calendar")
        return
    print("Deleting event")
    if clazz == "None":
        calendarId = get_student(request).calendarId
    else:
        if not is_professor(request):
            print("Cannot delete assignment from this class, not a professor")
            return
        calendarId = get_class(clazz).calendarId
    services.calendar_service.events().delete(
        calendarId=calendarId, eventId=id
    ).execute()


def create_calendar(request):
    """
    Create a calendar for the user querying the request, if they do not already have one
    """

    if calendar_exists(request):
        print(
            "Cannot create calendar for this user. Either null, or they have a calendar"
        )
        return

    if request.user.id == None:
        print("Cannot create calendar for null user")
        return
    print("Creating calendar for new user...")
    calendar = {
        "summary": "assignment organizer",
        "timeZone": "America/New_York",
    }

    # FIXME This try-catch will be ommitted until the exception type is found.
    # if this throws an exception, please fill it in on 120
    # having this try-catch without a specified exception breaks some tests
    # try:
    created_calendar = (
        services.calendar_service.calendars().insert(body=calendar).execute()
    )
    # except:
    #     print("Calendar creation quota error")
    #     return

    # add the calendar to this student model
    student = get_student(request)
    student.calendarId = created_calendar["id"]
    student.save()
    print("Calendar created for a user")


def calendar_exists(request):
    return (
        request.user.id != None
        and models.Student.objects.filter(userId=request.user.id).count() != 0
        and get_student(request).calendarId != ""
    )


def get_events_from_calendar(
    calendarId, day=None, month=None, year=None, className=None
):
    """
    Returns all events during specified day month year from calendar with calendarId
    If any of those are none, it does not filter. 
    Also, will assign className className to each event, if specified
    This way, calendar view can determine a potential color code for classes
    """
    events = services.calendar_service.events().list(calendarId=calendarId).execute()
    events = events["items"]

    if day != None:
        events = [
            event
            for event in events
            if datetime.datetime.fromisoformat(event["end"]["dateTime"]).day == day
        ]

    if month != None:
        events = [
            event
            for event in events
            if datetime.datetime.fromisoformat(event["end"]["dateTime"]).month == month
        ]

    if year != None:
        events = [
            event
            for event in events
            if datetime.datetime.fromisoformat(event["end"]["dateTime"]).year == year
        ]

    for event in events:
        event["className"] = className

    return events


def get_events_from_calendar_all_classes(student, day=None, month=None, year=None):
    events = get_events_from_calendar(
        student.calendarId, day=day, month=month, year=year,
    )

    for clazz in student.classes:
        print(clazz.className)
        events += get_events_from_calendar(
            clazz.calendarId,
            day=day,
            month=month,
            year=year,
            className=clazz.className,
        )
    return events


def get_events(request, day=None, month=None, year=None):
    """
    Gets all events from a calendar associated with the user making the current request
    **change** also returns all events from class calendars
    """
    create_calendar(request)

    if not student_exists(request):
        print("Student does not exist, cannot get events")
        return
    print("Getting events for student")

    student = get_student(request)

    return get_events_from_calendar_all_classes(
        student, day=day, month=month, year=year
    )


def get_all_events(request, className=None):
    """
    Returns all events from user belonging to request and from classname classname
    """
    if not student_exists(request):
        return []

    student = get_student(request)
    calendarIds = [(student.calendarId, None)]
    if className != None:
        calendarIds.append((get_class(className).calendarId, className))
    else:
        for clazz in student.classes:
            calendarIds.append((clazz.calendarId, clazz.className))

    events = []
    for calendarId, name in calendarIds:
        events += get_all_events_from_calendar(calendarId, name)

    return [event for event in events if event['description'] == str(className) or str(className) == 'None']


def get_all_events_from_calendar(calendarId, className=None):
    """
    Returns all events from a given calendar
    """
    print(datetime.datetime.now().isoformat())
    print(calendarId)
    events = services.calendar_service.events().list(calendarId=calendarId).execute()
    events = events["items"]

    for event in events:
        event["className"] = className

    return events


def get_date(request):
    """
    Gets a datetime object for when the request was put out
    """
    req_day = request.GET.get("day", None)
    if req_day:
        year, month = (int(x) for x in req_day.split("-"))
        return datetime.date(year, month, day=1)
    return datetime.datetime.now(tz=pytz.utc)


def add_class(request, className):
    """
    Adds the class with class name className to the student whose id is associated with this request
    """
    if not student_exists(request):
        print("Cannot add a class to a student that does not exist")
        return

    student = get_student(request)
    class_set = student.classes
    class_colors = student.class_colors
    class_set.add(get_class(className))
    class_colors[get_class(className)] = "#0052bd"
    student.save()


def remove_class(request, className):
    """
    Removes the class with class name className to the student whose id is associated with this request
    """
    if not student_exists(request):
        print("Cannot remove a class to a student that does not exist")
        return

    student = get_student(request)
    class_set = student.classes
    class_set.remove(get_class(className))
    student.save()


def is_professor(request):
    """
    Returns whether or not the user associated with the current request is a professor
    """

    return student_exists(request) and get_student(request).professor


def create_class(request, name, description):
    """
    Creates a class given string name. 
    **only** usable if this is a professor
    """

    if not is_professor(request):
        print("Cannot create a class if user is not a professor")
        return

    # if class already exists with this name, do not create class
    if models.Class.objects.filter(className=name).count() != 0:
        print("Cannot create a new class, class with this name exists")
        return

    # create a calendar for the new class
    print("Creating calendar for new class")
    calendar = {
        "summary": "assignment organizer",
        "timeZone": "America/New_York",
    }

    # try:
    # FIXME We are temporarily commenting out the try-catch to fix tests
    # if the actual exception thrown here is found, please uncomment the try-catch and except that exception
    created_calendar = (
        services.calendar_service.calendars().insert(body=calendar).execute()
    )
    # except:
    #     print("Calendar creation quota error")
    #     return

    print("Class created")
    models.Class.objects.create(
        className=name,
        calendarId=created_calendar["id"],
        description=description,
        professorId=get_student(request).userId,
    )


def upload_syllabus(request, form, className):
    csv_file = request.FILES["file"].read().decode("utf-8")
    line_count = 0
    for line in csv_file.splitlines():
        line = line.strip()
        ls = line.split(",")
        name = ls[0].strip()
        date = ls[1].strip()
        duration = ls[2].strip()
        datetime_object = datetime.datetime.strptime(date, "%Y-%m-%d")
        line_count += 1
        create_event(request, name, datetime_object, className)
        logger.error(f"{name}, {date}, {duration}")
    logger.error(f"Processed {line_count} lines.")


def send_message(userId, text):
    """
    Adds an email to the message queue. Will be sent at a later time,
    perhaps, every hour.
    """
    try:
        email = User.objects.filter(id=userId).first().email
        print("Model added")
        models.Notification.objects.create(email=email, text=text)
    except:
        import traceback

        traceback.print_exc()
        print(f"Failed to send email to userId {userId}")


def send_all_messages():
    """
    Sends out all messages defined in Notification objects
    """

    notifs = models.Notification.objects.all()

    print(f"Sending out {len(notifs)} emails...")
    for notif in notifs.iterator():
        services.email_service.message(
            text=notif.text, to=notif.email, subject="Assignment Organizer"
        )

    models.Notification.objects.all().delete()

    print("Email sending successful!")


def get_all_students(className):
    """
    Returns a list of all students who have a class who's name is className
    """
    ret = []

    clazz = models.Class.objects.filter(className=className).first()
    for student in models.Student.objects.all().iterator():
        if clazz in student.classes:
            ret.append(student)

    return ret


def notify_students_of_change(className, assignmentName, action):
    """
    Notifies all students of a className that an assignment has changed
    """
    print(get_all_students(className))
    for student in get_all_students(className):
        send_message(
            student.userId,
            f"""
Dear {student.name},<br>
<br>
An assignment has been updated in one of your classes:<br>
<br>
Assignment '{assignmentName}' was {action}d for class '{className}'.<br>
<br>
We hope you have a great day,<br>
Assignment Organizer
            """,
        )


def notify_students_of_today_assignments():
    """
    Notifies all students of assignments marked as due today
    """
    now = datetime.datetime.now(tz=pytz.UTC)

    # this is to fix a weird date offset where dates are being reported as one day in advance
    now = now - datetime.timedelta(days=1)

    for student in models.Student.objects.all().iterator():
        events = get_events_from_calendar_all_classes(
            student, day=now.day, month=now.month, year=now.year
        )
        if len(events) != 0:
            print("Sending daily assignment update")
            events.sort(
                key=lambda x: "None" if x["className"] == None else x["className"]
            )
            last_class = events[0]["className"]
            last_class_str = "Personal" if last_class == None else last_class
            event_string = f"For {last_class_str}:<br>"
            for event in events:
                if last_class != event["className"]:
                    last_class = event["className"]
                    last_class_str = "Personal" if last_class == None else last_class
                    event_string += f"For {last_class_str}:<br>"
                event_string += f"&emsp;{event['summary']}<br>"
            send_message(
                student.userId,
                f"""
Dear {student.name},<br>
<br>
You have some assignments due today:<br>
<br>
{event_string}<br>
<br>
Good luck on your classes,<br>
Assignment Organizer
            """,
            )


def get_argv():
    import sys

    print(sys.argv)


def set_class_color(request, className, color):
    """
    Sets the color of the class with class name to the user belonging to request with new color
    """
    student = get_student(request)
    if className == None:
        student.color = color
    else:
        student.class_colors[get_class(className)] = color
    print("Saving color", color, "for class", className)
    student.save()


def get_color(request, className=None):
    """
    Returns the class color for a class className (if provided) otherwise, default color
    """
    return (
        ("#0052bd" if not student_exists(request) else get_student(request).color)
        if className == None or not class_exists_for_student(request, className)
        else get_student(request).class_colors[get_class(className)]
    )


def className_from_url(request):
    """
    Attempts to parse a string classname from a request url
    """
    url = str(request.get_full_path()).replace("%20", " ")
    if "classes" not in url:
        return None
    try:
        url = url[url.index("classes/") + 8 :]
        url = url[: url.index("/")]
    except:
        return None
    if not class_exists(url):
        return None
    return url


def num_days_until(date_string):
    """
    Returns the number of days until date_string
    """
    then = datetime.datetime.fromisoformat(date_string).replace(tzinfo=None)
    now = datetime.datetime.now().replace(tzinfo=None)
    diff = then - now
    return diff.days


def days_until_string(date_string):
    """
    Returns a string form of num_days_until
    """
    diff = num_days_until(date_string)

    if diff == 0:
        return "Due Today"
    elif diff == 1:
        return "Due in 1 Day"
    elif diff == -1:
        return "Due 1 Day Ago"
    elif diff < 0:
        return f"Due {-diff} Days Ago"
    else:
        return f"Due in {diff} Days"


def is_checked_off(request, event):
    """
    Determines if a student checked off this assignment, signifying they have completed it
    """
    student_id = get_student(request).userId
    return (
        models.CheckedAssignments.objects.filter(
            userId=student_id, className=str(event['className']), eventId=event['id']
        ).count()
        != 0
    )


def todo_list(request, className=None, editable=False, todo_loc=False):
    """
    Returns an HTML display for a todo list to be displayed on any page
    editable iff editable (checkable, deletable)
    if corresponding event is authenticated professor for user, deletable
    otherwise, checkable
    todo_loc is used to modify the URL to work for todo list edits
    """
    if not student_exists(request):
        return None
    events = sorted(
        get_all_events(request, className),
        key=lambda event: datetime.datetime.fromisoformat(event["end"]["dateTime"]),
    )

    past_events = [
        event for event in events if num_days_until(event["end"]["dateTime"]) < 0
    ]
    future_events = [
        event for event in events if num_days_until(event["end"]["dateTime"]) >= 0
    ]

    ret = assignment_html(request, future_events, className, editable, todo_loc)
    if len(past_events):
        ret += '<h5 style="text-align:center; width:100%;">Past-Due Assignments:</h5>'
        ret += assignment_html(request, past_events, className, editable, todo_loc)
    return ret


def assignment_html(request, events, className=None, editable=False, todo_loc=False):
    """
    Given events list, displays html assignment format
    """
    ret = ""
    for i, event in enumerate(events):

        ret += f"""<div class="container">
        <div class="container" style="{"" if not is_checked_off(request, event) else "text-decoration: line-through;"} border-radius:1.5vh; background-color:{get_color(request, event['description'])};
        font-size:1.2vw; color:{"white" if not is_checked_off(request, event) else "gray"}; padding-left:5%; margin-bottom: 10px;">
        <div class="item" style="width:30%;overflow-wrap: break-word;">{event['summary']}</div>"""
        if className == None:
            ret += f"""
            <div style="text-align:center;overflow-wrap: break-word;" class="item">{event['description'] if str(event['description']) != "None" else "Personal"}</div>"""
        ret += f"""
        <div class="item" style="padding-right:5%;width:30%;text-align:right;overflow-wrap: break-word;">{days_until_string(event['end']['dateTime'])}</div>
        """
        ret += "</div>"

        if editable:

            ret += f"""<a href="{event['className']}/{event['id']}/delete_assignment/check/">
            """

            ret += f"""<button style="right:-20%; border-radius:80px;color:white;
            background-color:green; border:none;width:20%;font-size:1.2vw;position:absolute;"><i class='bx bx-{'check-' if is_checked_off(request, event) else ''}square'></i> Check Off</button></a>"""

        if editable and (is_admin_of_event(request, event)):
            ret += f"""<a href="{event['className']}/{event['id']}/delete_assignment/delete/">
            """
            ret += f"""<button style="left:-20%; border-radius:80px;color:white;
            background-color:red; border:none;width:20%;font-size:1.2vw;position:absolute;"><i class='bx bx-trash'></i>    Delete</button></a>"""
        ret += "</div>"
    return ret


def check_off(request, event_id, className):
    """
    Checks off assignment with event id and classname for the student
    """
    student_id = get_student(request).userId
    if is_checked_off(request, {"id" : event_id, 'className': className}):
        print("Assignment for class", className, "is already checked off")
        models.CheckedAssignments.objects.filter(
            userId=student_id, className=className, eventId=event_id
        ).delete()
        return
    print("Checking off", className, "assignment with type", type(className))
    models.CheckedAssignments.objects.create(
        userId=student_id, className=className, eventId=event_id
    )


def list_members_of_class(className):
    """
    Returns a list of every member of a class
    """
    if not class_exists(className):
        return []

    clazz = get_class(className)
    all_students = models.Student.objects.all()
    ret = []

    for student in all_students.iterator():
        if clazz in student.classes:
            ret.append(student)

    return ret

def get_user_with_id(userId):
    """
    Returns a student object given their unique id
    """
    if not user_with_id_exists(userId):
        return None
    return models.Student.objects.filter(userId=userId).first()

def user_with_id_exists(userId):
    """
    Returns whether or not a user with a specific ID exists
    """
    return models.Student.objects.filter(userId=userId).count() != 0

def default_description(email):
    """
    Creates a default description for a user's user page
    """
    return f"""
    <div class="container">
        <div>
            <label>Email</label>
        </div>
        <div>
            <p style="font-weight: 600; color: #0062cc;">{email}</p>
        </div>
    </div>
    
    """

def parse_description_to_text(description):
    """
    Parses html form description into a readable text format
    """
    desc_list = description.split("<div class=\"container\">")[1:]
    ret = ""
    p_before = '''<p style="font-weight: 600; color: #0062cc;">'''
    for desc in desc_list:
        key = desc[desc.index("<label>") + 7: desc.index("</label>")]
        value = desc[desc.index(p_before) + len(p_before): desc.index("</p>")]
        ret += f"{key}:{value}\n"
    return ret[:-1]

def parse_description_to_html(description):
    """
    Parses readable text format description into a html displayable format
    """
    desc_list = description.split("\n")
    ret = ""
    for desc in desc_list:
        if desc == "":
            continue
        key = desc[:desc.index(":")]
        value = desc[desc.index(":") + 1:]
        ret += f"""
        <div class="container">
        <div>
            <label>{key}</label>
        </div>
        <div>
            <p style="font-weight: 600; color: #0062cc;">{value}</p>
        </div>
    </div>
        """
    return ret

def get_username(request):
    """
    Returns the username for a request
    """
    if not student_exists(request):
        return "Log In"
    
    return get_student(request).name
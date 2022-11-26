from io import TextIOWrapper
import logging
from django.core.exceptions import ValidationError
from django.forms.widgets import SelectDateWidget
from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from . import tools, models, forms
from .calendar_generator import Calendar
from django.utils.safestring import mark_safe
from django.urls import reverse
import datetime as dt
from datetime import datetime
import django
import csv
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from .forms import FileForm
from django.shortcuts import redirect
from .models import File
from .models import FileFilter
from django.core.validators import RegexValidator

logger = logging.getLogger(__name__)

# Create your views here.
# NOTE ALWAYS use initialize_user(request) at the beginning of a view to make sure current user is valid


def index(request):
    """
    Basic home page
    """
    tools.initialize_user(request)
    # this is now needed because calendar is required to view home page
    tools.create_calendar(request)
    if tools.student_exists(request):
        todo = tools.todo_list(request)
        return render(
            request,
            "mainapp/index.html",
            {"todo": mark_safe(todo), "has_todo": len(todo) != 0, "student": tools.get_student(request)},
        )
    else:
        return render(request, "mainapp/index.html")


def calendar_view(request, month_id=None):
    """
    Shows calendar with events, and check marks for what events are to be deleted
    """
    tools.initialize_user(request)
    # make a calendar for this user. If they already have a calendar, this will do nothing.
    # if this is the null user, this will also do nothing. Will redirect home if calendar
    # still failed creation
    tools.create_calendar(request)

    # calendar failed to be created. head to index page
    if not tools.calendar_exists(request):
        return render(request, "mainapp/index.html", {"ERR_NOT_LOGGED_IN": True})

    # use today's date for the calendar
    d = tools.get_date(request)
    print("------")
    print(month_id)
    if month_id != None and month_id <= 0:
        return calendar_view(request)
    if month_id != None:
        if month_id % 12 == 0:
            d = d.replace(month=12, day=1, year=int(month_id / 12) - 1)
        else:
            d = d.replace(month=int(month_id % 12), day=1, year=int(month_id / 12))
    else:
        month_id = d.month + 12 * d.year
    # Instantiate our calendar class with today's year and date
    cal = Calendar(d.year, d.month)

    # Call the formatmonth method, which returns our calendar as a table
    html_cal = cal.formatmonth(request=request, withyear=True)
    args = {}
    args["calendar"] = mark_safe(html_cal)
    args["next_month"] = month_id

    m = tools.get_date(request)

    return TemplateResponse(request, "mainapp/calendar.html", args)


def prev_month(request, month_id):
    """
    Returns to previous month on calendar
    """
    tools.initialize_user(request)
    return calendar_view(request, month_id=month_id - 1)


def next_month(request, month_id):
    """
    Returns to next month on calendar
    """
    tools.initialize_user(request)
    return calendar_view(request, month_id=month_id + 1)


def classes(request):
    """
    A list of classes associated with the current user
    """
    print(request.user.id)
    tools.initialize_user(request)

    if not tools.student_exists(request):
        return render(request, "mainapp/index.html", {"ERR_NOT_LOGGED_IN": True})

    class_list = sorted(
        list(tools.get_student(request).classes), key=lambda clazz: clazz.className
    )
    return render(
        request,
        "mainapp/classes.html",
        {"class_list": class_list},
    )


def remove_classes(request, className=None):
    """
    Hidden page that handles removing classes from classes view page
    """
    tools.initialize_user(request)

    if not tools.student_exists(request):
        return render(request, "mainapp/index.html", {"ERR_NOT_LOGGED_IN": True})

    if className == None:
        return HttpResponseRedirect(reverse("index"))

    tools.remove_class(request, className)

    # Always return an HttpResponseRedirect after successfully dealing
    # with POST data. This prevents data from being posted twice if a
    # user hits the Back button.
    return HttpResponseRedirect(request.META.get("HTTP_REFERER"))


def all_classes(request):
    """
    A list of all registered classes
    """
    tools.initialize_user(request)

    if not tools.student_exists(request):
        return render(request, "mainapp/index.html", {"ERR_NOT_LOGGED_IN": True})

    class_list = list(models.Class.objects.all())
    class_list = [
        clazz for clazz in class_list if clazz not in tools.get_student(request).classes
    ]
    class_list = sorted(class_list, key=lambda clazz: clazz.className)
    return render(
        request,
        "mainapp/all_classes.html",
        {
            "class_list": class_list,
            "my_classes": sorted(
                list(tools.get_student(request).classes),
                key=lambda clazz: clazz.className,
            ),
        },
    )


def add_classes(request, className):
    """
    Hidden page that handles adding classes from all_classes view page
    """
    tools.initialize_user(request)

    if not tools.student_exists(request):
        return render(request, "mainapp/index.html", {"ERR_NOT_LOGGED_IN": True})

    if className == None:
        return HttpResponseRedirect(reverse("index"))

    tools.add_class(request, className)

    # Always return an HttpResponseRedirect after successfully dealing
    # with POST data. This prevents data from being posted twice if a
    # user hits the Back button.
    return HttpResponseRedirect(reverse("all_classes"))


def delete_assignment(request, className, event_id, action, untrueClassName=None):
    """
    Hidden page that handles deleting (or checking off) assignments
    untrueClassName parses the public classname for an assignment, but we dont care
    about the public name
        We only care about the private name here, so we can grab the calendar
        className (see tools creating assignment list code) will grab the true
        class name for an assignment
        True name is always the same, except for in the case where the assg is a private
        assg for a class.
    """
    tools.initialize_user(request)

    if not tools.student_exists(request):
        return render(request, "mainapp/index.html", {"ERR_NOT_LOGGED_IN": True})
    
    print("Class Name", className)
    print("Event ID", event_id)

    if action == "delete":
        tools.delete_event(request, event_id, className)
    elif action == "check":
        tools.check_off(request, event_id, className)
    return HttpResponseRedirect(request.META.get("HTTP_REFERER"))


def add_assignment(request, className=None):
    """
    Form page to add assignments to calendar
    """
    # save the classname for later (for determining redirect)
    origin_className = className
    tools.initialize_user(request)
    # if this is a post, then add assignment
    if not tools.student_exists(request):
        return render(request, "mainapp/index.html", {"ERR_NOT_LOGGED_IN": True})

    # ---------class definition for AddAssignment form---------- #
    # FIXME I hate this, but it is the only way I can think to provide request arguments
    # for the structure of this class. Anyone have any idea to not put this here?
    class AddAssignment(django.forms.Form):
        def no_slash(chosen_name):
            if "/" in chosen_name or "\\" in chosen_name:
                raise ValidationError("Cannot have assignment names with slashes")

        def no_illegal_name(chosen_name):
            if (
                chosen_name == "None"
                or chosen_name == "none"
                or chosen_name == "Personal"
                or chosen_name == "personal"
            ):
                raise ValidationError(
                    "This name is reserved, and cannot be used for a class name"
                )

        summary = django.forms.CharField(
            widget=django.forms.Textarea(
                attrs={
                    "cols": 50,
                    "rows": 1,
                    "style": "border-radius: 7px; border-color: black;margin-bottom:10px",
                }
            ),
            label="Assignment name:",
            max_length=50,
            required=True,
            # https://stackoverflow.com/questions/17165147/how-can-i-make-a-django-form-field-contain-only-alphanumeric-characters
            validators=[no_slash, no_illegal_name,],
        )
        time = django.forms.DateField(
            input_formats=("%Y-%m-%d",),
            widget=forms.DateInput(
                attrs={
                    "cols": 50,
                    "rows": 1,
                    "style": "border-radius: 7px; border-color: black;margin-bottom:10px;",
                }
            ),
            # widget=django.forms.Textarea(
            #     attrs={
            #         "cols": 50,
            #         "rows": 1,
            #         "style": "border-radius: 7px; border-color: black;padding-bottom:10px;",
            #     }
            # ),
            label="Date of assignment",
            required=True,
            
        )
        # if we are looking at a personal assignment creation, give the user a choice of class
        if str(className) == "None":
            classNames = [("Personal", "Personal")]
            classNames += [
                (str(className), str(className))
                for className in tools.get_student(request).classes
            ]
            calendar = django.forms.CharField(
                label="Calendar for this assignment",
                widget=django.forms.Select(choices=classNames),
            )

    # ------------ end class definition ------------- #

    if request.method == "POST":
        # gather the form
        form = AddAssignment(request.POST)
        # check whether the form fits the constraints:
        if form.is_valid():
            # save the assignment

            # get the class. If calendar was not on the form (not a professor) or
            # the professor chose personal, then no class
            # otherwise, it is a professor and they specified a class, pass it on
            if str(className) == "None":
                className = form.data["calendar"]

            # parse classname to real none if it is str none
            if className == "None":
                className = None

            tools.create_event(
                request,
                form.data["summary"],
                datetime.fromisoformat(form.data['time']),
                className=className,
                isPersonal=((str(origin_className)=='None'))
            )

            # notify students of event creation, if class is not personal
            # reassign to original classname, we do not want to notify other students if personal
            className = origin_className
            if className != None:
                tools.notify_students_of_change(
                    className, form.data["summary"], "create"
                )
            # redirect to the calendar
            if str(className) == "None":
                return HttpResponseRedirect(reverse("todo"))
            return HttpResponseRedirect(
                reverse("view_class", kwargs={"className": className})
            )

    # create a blank form
    else:
        form = AddAssignment()
    # display the webpage (if it was not a post)
    return render(
        request, "mainapp/addassignment.html", {"form": form, "className": className}
    )


def create_class(request):
    """
    View for creating a class. This view is **only** usable by a professor.
    """
    tools.initialize_user(request)

    if not tools.student_exists(request):
        return render(request, "mainapp/index.html", {"ERR_NOT_LOGGED_IN": True})

    # student is trying to create a class... dont let them! Bring them back home
    if not tools.is_professor(request):
        return HttpResponseRedirect(reverse("index"))

    # if this is a post, then add assignment
    if request.method == "POST":
        # gather the form
        form = forms.CreateClass(request.POST)
        # check whether the form fits the constraints:
        if form.is_valid():
            # save the class
            tools.create_class(request, form.data["name"], form.data["description"])

            # add the class for this professor
            tools.add_class(request, form.data["name"])
            # redirect to all class list
            return HttpResponseRedirect(reverse("classes"))

    # create a blank form
    else:
        form = forms.CreateClass()
    # display the webpage (if it was not a post)
    return render(request, "mainapp/create_class.html", {"form": form})


def upload_schedule(request, className):
    """
    View for creating a class. This view is **only** usable by a professor.
    """
    tools.initialize_user(request)
    if not tools.student_exists(request):
        return render(request, "mainapp/index.html", {"ERR_NOT_LOGGED_IN": True})
    # if this is a post, then upload a schedule
    class UploadSyllabus(django.forms.Form):
        file = django.forms.FileField()

    if request.method == "POST" and request.FILES:
        print(request)
        # gather the form
        form = UploadSyllabus(request.POST, request.FILES)
        # check whether the form fits the constraints:
        if form.is_valid():
            # save the class
            tools.upload_syllabus(request, form, className)
            if str(className) == "None":
                return HttpResponseRedirect(reverse("todo"))
            return HttpResponseRedirect(
                reverse("view_class", kwargs={"className": className})
            )

    # create a blank form
    else:
        form = UploadSyllabus()
    # display the webpage (if it was not a post)
    return render(
        request, "mainapp/upload_schedule.html", {"form": form, "className": className}
    )


def upload_file(request, className=None):
    tools.initialize_user(request)
    if not tools.student_exists(request):
        return render(request, "mainapp/index.html", {"ERR_NOT_LOGGED_IN": True})

    # cannot show a class that doesnt exist
    if className == None:
        return HttpResponseRedirect(reverse("index"))

    # cannot show a non-registered class
    if not tools.class_exists(className):
        return HttpResponseRedirect(reverse("index"))

    if request.method == "POST":
        form = FileForm(request.POST, request.FILES)
        if form.is_valid():
            print(request.POST["title"])
            models.File.objects.create(
                title=request.POST["title"],
                author=request.user.username,
                className=className,
                pdf=request.FILES["pdf"],
                description=request.POST['description']
            )
            return redirect("file_list", className=className)
    else:
        form = FileForm()

    return render(
        request, "mainapp/upload_file.html", {"form": form, "className": className}
    )


def delete_file(request, pk, className=None):
    tools.initialize_user(request)

    if not tools.student_exists(request):
        return render(request, "mainapp/index.html", {"ERR_NOT_LOGGED_IN": True})

    # cannot show a class that doesnt exist
    if className == None:
        return HttpResponseRedirect(reverse("index"))

    # cannot show a non-registered class
    if not tools.class_exists(className):
        return HttpResponseRedirect(reverse("index"))

    if request.method == "POST":
        file = File.objects.get(pk=pk)
        file.delete()
    return redirect("file_list", className=className)


def file_list(request, className=None):
    """
    Displays a list of files for a certain class with name className
    """
    tools.initialize_user(request)
    if not tools.student_exists(request):
        return render(request, "mainapp/index.html", {"ERR_NOT_LOGGED_IN": True})

    # cannot show a class that doesnt exist
    if className == None:
        return HttpResponseRedirect(reverse("index"))

    # cannot show a non-registered class
    if not tools.class_exists(className):
        return HttpResponseRedirect(reverse("index"))

    f = FileFilter(request.GET, queryset=File.objects.filter(className=className))
    return render(
        request, "mainapp/file_list.html", {"filter": f, "className": className}
    )


def view_class(request, className=None):
    """
    Shows the home page for a class
    """
    tools.initialize_user(request)
    if not tools.student_exists(request):
        return render(request, "mainapp/index.html", {"ERR_NOT_LOGGED_IN": True})

    # cannot show a class that doesnt exist
    if className == None:
        return HttpResponseRedirect(reverse("index"))

    # cannot show a non-registered class
    if not tools.class_exists(className):
        return HttpResponseRedirect(reverse("index"))

    # render the class page
    todo = tools.todo_list(request, className, editable=True,)
    return render(
        request,
        "mainapp/view_class.html",
        {
            "class": tools.get_class(className),
            "todo": mark_safe(todo),
            "has_todo": len(todo) != 0,
            "class_list": sorted(tools.list_members_of_class(className), key=lambda student : student.name),
            "professor": tools.get_user_with_id(tools.get_class(className).professorId),
        },
    )


def change_color(request, className=None):
    """
    Change the color for a class given the className
    The given request should have the color id
    """

    tools.initialize_user(request)
    if not tools.student_exists(request):
        return render(request, "mainapp/index.html", {"ERR_NOT_LOGGED_IN": True})

    # change default non-class color
    if className == None:
        tools.set_class_color(request, className, request.POST["colorpicker"])
    elif tools.class_exists(className):
        tools.set_class_color(request, className, request.POST["colorpicker"])
    return HttpResponseRedirect(request.META.get("HTTP_REFERER"))


def todo_list(request):
    """
    The view for the todo list
    """
    tools.initialize_user(request)
    if not tools.student_exists(request):
        return render(request, "mainapp/index.html", {"ERR_NOT_LOGGED_IN": True})

    todo = tools.todo_list(request, editable=True, todo_loc=True)
    return render(
        request,
        "mainapp/todo_list.html",
        {"todo": mark_safe(todo), "has_todo": len(todo) != 0,},
    )

def change_profile_photo(request):
    """
    Changes profile for current user
    """
    if not tools.student_exists(request):
        return HttpResponseRedirect(request.META.get("HTTP_REFERER"))
    student = tools.get_student(request)
    student.profile_photo = request.FILES['file']
    student.save()
    return HttpResponseRedirect(request.META.get("HTTP_REFERER"))

def user_page(request, user_id=None):
    tools.initialize_user(request)
    if not tools.student_exists(request):
        return render(request, "mainapp/index.html", {"ERR_NOT_LOGGED_IN": True})

    if user_id == None:
        user_id = tools.get_student(request).userId

    # bad url query
    if not tools.user_with_id_exists(user_id):
        return render(request, "mainapp/index.html")

    return render(
            request,
            "mainapp/user.html",
            {
            'student': tools.get_user_with_id(user_id),
            'description': mark_safe(tools.get_user_with_id(user_id).description),
            'mood': mark_safe(tools.get_user_with_id(user_id).mood),
            'owner' : tools.get_student(request).userId == user_id,
            }
        )

def edit_profile(request):
    """
    A page for users to edit their profile
    """
    tools.initialize_user(request)
    if not tools.student_exists(request):
        return render(request, "mainapp/index.html", {"ERR_NOT_LOGGED_IN": True})

    class EditProfileForm(django.forms.Form):
        def no_code(description):
            if "<" in description or ">" in description:
                raise ValidationError("Cannot use < or > symbols in description")

        def valid_description_format(description):
            desc_list = description.split("\n")
            for desc in desc_list:
                if desc.count(":") == 0:
                    raise ValidationError(f"Line {desc} does not have a semicolon")
                if desc.count(":") > 1:
                    raise ValidationError(f"Line {desc} has too many semicolons")
                if len(desc) > 40:
                    raise ValidationError(f"Line {desc} must be 40 characters or less \n(it is {len(desc)} characters)")

        name = django.forms.CharField(
            widget=django.forms.Textarea(
                attrs={
                    "cols": 50,
                    "rows": 1,
                    "style": "border-radius: 7px; border-color: black;margin-bottom:10px",
                }
            ),
            label="Username:",
            max_length=50,
            min_length=1,
            required=True,
            initial=tools.get_student(request).name,
            validators=[no_code]
        )
        
        mood = django.forms.CharField(
            widget=django.forms.Textarea(
                attrs={
                    "cols": 50,
                    "rows": 1,
                    "style": "border-radius: 7px; border-color: black;margin-bottom:10px",
                }
            ),
            label="Describe Yourself:",
            max_length=50,
            min_length=1,
            required=True,
            initial=tools.get_student(request).mood,
            validators=[no_code]
        )
        description = django.forms.CharField(
            widget=django.forms.Textarea(
                attrs={
                    "cols": 50,
                    "rows": 10,
                    "style": "border-radius: 7px; border-color: black;margin-bottom:10px",
                }
            ),
            label="List your Information:",
            max_length=500,
            min_length=1,
            required=True,
            initial=tools.parse_description_to_text(tools.get_student(request).description),
            validators=[no_code, valid_description_format]
        )

    if request.method == "POST":
        # gather the form
        form = EditProfileForm(request.POST)
        # check whether the form fits the constraints:
        if form.is_valid():
            # save the user profile

            student = tools.get_student(request)
            student.mood = form.data["mood"]
            student.description = tools.parse_description_to_html(form.data["description"])
            student.name = form.data["name"]
            student.save()

            # redirect to user page
            return HttpResponseRedirect(
                reverse("user")
            )

    # create a blank form
    else:
        form = EditProfileForm()
    # display the webpage (if it was not a post)
    return render(
        request, "mainapp/edit_user.html", {"form": form}
    )
    
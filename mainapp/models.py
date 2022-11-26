from django.db import models
from picklefield.fields import PickledObjectField
import django_filters

# Create your models here.


class Student(models.Model):
    """
    Student model. Allows mapping from internal user.id to google calendar api calendarIds.
    Professors are also counted as students, so they also get their own calendar
    """

    userId = models.IntegerField()
    calendarId = models.CharField(max_length=200)
    # pickled representation of python set of classNames
    classes = PickledObjectField()
    class_colors = PickledObjectField()
    color = models.CharField(default="#0052bd", max_length=10)
    professor = models.BooleanField(default=False)
    name = models.CharField(max_length=50, null=True)
    description = models.CharField(max_length=10000, null=True)
    mood = models.CharField(max_length=50, null=True)
    profile_photo = models.FileField(upload_to="files/profiles/", null=True)


class Class(models.Model):
    """
    Class model. Can be created by professors, each has a calendarId for its assignments
    Professors can add assignments to these calendars, students cannot
    Students can add classes to their calendars through a page
    """

    className = models.CharField(max_length=50)
    calendarId = models.CharField(max_length=200)
    professorId = models.IntegerField()
    description = models.CharField(max_length=200)

    def __str__(self):
        return self.className


class File(models.Model):
    className = models.CharField(max_length=255, blank=True)

    title = models.CharField(max_length=255, blank=False)
    author = models.CharField(max_length=255, blank=True)
    pdf = models.FileField(upload_to="files/pdfs/")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    description = models.CharField(max_length=200, blank=False)

    def __str__(self):
        return self.title

    def delete(self, *args, **kwargs):
        self.pdf.delete()
        super().delete(*args, **kwargs)


class FileFilter(django_filters.FilterSet):
    class Meta:
        model = File
        fields = []

    def my_custom_filter(self, queryset, name, value):
        return queryset.filter(**{name: value,})


class Notification(models.Model):
    """
    Notification model. Stores the userId, and body for emails to send to a user. Notifications are cleared periodically by the periodic message sender. 
    """

    email = models.CharField(max_length=50)
    text = models.CharField(max_length=500)


class CheckedAssignments(models.Model):
    """
    Maintains assignments that are checked off
    """

    userId = models.IntegerField()
    className = models.CharField(max_length=50)
    eventId = models.CharField(max_length=200)

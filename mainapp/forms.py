from django import forms
from django.core.exceptions import ValidationError
from .models import File
from django.core.validators import RegexValidator
from . import tools

# used to get calendar widget for creating assignment with date
# https://www.youtube.com/watch?v=I2-JYxnSiB0
class DateInput(forms.DateInput):
    input_type = 'date'

class CreateClass(forms.Form):
    def no_duplicate(chosen_name):
        if tools.class_exists(chosen_name):
            raise ValidationError("Class with this name already exists")

    def no_slash(chosen_name):
        if "/" in chosen_name or "\\" in chosen_name:
            raise ValidationError("Cannot have class names with slashes")

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

    name = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "cols": 50,
                "rows": 1,
                "style": "border-radius: 7px; border-color: black;margin-bottom:10px;",
            }
        ),
        label="Class name:",
        max_length=50,
        min_length=4,
        required=True,
        # https://stackoverflow.com/questions/17165147/how-can-i-make-a-django-form-field-contain-only-alphanumeric-characters
        validators=[no_slash, no_illegal_name, no_duplicate,],
    )
    description = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "cols": 50,
                "rows": 4,
                "style": "border-radius: 7px; border-color: black;margin-bottom:10px;",
            }
        ),
        label="Class description:",
        max_length=200,
        min_length=10,
        required=True,
    )


class FileForm(forms.ModelForm):
    class Meta:
        model = File
        fields = ("title", "description", "pdf")
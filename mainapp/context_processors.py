from . import tools


def is_professor(request):
    return {"USER_IS_PROFESSOR": tools.is_professor(request)}


def get_class_color(request):
    return {"CLASS_COLOR": tools.get_color(request, tools.className_from_url(request))}


def is_assigned_professor(request):
    return {
        "IS_ASSIGNED_PROFESSOR": tools.is_professor_for_class(
            request, tools.className_from_url(request)
        )
    }


def is_my_class(request):
    return {
        "IS_MY_CLASS": tools.class_exists_for_student(
            request, tools.className_from_url(request)
        )
    }

def get_name(request):
    return {
        "USERNAME": tools.get_username(
            request
        )
    }
from django.urls import path, include
from django.contrib.auth.views import LogoutView
from . import views
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls import url

# from django_filters.views import FilterView
# from myapp.models import Product

urlpatterns = [
    path("", views.index, name="index"),
    path("accounts/", include("allauth.urls"), name="google"),
    path("logout", LogoutView.as_view(), name="logout"),
    path("calendar/<int:month_id>/", views.calendar_view, name="calendar"),
    path("calendar/prev_month/<int:month_id>/", views.prev_month, name="prev_month"),
    path("calendar/next_month/<int:month_id>/", views.next_month, name="next_month"),
    path("calendar/", views.calendar_view, name="calendar"),
    # adding this prefix before delete assignment is the only way I can get this to work
    # I assume this is due to a bug in Django (see definition in tools, {url} did not work)
    # But Ive been coding this for like 2 days straight now and I really dont wanna fix it
    path(
        "classes/<str:untrueClassName>/view/<str:className>/<str:event_id>/delete_assignment/<str:action>/",
        views.delete_assignment,
        name="delete_assignment",
    ),
    path(
        "todo/<str:className>/<str:event_id>/delete_assignment/<str:action>/",
        views.delete_assignment,
        name="delete_assignment",
    ),
    path("classes/", views.classes, name="classes"),
    path("classes/<str:className>/view/", views.view_class, name="view_class"),
    path(
        "classes/<str:className>/files/upload/", views.upload_file, name="upload_file"
    ),
    path(
        "classes/<str:className>/files/delete/<int:pk>/",
        views.delete_file,
        name="delete_file",
    ),
    path("classes/<str:className>/files/", views.file_list, name="file_list"),
    path(
        "classes/<str:className>/add_assignment/",
        views.add_assignment,
        name="add_assignment",
    ),
    path("classes/add_assignment/", views.add_assignment, name="add_assignment",),
    path(
        "classes/<str:className>/remove_classes/",
        views.remove_classes,
        name="remove_classes",
    ),
    path(
        "classes/<str:className>/upload_schedule/",
        views.upload_schedule,
        name="upload_schedule",
    ),
    path("all_classes/", views.all_classes, name="all_classes"),
    path(
        "all_classes/add_classes/<str:className>/",
        views.add_classes,
        name="add_classes",
    ),
    path("classes/create_class/", views.create_class, name="create_class"),
    path("change_color/<str:className>/", views.change_color, name="change_color"),
    path("change_color/", views.change_color, name="change_color"),
    path("todo/", views.todo_list, name="todo"),
    path("save_username/", views.change_profile_photo, name="change_profile_photo"),

    path('user/<int:user_id>/', views.user_page, name="user"),
    path('user/', views.user_page, name="user"),
    path('user/edit/', views.edit_profile, name="edit_profile"),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

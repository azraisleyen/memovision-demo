from django.urls import path

from . import views


urlpatterns = [
    # PUBLIC
    path("", views.landing, name="landing"),
    path("plans/", views.public_plans, name="public_plans"),

    # AUTH
    path("login/", views.CustomLoginView.as_view(), name="login"),
    path("register/", views.register_view, name="register"),
    path("logout/", views.logout_view, name="logout"),

    # ANALYSIS
    path("analysis/new/", views.new_analysis, name="new_analysis"),
    path("analysis/<int:analysis_id>/", views.dashboard, name="dashboard"),

    # HISTORY
    path("projects/", views.projects, name="projects"),

    # REPORTS
    path("analysis/<int:pk>/report/", views.report_view, name="report_view"),
    path("analysis/<int:pk>/download/", views.download_report, name="download_report"),
    path("analysis/<int:analysis_id>/rerun/", views.rerun_analysis, name="rerun_analysis"),

    # SETTINGS
    path("settings/", views.settings_view, name="settings_page"),
]

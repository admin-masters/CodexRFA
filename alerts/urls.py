from django.urls import path
from . import views

app_name = "alerts"

urlpatterns = [
    path("doctor/setup/", views.doctor_setup, name="doctor_setup"),
    path("d/<slug:slug>/", views.patient_start, name="patient_start"),
    path("d/<slug:slug>/forms/<str:form_id>/", views.patient_form, name="patient_form"),
    path("doctor/red-flag/<str:red_flag_id>/", views.doctor_redflag_page, name="doctor_redflag"),
]

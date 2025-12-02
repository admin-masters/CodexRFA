from django import forms
from .models import Doctor


class DoctorCustomizationForm(forms.ModelForm):
    class Meta:
        model = Doctor
        fields = ["name", "email", "clinic_name", "city", "specialization"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "clinic_name": forms.TextInput(attrs={"class": "form-control"}),
            "city": forms.TextInput(attrs={"class": "form-control"}),
            "specialization": forms.TextInput(attrs={"class": "form-control"}),
        }


class PatientStartForm(forms.Form):
    form_id = forms.ChoiceField(label="Select form", widget=forms.Select(attrs={"class": "form-select"}))
    language = forms.ChoiceField(label="Language", widget=forms.Select(attrs={"class": "form-select"}))
    patient_name = forms.CharField(label="Patient name", widget=forms.TextInput(attrs={"class": "form-control"}))
    patient_mobile = forms.CharField(
        label="Mobile number", widget=forms.TextInput(attrs={"class": "form-control"}), max_length=15
    )

    def __init__(self, form_choices, language_choices, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["form_id"].choices = form_choices
        self.fields["language"].choices = language_choices

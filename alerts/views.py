from typing import Dict, List
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .email_utils import send_redflag_email
from .forms import DoctorCustomizationForm, PatientStartForm
from .models import (
    Doctor,
    DoctorLink,
    Form,
    FormTranslation,
    Language,
    OptionRedFlagMap,
    PatientSubmission,
    Question,
    QuestionCondition,
    QuestionOption,
    QuestionTranslation,
    RedFlag,
    RedFlagTranslation,
    generate_patient_id,
)


def doctor_setup(request: HttpRequest) -> HttpResponse:
    link = None
    if request.method == "POST":
        form = DoctorCustomizationForm(request.POST)
        if form.is_valid():
            doctor = form.save()
            link_url = settings.SITE_BASE_URL + reverse("alerts:patient_start", args=[doctor.shareable_slug])
            DoctorLink.objects.update_or_create(doctor=doctor, defaults={"link": link_url})
            link = link_url
    else:
        form = DoctorCustomizationForm()
    return render(request, "alerts/doctor_setup.html", {"form": form, "link": link})


def _language_choices() -> List[tuple]:
    return [(lang.code, lang.name) for lang in Language.objects.all()]


def _form_choices(language_code: str) -> List[tuple]:
    translations = FormTranslation.objects.filter(language__code=language_code)
    if not translations.exists():
        translations = FormTranslation.objects.filter(language__code="en")
    return [(ft.form.form_id, ft.form_name) for ft in translations]


def patient_start(request: HttpRequest, slug: str) -> HttpResponse:
    doctor = get_object_or_404(Doctor, shareable_slug=slug)
    language_choices = _language_choices()
    form_choices = _form_choices(language_code="en")

    if request.method == "POST":
        form = PatientStartForm(form_choices, language_choices, request.POST)
        if form.is_valid():
            request.session["patient_name"] = form.cleaned_data["patient_name"]
            request.session["patient_mobile"] = form.cleaned_data["patient_mobile"]
            request.session.modified = True
            return redirect(
                reverse(
                    "alerts:patient_form",
                    args=[slug, form.cleaned_data["form_id"]],
                )
                + f"?lang={form.cleaned_data['language']}"
            )
    else:
        form = PatientStartForm(form_choices, language_choices)

    return render(
        request,
        "alerts/patient_start.html",
        {"doctor": doctor, "form": form},
    )


def _get_question_text(question: Question, language: Language) -> str:
    try:
        return question.translations.get(language=language).question_text
    except QuestionTranslation.DoesNotExist:
        return question.translations.filter(language__code="en").first().question_text


def _option_text(option: QuestionOption, language: Language) -> str:
    try:
        return option.translations.get(language=language).option_text
    except OptionTranslation.DoesNotExist:
        fallback = option.translations.filter(language__code="en").first()
        return fallback.option_text if fallback else option.option_id


def _redflag_patient_text(redflag: RedFlag, language: Language) -> str:
    try:
        return redflag.translations.get(language=language).patient_response
    except RedFlagTranslation.DoesNotExist:
        return redflag.default_patient_response


def _redflag_doctor_text(redflag: RedFlag, language: Language) -> str:
    try:
        return redflag.translations.get(language=language).doctor_at_a_glance
    except RedFlagTranslation.DoesNotExist:
        return redflag.doctor_at_a_glance


def _question_conditions_met(question: Question, answers: Dict[str, List[str]]) -> bool:
    if not question.parent_question:
        return True
    if not question.conditions.exists():
        return True
    parent_answer = answers.get(question.parent_question.question_id, [])
    if isinstance(parent_answer, str):
        parent_answer = [parent_answer]
    trigger_options = {qc.trigger_option.option_id for qc in question.conditions.all()}
    return any(opt in trigger_options for opt in parent_answer)


def patient_form(request: HttpRequest, slug: str, form_id: str) -> HttpResponse:
    doctor = get_object_or_404(Doctor, shareable_slug=slug)
    form = get_object_or_404(Form, form_id=form_id)
    language_code = request.GET.get("lang", "en")
    language = get_object_or_404(Language, code=language_code)

    patient_name = request.session.get("patient_name")
    patient_mobile = request.session.get("patient_mobile")
    if not patient_name or not patient_mobile:
        return redirect(reverse("alerts:patient_start", args=[slug]))

    questions = list(form.questions.select_related("parent_question").prefetch_related("options__translations", "conditions"))

    if request.method == "POST":
        answers: Dict[str, List[str]] = {}
        for question in questions:
            if not _question_conditions_met(question, answers):
                continue
            key = f"q_{question.question_id}"
            if question.question_type == Question.TEXT:
                answers[question.question_id] = request.POST.get(key, "")
            elif question.question_type == Question.SELECT:
                answers[question.question_id] = request.POST.get(key)
            else:
                answers[question.question_id] = request.POST.getlist(key)

            if question.shows_text_field:
                answers[f"{question.question_id}_text"] = request.POST.get(f"{key}_text", "")

        red_flag_ids = set()
        for question in questions:
            value = answers.get(question.question_id)
            if not value:
                continue
            selected_options = value if isinstance(value, list) else [value]
            for option_id in selected_options:
                try:
                    option = QuestionOption.objects.get(option_id=option_id)
                except QuestionOption.DoesNotExist:
                    continue
                red_flag_ids.update(
                    OptionRedFlagMap.objects.filter(option=option).values_list("red_flag__red_flag_id", flat=True)
                )

        red_flags = list(RedFlag.objects.filter(red_flag_id__in=red_flag_ids))
        patient_id = generate_patient_id(patient_name, patient_mobile)
        submission = PatientSubmission.objects.create(
            patient_id=patient_id,
            doctor=doctor,
            form=form,
            language=language,
            responses=answers,
        )
        if red_flags:
            submission.red_flags.set(red_flags)

        red_flag_payload = [
            {
                "red_flag": rf,
                "patient_text": _redflag_patient_text(rf, language),
                "doctor_text": _redflag_doctor_text(rf, language),
            }
            for rf in red_flags
        ]

        if red_flag_payload:
            send_redflag_email(doctor, submission, red_flag_payload)

        return render(
            request,
            "alerts/patient_response.html",
            {
                "doctor": doctor,
                "red_flags": red_flag_payload,
                "language": language,
                "form": form,
            },
        )

    rendered_questions = []
    for question in questions:
        rendered_question = {
            "id": question.question_id,
            "text": _get_question_text(question, language),
            "type": question.question_type,
            "parent_id": question.parent_question.question_id if question.parent_question else None,
            "shows_text_field": question.shows_text_field,
            "conditions": [qc.trigger_option.option_id for qc in question.conditions.all()],
            "options": [
                {
                    "id": option.option_id,
                    "text": _option_text(option, language),
                    "shows_text_field": option.shows_text_field,
                }
                for option in question.options.all()
            ],
        }
        rendered_questions.append(rendered_question)

    return render(
        request,
        "alerts/patient_form.html",
        {
            "doctor": doctor,
            "form": form,
            "language": language,
            "questions": rendered_questions,
        },
    )


def doctor_redflag_page(request: HttpRequest, red_flag_id: str) -> HttpResponse:
    red_flag = get_object_or_404(RedFlag, red_flag_id=red_flag_id)
    return render(request, "alerts/doctor_redflag.html", {"red_flag": red_flag})

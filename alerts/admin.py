from django.contrib import admin
from .models import (
    Doctor,
    DoctorLink,
    Form,
    FormTranslation,
    Language,
    OptionRedFlagMap,
    OptionTranslation,
    PatientSubmission,
    Question,
    QuestionCondition,
    QuestionOption,
    QuestionTranslation,
    RedFlag,
    RedFlagTranslation,
)


class FormTranslationInline(admin.TabularInline):
    model = FormTranslation
    extra = 0


class QuestionTranslationInline(admin.TabularInline):
    model = QuestionTranslation
    extra = 0


class QuestionOptionInline(admin.TabularInline):
    model = QuestionOption
    extra = 0


class OptionTranslationInline(admin.TabularInline):
    model = OptionTranslation
    extra = 0


@admin.register(Form)
class FormAdmin(admin.ModelAdmin):
    inlines = [FormTranslationInline]
    list_display = ("form_id",)


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("question_id", "form", "sequence_no", "question_type")
    list_filter = ("form", "question_type")
    inlines = [QuestionTranslationInline, QuestionOptionInline]


@admin.register(QuestionOption)
class QuestionOptionAdmin(admin.ModelAdmin):
    list_display = ("option_id", "question", "sequence_no", "is_red_flag_option")
    inlines = [OptionTranslationInline]


admin.site.register(Language)
admin.site.register(FormTranslation)
admin.site.register(QuestionTranslation)
admin.site.register(QuestionCondition)
admin.site.register(RedFlag)
admin.site.register(RedFlagTranslation)
admin.site.register(OptionRedFlagMap)
admin.site.register(Doctor)
admin.site.register(DoctorLink)
admin.site.register(PatientSubmission)

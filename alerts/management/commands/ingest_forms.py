import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from alerts.models import (
    Form,
    FormTranslation,
    Language,
    OptionRedFlagMap,
    OptionTranslation,
    Question,
    QuestionCondition,
    QuestionOption,
    QuestionTranslation,
    RedFlag,
    RedFlagTranslation,
)


class Command(BaseCommand):
    help = "Ingest forms and translations from the provided spreadsheet"

    def add_arguments(self, parser):
        parser.add_argument("spreadsheet", type=str, help="Path to the Excel/ODS file to ingest")

    def handle(self, *args, **options):
        path = options["spreadsheet"]
        try:
            data = pd.read_excel(path, sheet_name=None)
        except Exception as exc:
            raise CommandError(f"Unable to read spreadsheet: {exc}")

        self._load_languages(data.get("Languages"))
        self._load_forms(data.get("Forms"))
        questions = self._load_questions(data.get("Questions"))
        self._load_question_conditions(data.get("QuestionConditions"), questions)
        options = self._load_options(data.get("QuestionOptions"))
        self._load_option_translations(data.get("OptionTranslations"), options)
        redflags = self._load_redflags(data.get("Redflags"))
        self._load_redflag_translations(data.get("RedflagTranslations"), redflags)
        self._load_option_redflag_map(data.get("OptionRedFlagMap"), options, redflags)
        self.stdout.write(self.style.SUCCESS("Ingestion complete"))

    def _load_languages(self, df):
        if df is None:
            return
        for _, row in df.iterrows():
            Language.objects.update_or_create(code=row["language_code"], defaults={"name": row["language_name"]})

    def _load_forms(self, df):
        if df is None:
            return
        languages = {lang.code: lang for lang in Language.objects.all()}
        for _, row in df.iterrows():
            form, _ = Form.objects.update_or_create(
                form_id=row["form_id"], defaults={"description": row.get("description", "")}
            )
            for code, language in languages.items():
                if code in row and pd.notna(row[code]):
                    FormTranslation.objects.update_or_create(
                        form=form, language=language, defaults={"form_name": row[code]}
                    )

    def _load_questions(self, df):
        question_map = {}
        if df is None:
            return question_map
        for _, row in df.iterrows():
            form = Form.objects.get(form_id=row["form_id"])
            parent = None
            if pd.notna(row.get("parent_question_id")):
                parent = Question.objects.filter(question_id=row["parent_question_id"]).first()
            question, _ = Question.objects.update_or_create(
                question_id=row["question_id"],
                defaults={
                    "form": form,
                    "sequence_no": row["sequence_no"],
                    "question_type": row["question_type"],
                    "branching_type": row.get("branching_type"),
                    "parent_question": parent,
                    "shows_text_field": bool(row.get("shows_text_field", False)),
                },
            )
            question_map[row["question_id"]] = question
            for language in Language.objects.all():
                col = language.code
                text = row.get(col)
                if pd.notna(text):
                    QuestionTranslation.objects.update_or_create(
                        question=question, language=language, defaults={"question_text": text}
                    )
        return question_map

    def _load_question_conditions(self, df, questions):
        if df is None:
            return
        for _, row in df.iterrows():
            question = questions.get(row["question_id"])
            if not question:
                continue
            try:
                option = QuestionOption.objects.get(option_id=row["trigger_option_id"])
            except QuestionOption.DoesNotExist:
                continue
            QuestionCondition.objects.update_or_create(question=question, trigger_option=option)

    def _load_options(self, df):
        options = {}
        if df is None:
            return options
        for _, row in df.iterrows():
            question = Question.objects.get(question_id=row["question_id"])
            option, _ = QuestionOption.objects.update_or_create(
                option_id=row["option_id"],
                defaults={
                    "question": question,
                    "sequence_no": row["sequence_no"],
                    "is_red_flag_option": bool(row.get("is_red_flag_option", False)),
                    "shows_text_field": bool(row.get("shows_text_field", False)),
                },
            )
            options[row["option_id"]] = option
        return options

    def _load_option_translations(self, df, options):
        if df is None:
            return
        for _, row in df.iterrows():
            option = options.get(row["option_id"])
            if not option:
                continue
            language = Language.objects.get(code=row["language_code"])
            OptionTranslation.objects.update_or_create(
                option=option, language=language, defaults={"option_text": row["option_text"]}
            )

    def _load_redflags(self, df):
        redflags = {}
        if df is None:
            return redflags
        for _, row in df.iterrows():
            redflag, _ = RedFlag.objects.update_or_create(
                red_flag_id=row["red_flag_id"],
                defaults={
                    "severity": row.get("severity", ""),
                    "default_patient_response": row.get("default_patient_response", ""),
                    "patient_video_url": row.get("patient_video_url", ""),
                    "doctor_at_a_glance": row.get("doctor_at_a_glance", ""),
                    "doctor_video_url": row.get("doctor_video_url", ""),
                },
            )
            redflags[row["red_flag_id"]] = redflag
        return redflags

    def _load_redflag_translations(self, df, redflags):
        if df is None:
            return
        for _, row in df.iterrows():
            redflag = redflags.get(row["red_flag_id"])
            if not redflag:
                continue
            language = Language.objects.get(code=row["language_code"])
            RedFlagTranslation.objects.update_or_create(
                red_flag=redflag,
                language=language,
                defaults={
                    "patient_response": row.get("patient_response", ""),
                    "doctor_at_a_glance": row.get("doctor_at_a_glance", ""),
                },
            )

    def _load_option_redflag_map(self, df, options, redflags):
        if df is None:
            return
        for _, row in df.iterrows():
            option = options.get(row["option_id"])
            redflag = redflags.get(row["red_flag_id"])
            if option and redflag:
                OptionRedFlagMap.objects.update_or_create(option=option, red_flag=redflag)

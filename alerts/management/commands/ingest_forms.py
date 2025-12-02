import re

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
            data = {name: self._normalize_dataframe(df) for name, df in pd.read_excel(path, sheet_name=None).items()}
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

    def _normalize_dataframe(self, df):
        if df is None:
            return None
        normalized = df.copy()
        normalized.columns = [self._normalize_column(col) for col in normalized.columns]
        return normalized

    def _normalize_column(self, name):
        normalized = re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower())
        return normalized.strip("_")

    def _get_required_value(self, row, key, sheet_name):
        if key not in row:
            available = ", ".join(row.index.astype(str))
            raise CommandError(
                f"Required column '{key}' not found while processing sheet '{sheet_name}'. "
                f"Available columns: {available}"
            )
        return row.get(key)

    def _require_columns(self, df, required, sheet_name):
        missing = [col for col in required if col not in df.columns]
        if missing:
            available = ", ".join(df.columns)
            raise CommandError(
                f"Missing columns {missing} in sheet '{sheet_name}'. Available columns: {available}"
            )

    def _translation_value(self, row, language):
        """Return the best-effort localized value for a given language.

        The source sheets sometimes use language *codes* ("en") and sometimes
        language *names* ("English"). We try both to avoid silently skipping
        translations which then surface as missing form names/options later in
        the UI.
        """

        candidates = [language.code, language.name, self._normalize_column(language.name)]
        for key in candidates:
            if key in row and pd.notna(row.get(key)):
                return row.get(key)
        return None

    def _load_languages(self, df):
        if df is None:
            return
        self._require_columns(df, ["language_code", "language_name"], "Languages")
        for _, row in df.iterrows():
            Language.objects.update_or_create(code=row["language_code"], defaults={"name": row["language_name"]})

    def _load_forms(self, df):
        if df is None:
            return
        self._require_columns(df, ["form_id"], "Forms")
        languages = {lang.code: lang for lang in Language.objects.all()}
        for _, row in df.iterrows():
            form_id = self._get_required_value(row, "form_id", "Forms")
            form, _ = Form.objects.update_or_create(
                form_id=form_id, defaults={"description": row.get("description", "")}
            )
            for code, language in languages.items():
                name = self._translation_value(row, language)
                if pd.notna(name):
                    FormTranslation.objects.update_or_create(
                        form=form, language=language, defaults={"form_name": name}
                    )

    def _load_questions(self, df):
        question_map = {}
        if df is None:
            return question_map
        self._require_columns(df, ["question_id", "form_id", "sequence_no", "question_type"], "Questions")
        for _, row in df.iterrows():
            form_id = self._get_required_value(row, "form_id", "Questions")
            question_id = self._get_required_value(row, "question_id", "Questions")
            form = Form.objects.get(form_id=form_id)
            parent = None
            if pd.notna(row.get("parent_question_id")):
                parent = Question.objects.filter(question_id=row.get("parent_question_id")).first()
            question, _ = Question.objects.update_or_create(
                question_id=question_id,
                defaults={
                    "form": form,
                    "sequence_no": row["sequence_no"],
                    "question_type": row["question_type"],
                    "branching_type": row.get("branching_type"),
                    "parent_question": parent,
                    "shows_text_field": bool(row.get("shows_text_field", False)),
                },
            )
            question_map[question_id] = question
            for language in Language.objects.all():
                text = self._translation_value(row, language)
                if pd.notna(text):
                    QuestionTranslation.objects.update_or_create(
                        question=question, language=language, defaults={"question_text": text}
                    )
        return question_map

    def _load_question_conditions(self, df, questions):
        if df is None:
            return
        self._require_columns(df, ["question_id", "trigger_option_id"], "QuestionConditions")
        for _, row in df.iterrows():
            question_id = self._get_required_value(row, "question_id", "QuestionConditions")
            question = questions.get(question_id)
            if not question:
                continue
            try:
                trigger_option_id = self._get_required_value(row, "trigger_option_id", "QuestionConditions")
                option = QuestionOption.objects.get(option_id=trigger_option_id)
            except QuestionOption.DoesNotExist:
                continue
            QuestionCondition.objects.update_or_create(question=question, trigger_option=option)

    def _load_options(self, df):
        options = {}
        if df is None:
            return options
        self._require_columns(df, ["option_id", "question_id", "sequence_no"], "QuestionOptions")
        for _, row in df.iterrows():
            option_id = self._get_required_value(row, "option_id", "QuestionOptions")
            question_id = self._get_required_value(row, "question_id", "QuestionOptions")
            question = Question.objects.get(question_id=question_id)
            option, _ = QuestionOption.objects.update_or_create(
                option_id=option_id,
                defaults={
                    "question": question,
                    "sequence_no": row["sequence_no"],
                    "is_red_flag_option": bool(row.get("is_red_flag_option", False)),
                    "shows_text_field": bool(row.get("shows_text_field", False)),
                },
            )
            options[option_id] = option
        return options

    def _load_option_translations(self, df, options):
        if df is None:
            return
        self._require_columns(df, ["option_id", "language_code", "option_text"], "OptionTranslations")
        for _, row in df.iterrows():
            option_id = self._get_required_value(row, "option_id", "OptionTranslations")
            option = options.get(option_id)
            if not option:
                continue
            language_code = self._get_required_value(row, "language_code", "OptionTranslations")
            language = Language.objects.get(code=language_code)
            OptionTranslation.objects.update_or_create(
                option=option, language=language, defaults={"option_text": row["option_text"]}
            )

    def _load_redflags(self, df):
        redflags = {}
        if df is None:
            return redflags
        self._require_columns(df, ["red_flag_id"], "Redflags")
        for _, row in df.iterrows():
            red_flag_id = self._get_required_value(row, "red_flag_id", "Redflags")
            redflag, _ = RedFlag.objects.update_or_create(
                red_flag_id=red_flag_id,
                defaults={
                    "severity": row.get("severity", ""),
                    "default_patient_response": row.get("default_patient_response", ""),
                    "patient_video_url": row.get("patient_video_url", ""),
                    "doctor_at_a_glance": row.get("doctor_at_a_glance", ""),
                    "doctor_video_url": row.get("doctor_video_url", ""),
                },
            )
            redflags[red_flag_id] = redflag
        return redflags

    def _load_redflag_translations(self, df, redflags):
        if df is None:
            return
        self._require_columns(df, ["red_flag_id", "language_code"], "RedflagTranslations")
        for _, row in df.iterrows():
            red_flag_id = self._get_required_value(row, "red_flag_id", "RedflagTranslations")
            redflag = redflags.get(red_flag_id)
            if not redflag:
                continue
            language_code = self._get_required_value(row, "language_code", "RedflagTranslations")
            language = Language.objects.get(code=language_code)
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
        self._require_columns(df, ["option_id", "red_flag_id"], "OptionRedFlagMap")
        for _, row in df.iterrows():
            option_id = self._get_required_value(row, "option_id", "OptionRedFlagMap")
            red_flag_id = self._get_required_value(row, "red_flag_id", "OptionRedFlagMap")
            option = options.get(option_id)
            redflag = redflags.get(red_flag_id)
            if option and redflag:
                OptionRedFlagMap.objects.update_or_create(option=option, red_flag=redflag)

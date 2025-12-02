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
            sheets = pd.read_excel(path, sheet_name=None)
            raw_sheets = pd.read_excel(path, sheet_name=None, header=None)
        except Exception as exc:
            raise CommandError(f"Unable to read spreadsheet: {exc}")

        data = {self._normalize_column(name): self._normalize_dataframe(df) for name, df in sheets.items()}
        raw_data = {self._normalize_column(name): df for name, df in raw_sheets.items()}

        # Fetch helpers tolerate variations in sheet names ("Red Flags", "redflags", etc.)
        get_sheet = lambda key: self._sheet_for(key, data)
        get_raw_sheet = lambda key: self._sheet_for(key, raw_data)

        self._load_languages(get_sheet("languages"))
        self._load_forms(get_sheet("forms"), get_raw_sheet("forms"))
        questions = self._load_questions(get_sheet("questions"))
        self._load_question_translations(get_sheet("questiontranslations"), questions, get_raw_sheet("questiontranslations"))
        self._load_question_conditions(get_sheet("questionconditions"), questions)
        options = self._load_options(get_sheet("questionoptions"))
        self._load_option_translations(get_sheet("optiontranslations"), options, get_raw_sheet("optiontranslations"))
        redflags = self._load_redflags(get_sheet("redflags"))
        self._load_redflag_translations(get_sheet("redflagtranslations"), redflags, get_raw_sheet("redflagtranslations"))
        self._load_option_redflag_map(get_sheet("optionredflagmap"), options, redflags)
        self.stdout.write(self.style.SUCCESS("Ingestion complete"))

    def _sheet_for(self, key, mapping):
        """Return a sheet even when the tab name contains spaces/underscores.

        We often see variations like "Red Flags", "RedFlags", "red_flags". We
        normalize both the requested key and the available sheet names by
        stripping underscores so the loader can still locate the data instead of
        silently skipping entire sheets (which led to empty tables despite a
        "success" message).
        """

        if mapping is None:
            return None

        if key in mapping:
            return mapping[key]

        target = key.replace("_", "")
        for name, df in mapping.items():
            if name.replace("_", "") == target:
                return df
        return None

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

    def _resolve_language_from_label(self, label, languages):
        norm = self._normalize_column(label)
        for lang in languages.values():
            if norm in {self._normalize_column(lang.code), self._normalize_column(lang.name)}:
                return lang
        return None

    def _parse_language_blocks(self, df, expected_headers, languages):
        """Parse sheets that stack language sections instead of using per-column codes.

        The source workbook repeats the header row for each language block:
        English -> header -> data rows, Hindi -> header -> data rows, etc.
        This helper walks the rows, tracks the current language label, captures the
        header row once, and then emits dictionaries that include a language_code key.
        """

        records = []
        if df is None:
            return records

        rows = df.fillna("").values.tolist()
        current_language = None
        header = []

        # If the language label was swallowed into the column header (first row was the
        # language name), fall back to using the first column label as the current language.
        if len(df.columns) > 0:
            header_language = self._resolve_language_from_label(df.columns[0], languages)
            if header_language:
                current_language = header_language

        for row in rows:
            if all(str(cell).strip() == "" for cell in row):
                continue

            possible_language = self._resolve_language_from_label(row[0], languages)
            if possible_language:
                current_language = possible_language
                header = []
                continue

            normalized_row = [self._normalize_column(cell) for cell in row]
            if not header and set(expected_headers).issubset(set(normalized_row)):
                header = normalized_row
                continue

            if current_language and header:
                entry = {header[idx]: row[idx] for idx in range(min(len(header), len(row)))}
                entry["language_code"] = current_language.code
                records.append(entry)

        return records

    def _load_languages(self, df):
        if df is None:
            return
        self._require_columns(df, ["language_code", "language_name"], "Languages")
        for _, row in df.iterrows():
            Language.objects.update_or_create(code=row["language_code"], defaults={"name": row["language_name"]})

    def _load_forms(self, df, raw_df=None):
        if df is None:
            return
        languages = {lang.code: lang for lang in Language.objects.all()}

        if "form_id" in df.columns:
            self._require_columns(df, ["form_id"], "Forms")
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
            return

        # Fallback for stacked language blocks (e.g., English/Hindi header sections)
        source_df = raw_df if raw_df is not None else df
        form_rows = self._parse_language_blocks(source_df, ["form_id", "form_name", "description"], languages)
        for entry in form_rows:
            form_id = entry.get("form_id")
            if not form_id:
                continue
            form, _ = Form.objects.update_or_create(
                form_id=form_id, defaults={"description": entry.get("description", "")}
            )
            language = languages.get(entry.get("language_code"))
            form_name = entry.get("form_name")
            if language and pd.notna(form_name):
                FormTranslation.objects.update_or_create(
                    form=form, language=language, defaults={"form_name": form_name}
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
        return question_map

    def _load_question_translations(self, df, questions, raw_df=None):
        if df is None:
            return

        languages = {lang.code: lang for lang in Language.objects.all()}

        if "language_code" in df.columns:
            self._require_columns(df, ["question_id", "language_code", "question_text"], "QuestionTranslations")
            iterator = df.iterrows()
            records = (
                {
                    "question_id": row["question_id"],
                    "language_code": row["language_code"],
                    "question_text": row.get("question_text"),
                }
                for _, row in iterator
            )
        else:
            source_df = raw_df if raw_df is not None else df
            records = self._parse_language_blocks(source_df, ["question_id", "question_text"], languages)

        for entry in records:
            question = questions.get(entry.get("question_id"))
            language = languages.get(entry.get("language_code"))
            if not question or not language:
                continue
            question_text = entry.get("question_text")
            if pd.notna(question_text):
                QuestionTranslation.objects.update_or_create(
                    question=question, language=language, defaults={"question_text": question_text}
                )

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

    def _load_option_translations(self, df, options, raw_df=None):
        if df is None:
            return
        languages = {lang.code: lang for lang in Language.objects.all()}

        if "language_code" in df.columns:
            self._require_columns(df, ["option_id", "language_code", "option_text"], "OptionTranslations")
            records = df.to_dict("records")
        else:
            source_df = raw_df if raw_df is not None else df
            records = self._parse_language_blocks(source_df, ["option_id", "option_text"], languages)

        for entry in records:
            option_id = entry.get("option_id")
            option = options.get(option_id)
            if not option:
                continue
            language = languages.get(entry.get("language_code"))
            option_text = entry.get("option_text")
            if language and pd.notna(option_text):
                OptionTranslation.objects.update_or_create(
                    option=option, language=language, defaults={"option_text": option_text}
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

    def _load_redflag_translations(self, df, redflags, raw_df=None):
        if df is None:
            return
        languages = {lang.code: lang for lang in Language.objects.all()}

        if "language_code" in df.columns:
            self._require_columns(df, ["red_flag_id", "language_code"], "RedflagTranslations")
            records = df.to_dict("records")
        else:
            source_df = raw_df if raw_df is not None else df
            records = self._parse_language_blocks(
                source_df, ["red_flag_id", "patient_response", "doctor_at_a_glance"], languages
            )

        for entry in records:
            red_flag_id = entry.get("red_flag_id")
            redflag = redflags.get(red_flag_id)
            language = languages.get(entry.get("language_code"))
            if not redflag or not language:
                continue
            RedFlagTranslation.objects.update_or_create(
                red_flag=redflag,
                language=language,
                defaults={
                    "patient_response": entry.get("patient_response", ""),
                    "doctor_at_a_glance": entry.get("doctor_at_a_glance", ""),
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

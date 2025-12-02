# CodexRFA

Django + MySQL reference implementation for the pediatric red-flag alert forms (Phase I). The project includes:

- Doctor setup to generate a patient-facing link
- Patient intake to pick a form and language, complete the dynamic form, and receive red-flag guidance
- SendGrid email alerts to the doctor when red flags are detected
- Deterministic, encrypted patient IDs and transaction storage without storing PII
- Spreadsheet ingestion command to load forms/questions/translations/red flags from the provided workbook

## Quickstart

1. Install dependencies (Django, mysqlclient, SendGrid, pandas).
2. Configure environment variables in a `.env` file:

```
DJANGO_SECRET_KEY=replace-me
DJANGO_DEBUG=false
SITE_BASE_URL=http://localhost:8000
DB_ENGINE=django.db.backends.mysql
DB_NAME=codexrfa
DB_USER=user
DB_PASSWORD=pass
DB_HOST=127.0.0.1
DB_PORT=3306
SENDGRID_API_KEY=your-key
DEFAULT_FROM_EMAIL=no-reply@example.com
PATIENT_ID_SECRET=super-secret
```

3. Run migrations:

```
python manage.py migrate
```

4. Ingest the spreadsheet (download the Google Sheet as XLSX first):

```
python manage.py ingest_forms ./redflags.xlsx
```

5. Create a superuser to manage data from the admin if needed:

```
python manage.py createsuperuser
```

6. Start the development server:

```
python manage.py runserver
```

## Flows

- Navigate to `/doctor/setup/` to create a doctor entry. The generated patient link appears on the confirmation screen and is also stored with the doctor record.
- Patients open the doctor link, choose a form and language, and complete the form. Conditional branching and inline free-text prompts are supported.
- After submission, red flags are shown on-screen with patient video links. When red flags are present, a SendGrid email with doctor education links is dispatched and the submission is saved with a deterministic patient ID and an 8-character record ID.

## Data model highlights

- Fully localized metadata for forms, questions, options, and red flags
- Deterministic patient IDs via salted PBKDF2 hashes (no names or phone numbers are stored)
- Submission JSON payload plus red-flag links for auditability

## Tech

- Django 5, MySQL-compatible schema, SendGrid email API, pandas-based ingestion

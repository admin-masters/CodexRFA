from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Doctor",
            fields=[
                ("doctor_id", models.AutoField(primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=255)),
                ("email", models.EmailField(max_length=254)),
                ("clinic_name", models.CharField(max_length=255)),
                ("city", models.CharField(blank=True, max_length=128)),
                ("specialization", models.CharField(blank=True, max_length=255)),
                ("shareable_slug", models.SlugField(blank=True, max_length=64, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="Form",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("form_id", models.CharField(max_length=64, unique=True)),
                ("description", models.TextField(blank=True)),
            ],
        ),
        migrations.CreateModel(
            name="Language",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=8, unique=True)),
                ("name", models.CharField(max_length=64)),
            ],
        ),
        migrations.CreateModel(
            name="RedFlag",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("red_flag_id", models.CharField(max_length=64, unique=True)),
                ("severity", models.CharField(max_length=32)),
                ("default_patient_response", models.TextField()),
                ("patient_video_url", models.URLField(blank=True)),
                ("doctor_at_a_glance", models.TextField()),
                ("doctor_video_url", models.URLField(blank=True)),
            ],
        ),
        migrations.CreateModel(
            name="FormTranslation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("form_name", models.CharField(max_length=255)),
                (
                    "form",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="translations", to="alerts.form"),
                ),
                ("language", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="alerts.language")),
            ],
            options={"unique_together": {("form", "language")}},
        ),
        migrations.CreateModel(
            name="Question",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("question_id", models.CharField(max_length=64, unique=True)),
                ("sequence_no", models.IntegerField()),
                ("question_type", models.CharField(choices=[("text", "Text"), ("select", "Select"), ("multi_select", "Multi Select")], max_length=32)),
                ("branching_type", models.CharField(blank=True, max_length=32, null=True)),
                ("shows_text_field", models.BooleanField(default=False)),
                (
                    "form",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="questions", to="alerts.form"),
                ),
                (
                    "parent_question",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="child_questions",
                        to="alerts.question",
                    ),
                ),
            ],
            options={"ordering": ["sequence_no"]},
        ),
        migrations.CreateModel(
            name="QuestionTranslation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("question_text", models.TextField()),
                ("language", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="alerts.language")),
                (
                    "question",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="translations", to="alerts.question"),
                ),
            ],
            options={"unique_together": {("question", "language")}},
        ),
        migrations.CreateModel(
            name="QuestionOption",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("option_id", models.CharField(max_length=64, unique=True)),
                ("sequence_no", models.IntegerField()),
                ("is_red_flag_option", models.BooleanField(default=False)),
                ("shows_text_field", models.BooleanField(default=False)),
                (
                    "question",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="options", to="alerts.question"),
                ),
            ],
            options={"ordering": ["sequence_no"]},
        ),
        migrations.CreateModel(
            name="QuestionCondition",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "question",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="conditions", to="alerts.question"),
                ),
                (
                    "trigger_option",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="alerts.questionoption"),
                ),
            ],
            options={"unique_together": {("question", "trigger_option")}},
        ),
        migrations.CreateModel(
            name="OptionTranslation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("option_text", models.TextField()),
                ("language", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="alerts.language")),
                (
                    "option",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="translations", to="alerts.questionoption"),
                ),
            ],
            options={"unique_together": {("option", "language")}},
        ),
        migrations.CreateModel(
            name="DoctorLink",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("link", models.URLField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "doctor",
                    models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="link", to="alerts.doctor"),
                ),
            ],
        ),
        migrations.CreateModel(
            name="RedFlagTranslation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("patient_response", models.TextField()),
                ("doctor_at_a_glance", models.TextField()),
                ("language", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="alerts.language")),
                (
                    "red_flag",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="translations", to="alerts.redflag"),
                ),
            ],
            options={"unique_together": {("red_flag", "language")}},
        ),
        migrations.CreateModel(
            name="OptionRedFlagMap",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("option", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="alerts.questionoption")),
                ("red_flag", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="alerts.redflag")),
            ],
            options={"unique_together": {("option", "red_flag")}},
        ),
        migrations.CreateModel(
            name="PatientSubmission",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("record_id", models.CharField(max_length=8, unique=True)),
                ("patient_id", models.CharField(db_index=True, max_length=128)),
                ("responses", models.JSONField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "doctor",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="submissions", to="alerts.doctor"),
                ),
                (
                    "form",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="alerts.form"),
                ),
                (
                    "language",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="alerts.language"),
                ),
            ],
        ),
        migrations.AddField(
            model_name="patientsubmission",
            name="red_flags",
            field=models.ManyToManyField(blank=True, related_name="submissions", to="alerts.redflag"),
        ),
    ]

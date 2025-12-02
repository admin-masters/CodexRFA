import secrets
from hashlib import pbkdf2_hmac
from django.conf import settings
from django.db import models
from django.utils.text import slugify


class Language(models.Model):
    code = models.CharField(max_length=8, unique=True)
    name = models.CharField(max_length=64)

    def __str__(self):
        return self.name


class Form(models.Model):
    form_id = models.CharField(max_length=64, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.form_id


class FormTranslation(models.Model):
    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name="translations")
    language = models.ForeignKey(Language, on_delete=models.CASCADE)
    form_name = models.CharField(max_length=255)

    class Meta:
        unique_together = ("form", "language")

    def __str__(self):
        return f"{self.form.form_id} ({self.language.code})"


class Question(models.Model):
    TEXT = "text"
    SELECT = "select"
    MULTI_SELECT = "multi_select"
    QUESTION_TYPES = [
        (TEXT, "Text"),
        (SELECT, "Select"),
        (MULTI_SELECT, "Multi Select"),
    ]

    question_id = models.CharField(max_length=64, unique=True)
    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name="questions")
    sequence_no = models.IntegerField()
    question_type = models.CharField(max_length=32, choices=QUESTION_TYPES)
    branching_type = models.CharField(max_length=32, blank=True, null=True)
    parent_question = models.ForeignKey(
        "self", blank=True, null=True, on_delete=models.SET_NULL, related_name="child_questions"
    )
    shows_text_field = models.BooleanField(default=False)

    class Meta:
        ordering = ["sequence_no"]

    def __str__(self):
        return self.question_id


class QuestionTranslation(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="translations")
    language = models.ForeignKey(Language, on_delete=models.CASCADE)
    question_text = models.TextField()

    class Meta:
        unique_together = ("question", "language")

    def __str__(self):
        return f"{self.question.question_id} ({self.language.code})"


class QuestionOption(models.Model):
    option_id = models.CharField(max_length=64, unique=True)
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="options")
    sequence_no = models.IntegerField()
    is_red_flag_option = models.BooleanField(default=False)
    shows_text_field = models.BooleanField(default=False)

    class Meta:
        ordering = ["sequence_no"]

    def __str__(self):
        return self.option_id


class OptionTranslation(models.Model):
    option = models.ForeignKey(QuestionOption, on_delete=models.CASCADE, related_name="translations")
    language = models.ForeignKey(Language, on_delete=models.CASCADE)
    option_text = models.TextField()

    class Meta:
        unique_together = ("option", "language")

    def __str__(self):
        return f"{self.option.option_id} ({self.language.code})"


class QuestionCondition(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="conditions")
    trigger_option = models.ForeignKey(QuestionOption, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("question", "trigger_option")

    def __str__(self):
        return f"{self.question.question_id} -> {self.trigger_option.option_id}"


class RedFlag(models.Model):
    red_flag_id = models.CharField(max_length=64, unique=True)
    severity = models.CharField(max_length=32)
    default_patient_response = models.TextField()
    patient_video_url = models.URLField(blank=True)
    doctor_at_a_glance = models.TextField()
    doctor_video_url = models.URLField(blank=True)

    def __str__(self):
        return self.red_flag_id


class RedFlagTranslation(models.Model):
    red_flag = models.ForeignKey(RedFlag, on_delete=models.CASCADE, related_name="translations")
    language = models.ForeignKey(Language, on_delete=models.CASCADE)
    patient_response = models.TextField()
    doctor_at_a_glance = models.TextField()

    class Meta:
        unique_together = ("red_flag", "language")

    def __str__(self):
        return f"{self.red_flag.red_flag_id} ({self.language.code})"


class OptionRedFlagMap(models.Model):
    option = models.ForeignKey(QuestionOption, on_delete=models.CASCADE)
    red_flag = models.ForeignKey(RedFlag, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("option", "red_flag")

    def __str__(self):
        return f"{self.option.option_id} -> {self.red_flag.red_flag_id}"


class Doctor(models.Model):
    doctor_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    email = models.EmailField()
    clinic_name = models.CharField(max_length=255)
    city = models.CharField(max_length=128, blank=True)
    specialization = models.CharField(max_length=255, blank=True)
    shareable_slug = models.SlugField(max_length=64, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.shareable_slug:
            base = slugify(f"{self.name}-{self.clinic_name}") or "doctor"
            slug = base
            counter = 1
            while Doctor.objects.filter(shareable_slug=slug).exclude(pk=self.pk).exists():
                counter += 1
                slug = f"{base}-{counter}"
            self.shareable_slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.clinic_name})"


class DoctorLink(models.Model):
    doctor = models.OneToOneField(Doctor, on_delete=models.CASCADE, related_name="link")
    link = models.URLField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.link


class PatientSubmission(models.Model):
    record_id = models.CharField(max_length=8, unique=True)
    patient_id = models.CharField(max_length=128, db_index=True)
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name="submissions")
    form = models.ForeignKey(Form, on_delete=models.PROTECT)
    language = models.ForeignKey(Language, on_delete=models.PROTECT)
    responses = models.JSONField()
    red_flags = models.ManyToManyField(RedFlag, related_name="submissions", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.record_id:
            self.record_id = secrets.token_hex(4)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.record_id} ({self.doctor_id})"


def generate_patient_id(name: str, mobile: str) -> str:
    raw = f"{name}:{mobile}".encode()
    secret = settings.PATIENT_ID_SECRET.encode()
    digest = pbkdf2_hmac("sha256", raw, secret, 100000, dklen=16)
    return digest.hex()

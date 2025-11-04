from django.db import models

class DraftReport(models.Model):
    filename = models.CharField(max_length=1024)
    study_id = models.CharField(max_length=255)
    region = models.CharField(max_length=255, null=True, blank=True)
    site = models.CharField(max_length=255, null=True, blank=True)
    batch = models.CharField(max_length=255, null=True, blank=True)
    product = models.CharField(max_length=255, null=True, blank=True)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    #test_pdf field to store the uploaded PDF file
    test_pdf = models.FileField(upload_to='test_pdfs/', null=True, blank=True)


    def __str__(self):
        return f"Draft {self.id} - {self.filename}"

class Approval(models.Model):
    report = models.OneToOneField(DraftReport, on_delete=models.CASCADE, related_name='approval')
    passed = models.BooleanField(null=True)
    approved_by = models.CharField(max_length=255, null=True, blank=True)
    approved_on = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Approval for {self.report_id} - {self.passed}"

class MailInstruction(models.Model):
    report = models.ForeignKey(DraftReport, on_delete=models.CASCADE, related_name='mail_instructions')
    recipient = models.CharField(max_length=255)
    source_type = models.CharField(max_length=32, default='LDAP')
    timestamp_added = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.recipient} ({self.source_type})"

class FinalReport(models.Model):
    id = models.BigAutoField(primary_key=True)
    filename = models.CharField(max_length=1024)
    study_id = models.CharField(max_length=255)
    region = models.CharField(max_length=255, null=True, blank=True)
    site = models.CharField(max_length=255, null=True, blank=True)
    batch = models.CharField(max_length=255, null=True, blank=True)
    product = models.CharField(max_length=255, null=True, blank=True)
    passed = models.BooleanField(null=True)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    approved_by = models.CharField(max_length=255, null=True, blank=True)
    approved_on = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "final_reports"
        unique_together = ("study_id", "site")

    def __str__(self):
        return f"{self.study_id} - {self.site}"

class ProcessLog(models.Model):
    timestamp = models.DateTimeField()
    study = models.CharField(max_length=255, null=True, blank=True)
    region = models.CharField(max_length=255, null=True, blank=True)
    site = models.CharField(max_length=255, null=True, blank=True)
    product = models.CharField(max_length=255, null=True, blank=True)
    response = models.CharField(max_length=255, null=True, blank=True)
    state = models.CharField(max_length=255, null=True, blank=True)
    text = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.timestamp} - {self.study or 'N/A'}"

class AccessLog(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    user_id = models.CharField(max_length=255)
    action = models.CharField(max_length=32)
    subject = models.CharField(max_length=1024)

    def __str__(self):
        return f"{self.timestamp} - {self.user_id} - {self.action}"

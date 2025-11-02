from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Approval, FinalReport

@receiver(post_save, sender=Approval)
def sync_final_report(sender, instance, **kwargs):
    """Auto-create or update FinalReport whenever a DraftReport is approved."""
    draft = instance.report

    FinalReport.objects.update_or_create(
        study_id=draft.study_id,
        site=draft.site,
        defaults={
            'filename': draft.filename.replace("draft", "final"),
            'region': draft.region,
            'batch': draft.batch,
            'product': draft.product,
            'passed': instance.passed,
            'approved_by': instance.approved_by,
            'approved_on': instance.approved_on,
            'start_date': draft.start_date,
            'end_date': draft.end_date,
        },
    )

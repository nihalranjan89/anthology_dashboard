from django.contrib import admin
from .models import DraftReport, FinalReport, Approval, MailInstruction, ProcessLog, AccessLog

admin.site.register(DraftReport)
admin.site.register(FinalReport)
admin.site.register(Approval)
admin.site.register(MailInstruction)
admin.site.register(ProcessLog)
admin.site.register(AccessLog)
# End of src/anthology/admin.py


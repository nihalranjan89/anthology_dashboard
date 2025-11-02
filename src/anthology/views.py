from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseForbidden, HttpResponse
from django.conf import settings
from .models import FinalReport, DraftReport
from .services import azure_blob, saml_auth, ldap_service
from django.utils.dateparse import parse_date
from datetime import datetime
from django.db.models import Q
from django.utils import timezone
from .models import Approval, FinalReport

def login_view(request):
    # Redirect to SSO login (placeholder)
    sso_login = f"{settings.SSO_HOSTNAME}{settings.SSO_LOGIN_URI}"
    return redirect(sso_login)

def login_callback(request):
    # Placeholder SAML callback: production must validate SAMLResponse signature
    # For dev mode: simulate a user by setting session vars
    # In production parse request.POST['SAMLResponse'] using python3-saml
    # Here we set a simple dev user for local testing
    request.session['USER_DISPLAY_NAME'] = 'Dev User'
    request.session['USER_ID'] = 'dev.user'
    request.session['USER_ROLE'] = 'APPROVER'  # ADMIN / APPROVER / VIEWER
    request.session['USER_REGIONS'] = []
    request.session['USER_SITES'] = []
    return redirect('anthology:reports')

def logout_view(request):
    request.session.flush()
    sso_logout = f"{settings.SSO_HOSTNAME}{settings.SSO_LOGOUT_URI}"
    return redirect(sso_logout)


def reports_list(request):
    """
    Show reports in reverse chronological order with filters:
      - Site
      - Date Range (start_date / end_date)
      - Status (Draft / Final)
      - Pass/Fail (for Final only)
    """
    site = request.GET.get('site', '').strip()
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    status = request.GET.get('status', 'final').lower()      # 'draft' or 'final'
    pass_filter = request.GET.get('pass_status', '').lower() # 'passed' or 'failed'

    # Choose model based on report type
    model = FinalReport if status == 'final' else DraftReport
    queryset = model.objects.all()

    # 🔹 Apply filters
    if site:
        queryset = queryset.filter(site__icontains=site)
    if start_date:
        queryset = queryset.filter(start_date__gte=parse_date(start_date))
    if end_date:
        queryset = queryset.filter(end_date__lte=parse_date(end_date))

    # 🔹 If viewing FINAL reports, allow pass/fail filter
    if status == 'final':
        if pass_filter == 'passed':
            queryset = queryset.filter(passed=True)
        elif pass_filter == 'failed':
            queryset = queryset.filter(passed=False)

    # 🔹 If viewing DRAFT reports, only show those without approval (pending)
    if status == 'draft':
        queryset = queryset.filter(approval__isnull=True)

    # Sort newest first
    order_field = '-approved_on' if status == 'final' else '-start_date'
    reports = queryset.order_by(order_field)

    context = {
        'reports': reports,
        'selected_site': site,
        'selected_status': status,
        'start_date': start_date,
        'end_date': end_date,
        'pass_filter': pass_filter,
    }
    return render(request, 'anthology/reports.html', context)



def report_detail(request, report_id):
    report = get_object_or_404(FinalReport, pk=report_id)
    # create a signed URL or proxy the blob; here we create blob url (SAS must be appended)
    blob_url = azure_blob.get_blob_url(report.filename, report_type='final')
    return render(request, 'anthology/report_detail.html', {'report': report, 'blob_url': blob_url})


def drafts_list(request):
    role = request.session.get('USER_ROLE')
    if role not in ('ADMIN', 'APPROVER'):
        return HttpResponseForbidden("Forbidden")

    drafts = DraftReport.objects.all().select_related('approval').order_by('-start_date')[:100]

    draft_data = []
    pending_count = 0

    for d in drafts:
        if hasattr(d, 'approval'):
            status = "✅ Passed" if d.approval.passed else "❌ Failed"
        else:
            status = "⏳ Pending"
            pending_count += 1

        draft_data.append({
            'id': d.id,
            'study_id': d.study_id,
            'site': d.site,
            'start_date': d.start_date,
            'status': status,
            'is_pending': status == "⏳ Pending",
        })

    # Save pending count in session for navbar notifications
    request.session['PENDING_DRAFT_COUNT'] = pending_count

    return render(request, 'anthology/drafts.html', {'drafts': draft_data})


def approval_review(request, draft_id):
    role = request.session.get('USER_ROLE')
    if role not in ('ADMIN', 'APPROVER'):
        return HttpResponseForbidden("Forbidden")
    draft = get_object_or_404(DraftReport, pk=draft_id)
    if request.method == 'POST':
        # a minimal placeholder to record approval - expand validation in production
        from .models import Approval
        passed = request.POST.get('passed') == 'pass'
        Approval.objects.update_or_create(report=draft, defaults={
            'passed': passed,
            'approved_by': request.session.get('USER_ID', 'dev.user'),
            'approved_on': __import__('django.utils.timezone').utils.timezone.now()
        })
        return redirect('anthology:drafts')
    return render(request, 'anthology/approvals.html', {'draft': draft})


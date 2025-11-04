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
from .services.ldap_service import get_site_members, get_region_members
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponseForbidden
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from .decorators import role_required
from django.contrib.auth.decorators import login_required
from .decorators import role_required
import json
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponseForbidden
from django.utils import timezone



def login_view(request):
    # Redirect to SSO login (placeholder)
    # sso_login = f"{settings.SSO_HOSTNAME}{settings.SSO_LOGIN_URI}"
    # return redirect(sso_login)
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            # Determine role from Django group
            groups = list(user.groups.values_list('name', flat=True))
            role = groups[0] if groups else 'VIEWER'

            # Store session details
            request.session['USER_ROLE'] = role
            request.session['USER_NAME'] = user.get_full_name() or user.username
            request.session['USER_ID'] = user.username

            messages.success(request, f"Welcome, {user.username}! Role: {role}")
            return redirect('anthology:drafts')
        else:
            messages.error(request, "Invalid username or password.")
    return render(request, 'anthology/login.html')


def logout_view(request):
    logout(request)
    messages.success(request, "Logged out successfully.")
    return redirect('anthology:login')

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
'''
def logout_view(request):
    request.session.flush()
    sso_logout = f"{settings.SSO_HOSTNAME}{settings.SSO_LOGOUT_URI}"
    return redirect(sso_logout)  '''

@login_required(login_url='anthology:login')
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


# @role_required(['MANUFACTURER'])
def report_detail(request, report_id):
    report = get_object_or_404(FinalReport, pk=report_id)
    # create a signed URL or proxy the blob; here we create blob url (SAS must be appended)
    blob_url = azure_blob.get_blob_url(report.filename, report_type='final')
    return render(request, 'anthology/report_detail.html', {'report': report, 'blob_url': blob_url})

@login_required(login_url='anthology:login')
@role_required(['ADMIN', 'APPROVER'])
def drafts_list(request):
    drafts = DraftReport.objects.all().select_related('approval').order_by('-start_date')

    draft_data = []
    pending_count = 0

    for d in drafts:
        if hasattr(d, 'approval'):
            status = "✅ Passed" if d.approval.passed else "❌ Failed"
            is_pending = False
        else:
            status = "⏳ Pending"
            is_pending = True
            pending_count += 1

        draft_data.append({
            'id': d.id,
            'region': d.region,
            'study_id': d.study_id,
            'site': d.site,
            'batch': d.batch,
            'product': d.product,
            'start_date': d.start_date,
            'end_date': d.end_date,
            'status': status,
            'is_pending': is_pending,
            'pdf_url': d.test_pdf.url if d.test_pdf else None,
        })

    request.session['PENDING_DRAFT_COUNT'] = pending_count

    return render(request, 'anthology/drafts.html', {'drafts': draft_data})


@role_required(['ADMIN', 'APPROVER'])
def approval_review(request, draft_id):
    """QA Approver reviews draft report — select recipients and pass/fail outcome."""
    role = request.session.get('USER_ROLE')
    if role not in ('ADMIN', 'APPROVER'):
        return HttpResponseForbidden("Forbidden")

    draft = get_object_or_404(DraftReport, pk=draft_id)

    # Step 1: GET request → show approval dialog with LDAP-based recipient list
    if request.method == 'GET':
        try:
            site_recipients = get_site_members(draft.site) or []
            region_recipients = get_region_members(draft.region) or []
        except Exception as e:
            print(f"LDAP fetch error: {e}")
            site_recipients, region_recipients = [], []

        # merge and remove duplicates
        default_emails = sorted(set(site_recipients + region_recipients))
        mail_list = ", ".join(default_emails) if default_emails else settings.DEFAULT_FROM_EMAIL

        return render(
            request,
            'anthology/approvals.html',
            {'draft': draft, 'default_mail_list': mail_list},
        )

    # Step 2: POST request → save approval + update FinalReport + send email
    if request.method == 'POST':
        passed = request.POST.get('passed') == 'pass'
        recipients = request.POST.get('mail_recipients', '').strip()

        approval, _ = Approval.objects.update_or_create(
            report=draft,
            defaults={
                'passed': passed,
                'approved_by': request.session.get('USER_ID', 'dev.user'),
                'approved_on': timezone.now(),
                'mail_recipients': recipients,
            },
        )

        # Update or create FinalReport entry
        FinalReport.objects.update_or_create(
            study_id=draft.study_id,
            site=draft.site,
            defaults={
                'filename': draft.filename.replace("draft", "final"),
                'region': draft.region,
                'batch': draft.batch,
                'product': draft.product,
                'passed': passed,
                'approved_by': approval.approved_by,
                'approved_on': approval.approved_on,
                'start_date': draft.start_date,
                'end_date': draft.end_date,
            },
        )

        # Send notification email
        if recipients:
            try:
                email_list = [e.strip() for e in recipients.split(',') if e.strip()]
                subject = f"[{draft.study_id}] Report {'PASSED ✅' if passed else 'FAILED ❌'}"
                message = (
                    f"Report: {draft.filename}\n"
                    f"Study: {draft.study_id}\n"
                    f"Site: {draft.site}\n"
                    f"Region: {draft.region}\n"
                    f"Status: {'PASSED ✅' if passed else 'FAILED ❌'}\n"
                    f"Approved by: {approval.approved_by}\n"
                    f"Date: {approval.approved_on.strftime('%Y-%m-%d %H:%M')}"
                )
                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, email_list, fail_silently=True)
            except Exception as e:
                print(f"Email sending failed: {e}")

        # Redirect back to drafts list
        return redirect('anthology:drafts')
    


@login_required(login_url='anthology:login')
@role_required(['ADMIN', 'APPROVER'])
def processing_logs(request):
    """Show processing or approval activity logs."""
    # Temporary placeholder logs — later this can pull from DB or audit table
    logs = [
        {"timestamp": "2025-11-02 10:22:34", "action": "Draft ST001 approved", "user": "approver_user"},
        {"timestamp": "2025-11-02 09:55:11", "action": "Final report uploaded", "user": "admin_user"},
        {"timestamp": "2025-11-01 17:12:08", "action": "Draft ST002 failed QA", "user": "approver_user"},
    ]
    return render(request, 'anthology/logs.html', {"logs": logs})



@role_required(['ADMIN', 'APPROVER'])
def review_draft(request, draft_id):
    """Review a specific draft report."""
    draft = get_object_or_404(DraftReport, pk=draft_id)
    return render(request, 'anthology/review_draft.html', {'draft': draft})


@csrf_exempt
@login_required(login_url='anthology:login')
@role_required(['ADMIN', 'APPROVER'])
def approval_review(request, draft_id):
    draft = get_object_or_404(DraftReport, pk=draft_id)
    if request.method == 'POST':
        data = json.loads(request.body.decode('utf-8'))
        passed = data.get('passed', False)
        recipients = data.get('recipients', [])

        Approval.objects.update_or_create(
            report=draft,
            defaults={
                'passed': passed,
                'approved_by': request.session.get('USER_ID', 'system'),
                'approved_on': timezone.now()
            }
        )

        # Send email (to be added next)
        # Log action in AccessLog

        return JsonResponse({'status': 'ok'})
    return HttpResponseForbidden()








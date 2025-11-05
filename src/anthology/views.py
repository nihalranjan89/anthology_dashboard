from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseForbidden, HttpResponse
from django.http import JsonResponse
import json
from .models import DraftReport, Approval

from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
import json
from .models import DraftReport, Approval


from django.conf import settings
from .models import FinalReport, DraftReport, Approval
from .services import azure_blob, saml_auth, ldap_service
from django.utils.dateparse import parse_date
from datetime import datetime
from django.db.models import Q
from django.shortcuts import render, get_object_or_404
from .models import DraftReport as Draft
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
from django.contrib.auth.models import Group, User
from .decorators import role_required
from django.contrib.auth.decorators import login_required
from .decorators import role_required
import json
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponseForbidden
from django.utils import timezone

import os
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect
from onelogin.saml2.auth import OneLogin_Saml2_Auth




def init_saml_auth(request):
    """
    Initializes a SAML auth object based on the current request and local SAML settings.
    """
    saml_dir = os.path.join(os.path.dirname(__file__), "saml")
    req = {
        "https": "on" if request.is_secure() else "off",
        "http_host": request.META["HTTP_HOST"],
        "script_name": request.META["PATH_INFO"],
        "get_data": request.GET.copy(),
        "post_data": request.POST.copy(),
    }
    return OneLogin_Saml2_Auth(req, custom_base_path=saml_dir)
 
 
def login_saml(request):
    """
    Initiates login redirect to Identity Provider (IdP)
    """
    auth = init_saml_auth(request)
    return redirect(auth.login())
 
 
def acs(request):
    """
    Assertion Consumer Service — handles the response from IdP
    """
    auth = init_saml_auth(request)
    auth.process_response()
    errors = auth.get_errors()
 
    if errors:
        return HttpResponse(f"SAML Error: {errors}")
 
    # Extract user data from SAML response
    saml_attrs = auth.get_attributes()
    request.session["USER_ID"] = auth.get_nameid()
    request.session["USER_NAME"] = saml_attrs.get("cn", ["Unknown"])[0]
    request.session["USER_ROLE"] = saml_attrs.get("memberOf", ["VIEWER"])[0]
    request.session["USER_EMAIL"] = saml_attrs.get("emailAddress", [""])[0]
 
    return redirect("anthology:reports")
 
 
def metadata(request):
    """
    Exposes SP metadata for IdP registration
    """
    from onelogin.saml2.settings import OneLogin_Saml2_Settings
    saml_dir = os.path.join(os.path.dirname(__file__), "saml")
    saml_settings = OneLogin_Saml2_Settings(custom_base_path=saml_dir, sp_validation_only=True)
    metadata = saml_settings.get_sp_metadata()
 
    return HttpResponse(metadata, content_type="text/xml")

def login_view(request):
    # Redirect to SSO login (placeholder)
    # sso_login = f"{settings.SSO_HOSTNAME}{settings.SSO_LOGIN_URI}"
    # return redirect(sso_login)
    # Always clear any existing session before showing login form

    if request.user.is_authenticated:
        logout(request)
        request.session.flush()

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            # Determine role from Django groups with priority
            groups = list(user.groups.values_list('name', flat=True))
            
            if 'ADMIN' in groups:
                role = 'ADMIN'
            elif 'APPROVER' in groups:
                role = 'APPROVER'
            elif 'MANUFACTURER' in groups:
                role = 'MANUFACTURER'
            else:
                role = 'VIEWER'

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
    logout(request) # Django logout
    request.session.flush()      # Clears all session data
    messages.success(request, "Logged out successfully.")
    return redirect('anthology:login')

def login_callback(request):
    user = User.objects.get(username="dev.user")
    groups = list(user.groups.values_list('name', flat=True))

    if 'ADMIN' in groups:
        role = 'ADMIN'
    elif 'APPROVER' in groups:
        role = 'APPROVER'
    elif 'MANUFACTURER' in groups:
        role = 'MANUFACTURER'
    else:
        role = 'VIEWER'

    request.session['USER_DISPLAY_NAME'] = 'Dev User'
    request.session['USER_ID'] = 'user.username'
    request.session['USER_ROLE'] = role 
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
    region = request.GET.get('region', '').strip()
    product = request.GET.get('product', '').strip()
    batch = request.GET.get('batch', '').strip()
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    status = request.GET.get('status', 'final').lower()      # 'draft' or 'final'
    pass_filter = request.GET.get('pass_status', '').lower() # 'passed' or 'failed'
    sort_field = request.GET.get('sort', '')   
    approved_by = request.GET.get('approved_by', '').strip()
    approved_on = request.GET.get('approved_on', '')

    # Choose model based on report type
    model = FinalReport if status == 'final' else DraftReport
    queryset = model.objects.all()

    # 🔹 Apply filters
    if site:
        queryset = queryset.filter(site__icontains=site)
    if region:
        queryset = queryset.filter(region__icontains=region)
    if product:
        queryset = queryset.filter(product__icontains=product)
    if batch:
        queryset = queryset.filter(batch__icontains=batch)
    if start_date:
        queryset = queryset.filter(start_date__gte=parse_date(start_date))
    if end_date:
        queryset = queryset.filter(end_date__lte=parse_date(end_date))
    if approved_by:
        queryset = queryset.filter(approved_by__icontains=approved_by)
    if approved_on:
        queryset = queryset.filter(approved_on__gte=parse_date(approved_on))

    # 🔹 If viewing FINAL reports, allow pass/fail filter
    if status == 'final':
        if pass_filter == 'passed':
            queryset = queryset.filter(passed=True)
        elif pass_filter == 'failed':
            queryset = queryset.filter(passed=False)

    else:
        queryset = queryset.filter(approval__isnull=True)

    # 🔹 If viewing DRAFT reports, only show those without approval (pending)
    # if status == 'draft':
    #     queryset = queryset.filter(approval__isnull=True)

    # Sort newest first
    # order_field = '-approved_on' if status == 'final' else '-start_date'
    # reports = queryset.order_by(order_field)

    valid_fields = ['region', 'site', 'batch', 'product', 'start_date', 'end_date', 'approved_on','approved_by']
    if sort_field.lstrip('-') in valid_fields:
        queryset = queryset.order_by(sort_field)
    else:
        queryset = queryset.order_by('-approved_on' if status == 'final' else '-start_date')

    context = {
        'reports': queryset,
        'selected_site': site,
        'region': region,
        'product': product,
        'batch': batch,
        'selected_status': status,
        'start_date': start_date,
        'end_date': end_date,
        'pass_filter': pass_filter,
        'approved_by': approved_by,
        'approved_on': approved_on,  
    }
    return render(request, 'anthology/reports.html', context)

# @role_required(['MANUFACTURER'])
def report_detail(request, report_id):
    report = get_object_or_404(FinalReport, pk=report_id)
    # create a signed URL or proxy the blob; here we create blob url (SAS must be appended)
    blob_url = azure_blob.get_blob_url(report.filename, report_type='final')
    return render(request, 'anthology/report_detail.html', {'report': report, 'blob_url': blob_url})

@require_POST
@role_required(['ADMIN', 'APPROVER'])
def submit_approval(request, draft_id):
    """Handle AJAX POST request to submit approval."""
    draft = get_object_or_404(DraftReport, pk=draft_id)
    
    data = json.loads(request.body)

    passed = data.get("passed")
    comments = data.get("comments", "")
    recipients = data.get("recipients", [])

    approval, _ = Approval.objects.get_or_create(report=draft)
    approval.passed = passed
    approval.comments = comments
    approval.recipients = recipients
    approval.approved_by = request.user.username
    approval.approved_on = timezone.now()
    approval.save()

    return JsonResponse({"success": True})

@login_required(login_url='anthology:login')
@role_required(['ADMIN', 'APPROVER'])
def drafts_list(request):
    """List only draft reports that still need approval (pending ones)."""
    role = request.session.get('USER_ROLE')
    if role not in ('ADMIN', 'APPROVER'):
        return HttpResponseForbidden("Forbidden")

    drafts = (
        DraftReport.objects
        .filter(approval__isnull=True)   # ✅ Only pending drafts
        .order_by('-start_date')
    )

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
            'status': status,
            'start_date': d.start_date,
            'end_date': d.end_date,
            'is_pending': is_pending,
            'pdf_url': d.test_pdf.url if d.test_pdf else None,
        })

    request.session['PENDING_DRAFT_COUNT'] = drafts.count()

    return render(request, 'anthology/drafts.html', {'drafts': draft_data})


# @role_required(['MANUFACTURER'])
def report_detail(request, report_id):
    report = get_object_or_404(FinalReport, pk=report_id)
    # create a signed URL or proxy the blob; here we create blob url (SAS must be appended)
    blob_url = azure_blob.get_blob_url(report.filename, report_type='final')
    return render(request, 'anthology/report_detail.html', {'report': report, 'blob_url': blob_url})




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


# @login_required(login_url='anthology:login')
# @role_required(['ADMIN', 'APPROVER'])
# def draft_detail(request, draft_id):
#     """Show details for a single draft, including PDF and approval status."""
#     role = request.session.get('USER_ROLE')
#     if role not in ('ADMIN', 'APPROVER'):
#         return HttpResponseForbidden("Forbidden")

#     # Fetch the specific draft report
#     draft = get_object_or_404(DraftReport, pk=draft_id)

#     # Determine status and pending state
#     if hasattr(draft, 'approval'):
#         status = "✅ Passed" if draft.approval.passed else "❌ Failed"
#         is_pending = False
#     else:
#         status = "⏳ Pending"
#         is_pending = True

#     # Get the PDF URL if available
#     pdf_url = draft.test_pdf.url if draft.test_pdf else None

#     context = {
#         'draft': draft,
#         'status': status,
#         'is_pending': is_pending,
#         'pdf_url': pdf_url,
#     }

#     return render(request, 'anthology/draft_detail.html', context)

@login_required(login_url='anthology:login')
@role_required(['ADMIN', 'APPROVER'])
def draft_detail(request, draft_id):
    role = request.session.get('USER_ROLE')
    if role not in ('ADMIN', 'APPROVER'):
        return HttpResponseForbidden("Forbidden")

    draft = get_object_or_404(DraftReport, pk=draft_id)
    AccessLog.objects.create(
        user=role,
        action="Viewed Draft",
        subject=f"{draft.study_id} - {draft.filename}"
    )

    if hasattr(draft, 'approval'):
        status = "✅ Passed" if draft.approval.passed else "❌ Failed"
        is_pending = False
    else:
        status = "⏳ Pending"
        is_pending = True

    pdf_url = draft.test_pdf.url if draft.test_pdf else None

    context = {
        'draft': draft,
        'status': status,
        'is_pending': is_pending,
        'pdf_url': pdf_url,
    }
    return render(request, 'anthology/draft_detail.html', context)


from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.http import JsonResponse, HttpResponseForbidden
import json
from .models import DraftReport, Approval, FinalReport, ProcessLog, AccessLog
from django.shortcuts import get_object_or_404
from django.conf import settings


@csrf_exempt
@login_required(login_url='anthology:login')
@role_required(['ADMIN', 'APPROVER'])
def approval_review(request, draft_id):
    """Handles approval submission from the draft detail page."""
    if request.method != 'POST':
        return HttpResponseForbidden()

    try:
        data = json.loads(request.body.decode('utf-8'))
        passed = data.get('passed', False)
        recipients = data.get('recipients', [])
        comments = data.get('comments', '')
        user_id = request.session.get('USER_ID', 'system')

        draft = get_object_or_404(DraftReport, pk=draft_id)

        # ✅ Save approval record
        approval, _ = Approval.objects.update_or_create(
            report=draft,
            defaults={
                'passed': passed,
                'approved_by': user_id,
                'approved_on': timezone.now(),
                'comments': comments,
            }
        )

        # ✅ Update or create final report
        FinalReport.objects.update_or_create(
            study_id=draft.study_id,
            site=draft.site,
            defaults={
                'filename': draft.filename.replace("draft", "final"),
                'region': draft.region,
                'batch': draft.batch,
                'product': draft.product,
                'passed': passed,
                'approved_by': user_id,
                'approved_on': timezone.now(),
                'start_date': draft.start_date,
                'end_date': draft.end_date,
            },
        )

        # ✅ Log this action in ProcessLog
        ProcessLog.objects.create(
            timestamp=timezone.now(),
            study=draft.study_id,
            region=draft.region,
            site=draft.site,
            product=draft.product,
            response=f"Draft ID {draft.id}",
            state="PASSED" if passed else "FAILED",
            text=f"Report '{draft.filename}' was {'approved' if passed else 'rejected'} by {user_id}. Comments: {comments}",
        )

        AccessLog.objects.create(
        user=request.session.get('USER_ID', 'system'),
        action=f"{'Approved' if passed else 'Rejected'} Draft",
        subject=f"{draft.study_id}"
    )


        # ✅ Optional: Send notification email
        if recipients:
            try:
                from django.core.mail import send_mail
                subject = f"[{draft.study_id}] Report {'PASSED ✅' if passed else 'FAILED ❌'}"
                message = (
                    f"Report: {draft.filename}\n"
                    f"Study: {draft.study_id}\n"
                    f"Site: {draft.site}\n"
                    f"Region: {draft.region}\n"
                    f"Status: {'PASSED ✅' if passed else 'FAILED ❌'}\n"
                    f"Approved by: {user_id}\n"
                    f"Date: {timezone.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                    f"Comments: {comments}"
                )
                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=True)
            except Exception as e:
                print(f"⚠️ Email sending failed: {e}")

        print(f"✅ Approval logged and FinalReport updated for {draft.study_id}")
        return JsonResponse({'status': 'success'})

    except Exception as e:
        print(f"⚠️ Error in approval_review: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

# Processing Logs View
from django.core.paginator import Paginator
from django.db.models import Q

@login_required(login_url='anthology:login')
@role_required(['ADMIN', 'APPROVER'])
def processing_logs(request):
    return render(request, "anthology/processing_logs.html")

@login_required(login_url='anthology:login')
@role_required(['ADMIN', 'APPROVER'])
def processing_logs_data(request):
    page = int(request.GET.get("page", 1))
    search = request.GET.get("search", "")
    
    logs = ProcessLog.objects.all()

    # Simple search filter
    if search:
        logs = logs.filter(
            Q(region__icontains=search) |
            Q(site__icontains=search) |
            Q(study__icontains=search) |
            Q(product__icontains=search) |
            Q(text__icontains=search) |
            Q(state__icontains=search)
        )

    paginator = Paginator(logs, 30)  # 30 logs per scroll
    page_obj = paginator.get_page(page)

    data = [{
        "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M"),
        "region": log.region,
        "site": log.site,
        "study": log.study,
        "product": log.product,
        "response": log.response,
        "state": log.state,
        "text": log.text,
    } for log in page_obj]

    return JsonResponse({
        "logs": data,
        "has_next": page_obj.has_next()
    })


@login_required(login_url='anthology:login')
@role_required(['ADMIN'])   # ONLY ADMIN
def access_logs(request):
    logs = AccessLog.objects.all()[:200]  # return first 200 to simulate endless scroll
    return render(request, "anthology/access_logs.html", {"logs": logs})

from django.urls import path
from . import views

app_name = 'anthology'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('login_cb/', views.login_callback, name='login_cb'),
    path('logout/', views.logout_view, name='logout'),
    path('reports/', views.reports_list, name='reports'),
    path('drafts/<int:draft_id>/', views.draft_detail, name='draft_detail'),
    path("login_saml/", views.login_saml, name="login_saml"),
    path("acs/", views.acs, name="acs"),
    path("metadata/", views.metadata, name="metadata"),
    path('reports/view/<int:report_id>/', views.report_detail, name='report_detail'),
    path('drafts/', views.drafts_list, name='drafts'),
    path('approvals/review/<int:draft_id>/', views.approval_review, name='approval_review'),
    path('', views.reports_list, name='home'),
    path('drafts/review/<int:draft_id>/', views.review_draft, name='review_draft'),
    # Processing logs URLs
    path("logs/processing/", views.processing_logs, name="processing_logs"),
    path("logs/processing/data/", views.processing_logs_data, name="processing_logs_data"),
    path('logs/access', views.access_logs, name="access_logs"),


]
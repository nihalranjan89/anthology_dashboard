from django.urls import path
from . import views

app_name = 'anthology'

urlpatterns = [
    #path('login/', views.login_view, name='login'),
    path('login/', views.login_view, name='login'),
    path('login_cb/', views.login_callback, name='login_cb'),
    path('logout/', views.logout_view, name='logout'),
    path('reports/', views.reports_list, name='reports'),
    path('reports/view/<int:report_id>/', views.report_detail, name='report_detail'),
    path('drafts/', views.drafts_list, name='drafts'),
    path('approvals/review/<int:draft_id>/', views.approval_review, name='approval_review'),
    path('', views.reports_list, name='home'),
    path('logs/processing/', views.processing_logs, name='processing_logs'),
    path('drafts/review/<int:draft_id>/', views.review_draft, name='review_draft'),


]

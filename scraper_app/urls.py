from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('scrape/start/', views.start_scrape, name='start_scrape'),
    path('job/<int:job_id>/', views.job_detail, name='job_detail'),
    path('job/<int:job_id>/delete/', views.delete_job, name='delete_job'),
    path('job/<int:job_id>/cancel/', views.cancel_job, name='cancel_job'),
    path('api/job/<int:job_id>/status/', views.job_status_api, name='job_status_api'),
    path('api/job/<int:job_id>/cancel/', views.cancel_job, name='cancel_job_api'),
    path('export/excel/', views.export_excel, name='export_excel'),
    path('export/csv/', views.export_csv, name='export_csv'),
    path('clear-all/', views.clear_all_data, name='clear_all_data'),
]

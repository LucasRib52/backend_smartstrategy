# dashboard/urls.py
from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('dashboard/', views.DashboardAPIView.as_view(), name='dashboard_api'),
    path('dashboard/all-years/', views.AllYearsDashboardAPIView.as_view(), name='all_years_dashboard_api'),
    path('dashboard/available-years/', views.AvailableYearsAPIView.as_view(), name='available_years_api'),
]

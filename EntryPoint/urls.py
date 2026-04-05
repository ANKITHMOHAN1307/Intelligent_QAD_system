from django.urls import path

from . import views

urlpatterns = [
    path('', views.splash, name='splash'),
    path('main/', views.main, name='main'),
    path('analyze-barcode/', views.analyze_barcode, name='analyze_barcode'),
    path('task-status/<str:task_id>/',views.task_status, name = 'task_status')
]


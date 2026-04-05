from django.urls import path

from . import views

urlpatterns = [
    path('', views.splash, name='splash'),
    path('main/', views.main, name='main'),
    path('analyze-ocr-label/', views.analyze_ocr_label, name='analyze_ocr_label'),
]

from . import views
from django.urls import path
# app level url configurations are made here
urlpatterns = [
    path('',views.splash, name ='splash'), 
    path('main/', views.main, name = 'main'),
    # path('open_camera/', views.open_camera, name = 'Camera')
    path('upload_image', views.upload_image, name = "uploadimage")
]
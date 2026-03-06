from django.shortcuts import render
from django.http import HttpResponse
# import cv2

import os 

def open_camera(request):
    return HttpResponse("Camera function")

def splash(request):
    return render (request, "splash.html")

def main(request):
    return render(request, "main.html")

def upload_image(request):
    if request.method == "POST" and request.FILES['image']:
        image = request.FILES['image']
        file = default_storage.save(f'uploads/{image.name}', image)
        return JsonResponse({'status': 'success', 'filename': file})
    return JsonResponse({'status': 'error'})

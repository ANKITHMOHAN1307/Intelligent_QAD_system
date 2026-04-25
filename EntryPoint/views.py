import json
from datetime import datetime
from urllib import error, request as urllib_request
from django.views.decorators.csrf import ensure_csrf_cookie
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from .tasks import run_ocr_fallback


OPEN_FOOD_FACTS_URL = "https://world.openfoodfacts.org/api/v2/product/{barcode}.json"

from celery.result import AsyncResult


def splash(request):
    return render(request, "splash.html")


@ensure_csrf_cookie
def main(request):
    return render(request, "main.html")


def _parse_expiry_status(raw_value):
    if not raw_value:
        return {
            "raw": "Not available",
            "days_left": None,
            "status": "Unknown",
            "message": "Expiry date is not available in this barcode dataset.",
        }

    formats = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d"]
    parsed_date = None
    for date_format in formats:
        try:
            parsed_date = datetime.strptime(raw_value.strip(), date_format).date()
            break
        except (ValueError, TypeError):
            continue

    if parsed_date is None:
        return {
            "raw": raw_value,
            "days_left": None,
            "status": "Unknown",
            "message": "Expiry date format is not recognized.",
        }

    days_left = (parsed_date - datetime.utcnow().date()).days
    if days_left < 0:
        status, message = "Expired", "Product appears to be past expiry date."
    elif days_left <= 30:
        status, message = "Near Expiry", "Product should be consumed soon."
    else:
        status, message = "Safe Window", "Product is not near expiry based on available data."

    return {"raw": raw_value, "days_left": days_left, "status": status, "message": message}


def _nutrition_quality(nutriments):
    sugar = float(nutriments.get("sugars_100g") or 0)
    salt = float(nutriments.get("salt_100g") or 0)
    fat = float(nutriments.get("fat_100g") or 0)

    score = 100
    if sugar > 22.5:
        score -= 30
    elif sugar > 10:
        score -= 15

    if salt > 1.5:
        score -= 30
    elif salt > 0.3:
        score -= 15

    if fat > 17.5:
        score -= 20
    elif fat > 3:
        score -= 10

    if score >= 75:
        return {"score": score, "quality": "Good", "message": "Balanced nutrition profile for basic screening."}
    if score >= 50:
        return {"score": score, "quality": "Moderate", "message": "Contains medium-high levels of sugar/salt/fat."}
    return {"score": max(score, 0), "quality": "Caution", "message": "High levels detected; consume in moderation."}


@require_POST
def analyze_barcode(request):
    payload = {}
    if request.body:
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {}

    barcode = str(payload.get("barcode") or request.POST.get("barcode") or "").strip()
    if not barcode:
        return JsonResponse({"status": "error", "message": "Barcode is required."}, status=400)

    # ✅ Frontend signals Quagga failed — skip API, go straight to Celery
    if barcode == 'OCR_FALLBACK':
        task =run_ocr_fallback.delay()
        return JsonResponse({
            "status": "fallback",
            "message": "OCR task queued.",
            "task_id": task.id,
        }, status=202)

    
    try:
        with urllib_request.urlopen(OPEN_FOOD_FACTS_URL.format(barcode=barcode), timeout=12) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (error.HTTPError, error.URLError, TimeoutError, json.JSONDecodeError):
        task = run_ocr_fallback.delay()
        return JsonResponse(
            {
                "status": "fallback",
                "message": "Unable to fetch product details; OCR task queued.",
                "task_id": task.id,
            },
            status=202,
        )

    product = result.get("product", {})
    if result.get("status") != 1 or not product:
        task = task_status.delay()
        return JsonResponse(
            {
                "status": "fallback",
                "message": "NO Product Data found in barcode response ; OCR task queued",
                "task_id": task.id,
            },
            status=202,
        )

    nutriments = product.get("nutriments") or {}
    response_data = {
        "status": "success",
        "barcode": barcode,
        "product_name": product.get("product_name", "Unknown product"),
        "brand": product.get("brands", "Unknown brand"),
        "ingredients": product.get("ingredients_text_en") or product.get("ingredients_text") or "Not available",
        "manufacturing_date": product.get("manufacturing_places", "Not available"),
        "expiry": _parse_expiry_status(product.get("expiration_date")),
        "nutrition": {
            "energy_kcal_100g": nutriments.get("energy-kcal_100g") or nutriments.get("energy-kcal"),
            "proteins_100g": nutriments.get("proteins_100g"),
            "carbohydrates_100g": nutriments.get("carbohydrates_100g"),
            "fat_100g": nutriments.get("fat_100g"),
            "sugars_100g": nutriments.get("sugars_100g"),
            "salt_100g": nutriments.get("salt_100g"),
            "fiber_100g": nutriments.get("fiber_100g"),
        },
        "quality": _nutrition_quality(nutriments),
        "image": product.get("image_front_url") or product.get("image_url"),
    }
    return JsonResponse(response_data)


def task_status(request, task_id):
    result = AsyncResult(task_id)
    return JsonResponse({
        "task_id": task_id,
        "status": result.status,
        "result": result.result if result.ready() else None,
    })


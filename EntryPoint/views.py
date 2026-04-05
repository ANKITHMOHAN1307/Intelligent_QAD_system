import json
import os
import tempfile
from datetime import datetime
from urllib import error, parse, request as urllib_request

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from .ocr_service import process_food_label

OPEN_FOOD_FACTS_URL = "https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
OPEN_FOOD_FACTS_SEARCH_URL = "https://world.openfoodfacts.org/cgi/search.pl"


# -----------------------------
# BASIC PAGES
# -----------------------------
def splash(request):
    return render(request, "splash.html")


def main(request):
    return render(request, "main.html")


# -----------------------------
# EXPIRY PARSER
# -----------------------------
def _parse_expiry_status(raw_value):
    if not raw_value:
        return {
            "raw": "Not available",
            "days_left": None,
            "status": "Unknown",
            "message": "Expiry date not available.",
        }

    formats = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d"]

    for fmt in formats:
        try:
            parsed = datetime.strptime(raw_value.strip(), fmt).date()
            days_left = (parsed - datetime.utcnow().date()).days

            if days_left < 0:
                return {"raw": raw_value, "days_left": days_left, "status": "Expired"}
            elif days_left <= 30:
                return {"raw": raw_value, "days_left": days_left, "status": "Near Expiry"}
            else:
                return {"raw": raw_value, "days_left": days_left, "status": "Safe"}
        except:
            continue

    return {"raw": raw_value, "days_left": None, "status": "Unknown"}


# -----------------------------
# NUTRITION QUALITY
# -----------------------------
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

    return {
        "score": max(score, 0),
        "quality": "Good" if score >= 75 else "Moderate" if score >= 50 else "Caution",
    }


# -----------------------------
# BARCODE ANALYSIS
# -----------------------------
@require_POST
def analyze_barcode(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
        barcode = payload.get("barcode", "").strip()

        if not barcode:
            return JsonResponse({"error": "Barcode required"}, status=400)

        url = OPEN_FOOD_FACTS_URL.format(barcode=barcode)

        with urllib_request.urlopen(url, timeout=10) as res:
            data = json.loads(res.read().decode())

        product = data.get("product", {})

        if not product:
            return JsonResponse({"error": "Product not found"}, status=404)

        nutriments = product.get("nutriments", {})

        return JsonResponse({
            "product_name": product.get("product_name"),
            "brand": product.get("brands"),
            "ingredients": product.get("ingredients_text"),
            "nutrition": nutriments,
            "quality": _nutrition_quality(nutriments),
            "expiry": _parse_expiry_status(product.get("expiration_date")),
            "image": product.get("image_front_url"),
        })

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# -----------------------------
# OCR ANALYSIS (FIXED)
# -----------------------------
import json
import os
import tempfile
from datetime import datetime
from urllib import error, parse, request as urllib_request

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from .ocr_service import process_food_label

OPEN_FOOD_FACTS_URL = "https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
OPEN_FOOD_FACTS_SEARCH_URL = "https://world.openfoodfacts.org/cgi/search.pl"


# -----------------------------
# BASIC PAGES
# -----------------------------
def splash(request):
    return render(request, "splash.html")


def main(request):
    return render(request, "main.html")


# -----------------------------
# EXPIRY PARSER
# -----------------------------
def _parse_expiry_status(raw_value):
    if not raw_value:
        return {
            "raw": "Not available",
            "days_left": None,
            "status": "Unknown",
            "message": "Expiry date not available.",
        }

    formats = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d"]

    for fmt in formats:
        try:
            parsed = datetime.strptime(raw_value.strip(), fmt).date()
            days_left = (parsed - datetime.utcnow().date()).days

            if days_left < 0:
                return {"raw": raw_value, "days_left": days_left, "status": "Expired"}
            elif days_left <= 30:
                return {"raw": raw_value, "days_left": days_left, "status": "Near Expiry"}
            else:
                return {"raw": raw_value, "days_left": days_left, "status": "Safe"}
        except:
            continue

    return {"raw": raw_value, "days_left": None, "status": "Unknown"}


# -----------------------------
# NUTRITION QUALITY
# -----------------------------
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

    return {
        "score": max(score, 0),
        "quality": "Good" if score >= 75 else "Moderate" if score >= 50 else "Caution",
    }


# -----------------------------
# BARCODE ANALYSIS
# -----------------------------
@require_POST
def analyze_barcode(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
        barcode = payload.get("barcode", "").strip()

        if not barcode:
            return JsonResponse({"error": "Barcode required"}, status=400)

        url = OPEN_FOOD_FACTS_URL.format(barcode=barcode)

        with urllib_request.urlopen(url, timeout=10) as res:
            data = json.loads(res.read().decode())

        product = data.get("product", {})

        if not product:
            return JsonResponse({"error": "Product not found"}, status=404)

        nutriments = product.get("nutriments", {})

        return JsonResponse({
            "status": "suceess",
            "ocr_text":oc_text,
            "product_name": product.get("product_name"),
            "brand": product.get("brands"),
            "ingredients": product.get("ingredients_text"),
            "nutrition": nutriments,
            "quality": _nutrition_quality(nutriments),
            "expiry": _parse_expiry_status(product.get("expiration_date")),
            "image": product.get("image_front_url"),
        })

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# -----------------------------
# OCR ANALYSIS (FIXED)
# -----------------------------
@require_POST
def analyze_ocr_label(request):
    temp_file_path = None

    try:
        image_file = request.FILES.get("image")

        if not image_file:
            return JsonResponse({"error": "No image uploaded"}, status=400)

        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
            for chunk in image_file.chunks():
                temp_file.write(chunk)

            temp_file_path = temp_file.name

        # Process using OCR pipeline
        result = process_food_label(temp_file_path)

        return JsonResponse({
    "status": "success",
    "ocr_text": raw_text,
    "ingredients": ...,
    "nutrients": ...,
    "nutrition_per_100g": ...
})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

    finally:
        # Cleanup temp file
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
import json
from datetime import datetime
from urllib import error, parse, request as urllib_request

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from .ocr_service import analyze_label_image, image_file_to_base64

OPEN_FOOD_FACTS_URL = "https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
OPEN_FOOD_FACTS_SEARCH_URL = "https://world.openfoodfacts.org/cgi/search.pl"


def splash(request):
    return render(request, "splash.html")


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
        status = "Expired"
        message = "Product appears to be past expiry date."
    elif days_left <= 30:
        status = "Near Expiry"
        message = "Product should be consumed soon."
    else:
        status = "Safe Window"
        message = "Product is not near expiry based on available data."

    return {
        "raw": raw_value,
        "days_left": days_left,
        "status": status,
        "message": message,
    }


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
        quality = "Good"
        message = "Balanced nutrition profile for basic screening."
    elif score >= 50:
        quality = "Moderate"
        message = "Contains medium-high levels of sugar/salt/fat."
    else:
        quality = "Caution"
        message = "High levels detected; consume in moderation."

    return {"score": max(score, 0), "quality": quality, "message": message}


def _find_best_alternative(source_product):
    product_name = source_product.get("product_name") or ""
    brand = source_product.get("brands") or ""
    source_barcode = str(source_product.get("code") or "")

    search_terms = " ".join(part for part in [brand, product_name] if part).strip() or product_name
    if not search_terms:
        return None

    query = parse.urlencode(
        {
            "search_terms": search_terms,
            "search_simple": 1,
            "action": "process",
            "json": 1,
            "page_size": 20,
        }
    )

    try:
        with urllib_request.urlopen(f"{OPEN_FOOD_FACTS_SEARCH_URL}?{query}", timeout=12) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (error.HTTPError, error.URLError, TimeoutError, json.JSONDecodeError):
        return None

    candidates = result.get("products") or []
    ranked = []

    for candidate in candidates:
        candidate_code = str(candidate.get("code") or "")
        if source_barcode and candidate_code == source_barcode:
            continue

        nutriments = candidate.get("nutriments") or {}
        quality = _nutrition_quality(nutriments)

        ranked.append(
            {
                "name": candidate.get("product_name") or "Unknown product",
                "brand": candidate.get("brands") or "Unknown brand",
                "barcode": candidate_code or "N/A",
                "image": candidate.get("image_front_url") or candidate.get("image_url"),
                "nutrition": {
                    "energy_kcal_100g": nutriments.get("energy-kcal_100g") or nutriments.get("energy-kcal"),
                    "proteins_100g": nutriments.get("proteins_100g"),
                    "carbohydrates_100g": nutriments.get("carbohydrates_100g"),
                    "fat_100g": nutriments.get("fat_100g"),
                    "sugars_100g": nutriments.get("sugars_100g"),
                    "salt_100g": nutriments.get("salt_100g"),
                    "fiber_100g": nutriments.get("fiber_100g"),
                },
                "quality": quality,
            }
        )

    if not ranked:
        return None

    ranked.sort(key=lambda item: item["quality"]["score"], reverse=True)
    best = ranked[0]
    best["reason"] = (
        f"Selected from similar products with the highest nutrition quality score "
        f"({best['quality']['score']}/100)."
    )
    return best


@require_POST
def analyze_barcode(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid request payload."}, status=400)

    barcode = str(payload.get("barcode", "")).strip()
    if not barcode:
        return JsonResponse({"status": "error", "message": "Barcode is required."}, status=400)

    api_url = OPEN_FOOD_FACTS_URL.format(barcode=barcode)
    try:
        with urllib_request.urlopen(api_url, timeout=12) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (error.HTTPError, error.URLError, TimeoutError):
        return JsonResponse(
            {
                "status": "error",
                "message": "Unable to contact Open Food Facts service right now.",
            },
            status=502,
        )

    product = result.get("product", {})
    if result.get("status") != 1 or not product:
        return JsonResponse(
            {
                "status": "error",
                "message": "No product information found for this barcode.",
            },
            status=404,
        )

    ingredients = product.get("ingredients_text_en") or product.get("ingredients_text") or "Not available"
    nutriments = product.get("nutriments", {})

    nutrition = {
        "energy_kcal_100g": nutriments.get("energy-kcal_100g") or nutriments.get("energy-kcal"),
        "proteins_100g": nutriments.get("proteins_100g"),
        "carbohydrates_100g": nutriments.get("carbohydrates_100g"),
        "fat_100g": nutriments.get("fat_100g"),
        "sugars_100g": nutriments.get("sugars_100g"),
        "salt_100g": nutriments.get("salt_100g"),
        "fiber_100g": nutriments.get("fiber_100g"),
    }

    expiry_info = _parse_expiry_status(product.get("expiration_date"))
    quality = _nutrition_quality(nutriments)
    best_alternative = _find_best_alternative(product)

    response_data = {
        "status": "success",
        "barcode": barcode,
        "product_name": product.get("product_name", "Unknown product"),
        "brand": product.get("brands", "Unknown brand"),
        "ingredients": ingredients,
        "manufacturing_date": product.get("manufacturing_places", "Not available"),
        "expiry": expiry_info,
        "nutrition": nutrition,
        "quality": quality,
        "best_alternative": best_alternative,
        "image": product.get("image_front_url") or product.get("image_url"),
    }

    return JsonResponse(response_data)

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .ocr_service import process_food_label


@require_POST
def analyze_ocr_label(request):
    try:
        image_file = request.FILES.get("image")

        if not image_file:
            return JsonResponse({"error": "No image uploaded"}, status=400)

        result = process_food_label(image_file)

        return JsonResponse(result)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

    
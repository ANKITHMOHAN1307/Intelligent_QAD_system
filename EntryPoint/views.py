from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from .ocr_service import analyze_label_image


def splash(request):
    return render(request, "splash.html")


def main(request):
    return render(request, "main.html")


@require_POST
def analyze_ocr_label(request):
    image_file = request.FILES.get("image")
    if not image_file:
        return JsonResponse({"status": "error", "message": "Image file is required."}, status=400)

    try:
        ocr_data = analyze_label_image(image_file=image_file)
    except ValueError as exc:
        return JsonResponse({"status": "error", "message": str(exc)}, status=500)
    except RuntimeError as exc:
        return JsonResponse({"status": "error", "message": str(exc)}, status=502)

    return JsonResponse(
        {
            "status": "success",
            "ingredients": ", ".join(ocr_data.get("ingredients", [])) or "Not available",
            "ocr_text": ocr_data.get("raw_text", ""),
            "ocr_nutrients": ocr_data.get("nutrients", []),
            "nutrition": ocr_data.get("nutrition_per_100g", {}),
            "product_name": "OCR Label Analysis",
            "brand": "Extracted from uploaded label",
            "expiry": {
                "status": "OCR Only",
                "message": "No barcode or external database lookup is used in this mode.",
            },
            "quality": {
                "quality": "OCR Extraction",
                "score": "-",
                "message": "Nutritional chart is generated directly from OCR-detected values.",
            },
            "image": None,
        }
    )

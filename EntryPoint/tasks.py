from celery import shared_task

@shared_task
def run_ocr_fallback():
    # Placeholder until OCR branch is merged
    return {
        "status": "success",
        "message": "OCR task executed successfully — real OCR coming after merge.",
        "ingredients": [],
        "nutrients": [],
        "nutrition_per_100g": {},
    }
from celery import shared_task

from .ocr import run_ocr


@shared_task
def run_ocr_fallback() -> str:
    return run_ocr()

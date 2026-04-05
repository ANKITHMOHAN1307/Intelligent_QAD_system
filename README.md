# Intelligent-QAD-System

A Django-based **Smart Food Label OCR Analyzer** web app.

## What it does

- Upload a food label image (nutrition table + ingredients panel).
- Extract OCR text using **OCR.Space Cloud API**.
- Parse and display:
  - Ingredients list
  - Nutrient composition (normalized to per-100g when possible)
- Show results in a cleaner dashboard with:
  - User-friendly upload preview
  - OCR status feedback
  - Nutrition bar chart

## Project objective

This project aims to provide a web-based application that allows users to:

1. Upload an image of a packaged food label.
2. Extract useful nutrition and ingredient information directly from OCR.
3. View clear OCR output and nutrition indicators in an easy dashboard.

## Run locally

```bash
python manage.py migrate
python manage.py runserver
```

Open `http://127.0.0.1:8000/`.

## Environment variables

- `OCR_SPACE_API_KEY`: Required API key for OCR.Space.

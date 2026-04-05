# Intelligent-QAD-System

A Django-based **Smart Food Packet Scanner & Quality Analyzer** web app.

## What it does

- Scan a packaged food barcode using the **camera**.
- Upload an image and **decode barcode** from file.
- Send decoded barcode to **Open Food Facts** (`https://world.openfoodfacts.org/`) and fetch:
  - Product name and brand
  - Ingredients list
  - Nutrient composition
- Run basic quality checks:
  - Nutrition-based quality indicator score
  - Expiry risk status (when expiry metadata is available)
- Display all results in a visual dashboard with:
  - Animated cards and status messages
  - Nutrition bar chart

## Project objective

This project aims to provide a web-based application that allows users to:

1. Scan or upload an image of a packaged food product.
2. Extract useful information (expiry, manufacturing details when available, ingredients, nutrition).
3. Analyze if the product is likely safe and whether expiry is near.
4. View clear quality indicators in an easy dashboard.

## Run locally

```bash
python manage.py migrate
python manage.py runserver
```

Open `http://127.0.0.1:8000/`.

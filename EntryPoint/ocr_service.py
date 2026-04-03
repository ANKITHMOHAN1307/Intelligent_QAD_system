import os
import json
import base64
import easyocr
import numpy as np
from PIL import Image
from io import BytesIO
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# -----------------------------
# OCR PART (EasyOCR)
# -----------------------------
reader = easyocr.Reader(['en'], gpu=False)


def extract_text_from_image(image_file):
    """
    Converts uploaded image → raw OCR text
    """

    image = Image.open(image_file).convert("RGB")
    image_np = np.array(image)

    results = reader.readtext(image_np, detail=0)

    raw_text = " ".join(results)

    return raw_text


# -----------------------------
# AI ANALYSIS PART
# -----------------------------
def analyze_label_text(raw_text):
    """
    Sends OCR text → OpenAI → structured JSON
    """

    prompt = f"""
Extract structured food label data from the OCR text below.

Return STRICT JSON format:
{{
  "raw_text": "...",
  "ingredients": ["..."],
  "nutrients": [
    {{
      "name": "...",
      "value": number,
      "unit": "g|mg|kcal",
      "basis": "per_100g|per_serving"
    }}
  ]
}}

OCR TEXT:
{raw_text}
"""

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt,
        text={
            "format": {
                "type": "json_object"
            }
        }
    )

    return json.loads(response.output_text)


# -----------------------------
# NORMALIZATION
# -----------------------------
def normalize_per_100g(nutrients):
    """
    Converts all nutrients → per 100g
    """

    normalized = {}

    for n in nutrients:
        name = n["name"].lower()
        value = float(n["value"])
        basis = n.get("basis", "per_100g")

        if basis == "per_serving":
            # Assume 1 serving = 30g (can be improved later)
            value = value * (100 / 30)

        normalized[name] = round(value, 2)

    return normalized


# -----------------------------
# MAIN PIPELINE
# -----------------------------
def process_food_label(image_file):
    """
    Full pipeline:
    Image → OCR → AI → Clean Output
    """

    raw_text = extract_text_from_image(image_file)

    ai_data = analyze_label_text(raw_text)

    nutrients = ai_data.get("nutrients", [])

    return {
        "raw_text": raw_text,
        "ingredients": ai_data.get("ingredients", []),
        "nutrients": nutrients,
        "nutrition_per_100g": normalize_per_100g(nutrients),
    }
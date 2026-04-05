import os
import json
import requests
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# -----------------------------
# OCR PART (OCR.Space API)
# -----------------------------
def extract_text_from_image(image_path):
    url = "https://api.ocr.space/parse/image"

    with open(image_path, "rb") as f:
        response = requests.post(
            url,
            files={"file": f},
            data={
                "apikey": "K83445173588957",  # replace if needed
                "language": "eng"
            }
        )

    result = response.json()

    if result.get("IsErroredOnProcessing"):
        raise Exception(result.get("ErrorMessage"))

    return result["ParsedResults"][0]["ParsedText"]


# -----------------------------
# AI ANALYSIS PART
# -----------------------------
def analyze_label_text(raw_text):
    prompt = f"""
Extract structured food label data from the OCR text below.

Return STRICT JSON:
{{
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
        input=prompt
    )

    output_text = ""

    for item in response.output:
        if hasattr(item, "content"):
            for c in item.content:
                if hasattr(c, "text"):
                    output_text += c.text

    try:
        return json.loads(output_text)
    except Exception as e:
        print("AI RAW OUTPUT:\n", output_text)
        raise Exception("Invalid JSON from AI")

    


# -----------------------------
# NORMALIZATION
# -----------------------------
def normalize_per_100g(nutrients):
    normalized = {}

    for n in nutrients:
        try:
            name = n["name"].lower()
            value = float(n["value"])
            basis = n.get("basis", "per_100g")

            if basis == "per_serving":
                value = value * (100 / 30)

            normalized[name] = round(value, 2)
        except:
            continue

    return normalized


# -----------------------------
# MAIN PIPELINE
# -----------------------------
def process_food_label(image_path):

    raw_text = extract_text_from_image(image_path)

    ai_data = analyze_label_text(raw_text)

    nutrients = ai_data.get("nutrients", [])

    return {
        "raw_text": raw_text,
        "ingredients": ai_data.get("ingredients", []),
        "nutrients": nutrients,
        "nutrition_per_100g": normalize_per_100g(nutrients),
    }


# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    result = process_food_label("C:/PROJECT/Intelligent-QAD-System/nutrition_en.8.full.jpg")
    print(json.dumps(result, indent=2))
import os
import json
import requests
import re
from groq import Groq
import base64
from urllib import parse, error, request as urllib_request
from dotenv import load_dotenv
load_dotenv()  # 

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

OCR_SPACE_API_URL = "https://api.ocr.space/parse/image"

# -----------------------------
# AI ANALYSIS PART
# -----------------------------
def analyze_label_text(raw_text):
    prompt = f"""
You are a food label parser. The text below was extracted via OCR from a nutrition label.
The text may be misaligned — nutrient names and their values may be on different lines.

Your job:
1. Match each nutrient name to its correct numeric value
2. Ignore % daily values, serving info, allergen text, and marketing text
3. For "PER 100g" labels, set basis to "per_100g"
4. For "<1" or "<1g" values, use 0.5 as the value
5. Fix OCR errors: "B" likely means "g", "lg" means "g", "ll" means "1"

Return ONLY this strict JSON, no explanation, no markdown:
{{
  "ingredients": [],
  "nutrients": [
    {{
      "name": "energy",
      "value": 589,
      "unit": "kcal",
      "basis": "per_100g"
    }},
    {{
      "name": "protein",
      "value": 15.2,
      "unit": "g",
      "basis": "per_100g"
    }}
  ]
}}

Nutrient names to look for (use these exact names):
energy, protein, carbohydrates, total_sugars, added_sugars, dietary_fiber, total_fat, saturated_fat, trans_fat, cholesterol, sodium

OCR TEXT:
{raw_text}
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1  # ✅ low temperature = more consistent structured output
    )

    output_text = response.choices[0].message.content.strip()
    output_text = re.sub(r"^```json|^```|```$", "", output_text, flags=re.MULTILINE).strip()

    try:
        return json.loads(output_text)
    except Exception as e:
        print("AI RAW OUTPUT:\n", output_text)
        raise Exception("Invalid JSON from AI")

# -----------------------------
# NORMALIZATION
# -----------------------------



def _safe_float(value):
    try:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        cleaned = re.sub(r"[^0-9.\-]", "", str(value))
        if not cleaned:
            return None
        return float(cleaned)
    except (ValueError, TypeError):
        return None



def _normalize_nutrients_per_100g(nutrients):
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
        "nutrition_per_100g": _normalize_nutrients_per_100g(nutrients),
    }

def _extract_ingredients(raw_text):
    if not raw_text:
        return []

    ingredient_block = ""
    for line in raw_text.splitlines():
        if "ingredient" in line.lower():
            ingredient_block = line
            break

    if not ingredient_block:
        return []

    after_colon = ingredient_block.split(":", 1)[-1]
    candidates = [part.strip() for part in re.split(r",|;", after_colon) if part.strip()]
    return candidates[:25]



def _extract_nutrients(raw_text):
    if not raw_text:
        return []

    nutrients = []
    nutrient_patterns = {
        "energy": r"(energy|kcal|calories)",
        "protein": r"(protein|proteins)",
        "carbohydrates": r"(carbohydrate|carbohydrates|carbs)",
        "fat": r"(fat|fats|total fat)",
        "sugars": r"(sugar|sugars)",
        "salt": r"(salt|sodium)",
        "fiber": r"(fiber|fibre)",
    }

    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

    for line in lines:
        lower_line = line.lower()

        detected_name = None
        for canonical, pattern in nutrient_patterns.items():
            if re.search(pattern, lower_line):
                detected_name = canonical
                break

        if not detected_name:
            continue

        value_match = re.search(r"(-?\d+(?:\.\d+)?)\s*(kcal|kj|g|mg|mcg|µg|ml)?", lower_line)
        if not value_match:
            continue

        value = _safe_float(value_match.group(1))
        unit = (value_match.group(2) or "g").lower()

        basis = "100g"
        basis_match = re.search(r"(?:per|/)\s*(\d+(?:\.\d+)?)\s*(g|ml)", lower_line)
        if basis_match:
            basis = f"{basis_match.group(1)}{basis_match.group(2)}"

        nutrients.append(
            {
                "name": detected_name,
                "value": value,
                "unit": unit,
                "basis": basis,
            }
        )

    deduped = {}
    for item in nutrients:
        deduped[item["name"]] = item

    return list(deduped.values())



def image_file_to_base64(file_obj):
    binary = file_obj.read()
    return base64.b64encode(binary).decode("utf-8")



def _ocr_space_read_text(image_base64, api_key):
    payload = parse.urlencode(
        {
            "apikey": api_key,
            "base64Image": f"data:image/jpeg;base64,{image_base64}",
            "language": "eng",
            "isOverlayRequired": "false",
            "OCREngine": "2",
            "scale": "true",
        }
    ).encode("utf-8")

    req = urllib_request.Request(
        OCR_SPACE_API_URL,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    try:
        with urllib_request.urlopen(req, timeout=45) as response:
            parsed = json.loads(response.read().decode("utf-8"))
    except (error.HTTPError, error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError("Unable to contact OCR.Space service.") from exc

    if parsed.get("IsErroredOnProcessing"):
        error_message = " ".join(parsed.get("ErrorMessage") or []) or "OCR processing failed."
        raise RuntimeError(error_message)

    parsed_results = parsed.get("ParsedResults") or []
    if not parsed_results:
        raise RuntimeError("OCR.Space returned no parsed results.")

    text = "\n".join(result.get("ParsedText", "") for result in parsed_results).strip()
    return text



def analyze_label_image(image_file):
    api_key = os.getenv("OCR_SPACE_API_KEY")
    print(api_key)
    if not api_key:
        raise ValueError("OCR_SPACE_API_KEY is not configured.")

    image_base64 = image_file_to_base64(image_file)
    raw_text = _ocr_space_read_text(image_base64=image_base64, api_key=api_key)

    try:
        ai_data = analyze_label_text(raw_text)
        ingredients = ai_data.get("ingredients", [])
        nutrients = ai_data.get("nutrients", [])
    except Exception as e:
        print(f"AI analysis failed, falling back to regex: {e}")
        ingredients = _extract_ingredients(raw_text)   # ✅ called with ()
        nutrients = _extract_nutrients(raw_text)       # ✅ called with ()

    # ✅ Make sure all values are JSON-serializable plain types
    return {
        "raw_text": str(raw_text),
        "ingredients": list(ingredients),
        "nutrients": list(nutrients),
        "nutrition_per_100g": dict(_normalize_nutrients_per_100g(nutrients)),
    }
# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    result = process_food_label("C:/PROJECT/Intelligent-QAD-System/nutrition_en.8.full.jpg")
    print(json.dumps(result, indent=2))

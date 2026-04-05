import base64
import json
import os
import re
from urllib import error, parse, request as urllib_request

OCR_SPACE_API_URL = "https://api.ocr.space/parse/image"



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
    for item in nutrients or []:
        name = str(item.get("name", "")).strip()
        value = _safe_float(item.get("value"))
        unit = str(item.get("unit", "")).strip().lower() or "g"
        basis = str(item.get("basis", "100g")).strip().lower()

        if not name:
            continue

        if value is None:
            normalized[name] = {
                "value_per_100g": None,
                "unit": unit,
                "source_basis": basis,
            }
            continue

        if basis == "100g":
            value_per_100g = value
        elif basis.endswith("g"):
            basis_num = _safe_float(basis.replace("g", ""))
            value_per_100g = (value / basis_num) * 100 if basis_num and basis_num > 0 else value
        elif basis.endswith("ml"):
            basis_num = _safe_float(basis.replace("ml", ""))
            value_per_100g = (value / basis_num) * 100 if basis_num and basis_num > 0 else value
        else:
            value_per_100g = value

        normalized[name] = {
            "value_per_100g": round(value_per_100g, 3) if value_per_100g is not None else None,
            "unit": unit,
            "source_basis": basis,
        }

    return normalized



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
    if not api_key:
        raise ValueError("OCR_SPACE_API_KEY is not configured.")

    image_base64 = image_file_to_base64(image_file)
    raw_text = _ocr_space_read_text(image_base64=image_base64, api_key=api_key)

    nutrients = _extract_nutrients(raw_text)

    return {
        "raw_text": raw_text,
        "ingredients": _extract_ingredients(raw_text),
        "nutrients": nutrients,
        "nutrition_per_100g": _normalize_nutrients_per_100g(nutrients),
    }

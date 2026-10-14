"""Opt-in browser diary. No server database, user ID, or photo persistence."""
import base64
import math
import uuid
from pathlib import Path

import streamlit as st
import streamlit.components.v2 as components
from report_export import build_meal_pdf

NUTRIENTS = ("Calories", "Protein", "Carbs", "Fat")
ROOT = Path(__file__).parent



def clean_snapshot(payload):
    """Allowlist meal fields, including for untrusted browser PDF requests."""
    if not isinstance(payload, dict) or payload.get("demo") or not isinstance(payload.get("foods"), list):
        raise ValueError("Please review a real meal first.")
    if not 1 <= len(payload["foods"]) <= 15:
        raise ValueError("Invalid food list.")
    def text(value, limit=200):
        return str(value or "")[:limit]
    def number(value, maximum=10000000):
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not 0 <= value <= maximum:
            raise ValueError("Invalid nutrition value.")
        return value
    def nutrients(values):
        if not isinstance(values, dict):
            raise ValueError("Invalid nutrients.")
        return {name: number(values.get(name)) for name in NUTRIENTS}
    foods = []
    for food in payload["foods"]:
        if not isinstance(food, dict):
            raise ValueError("Invalid food.")
        foods.append({"name": text(food.get("name")), "grams": number(food.get("grams"), 5000),
                      "weighed": food.get("weighed") is True,
                      "portion_low_g": number(food.get("portion_low_g"), 25000000),
                      "portion_high_g": number(food.get("portion_high_g"), 25000000),
                      "nutrition_match": text(food.get("nutrition_match"), 300),
                      "usda_fdc_id": number(food.get("usda_fdc_id"), 100000000),
                      "nutrients": nutrients(food.get("nutrients"))})
    excluded = payload.get("excluded_foods", [])
    if not isinstance(excluded, list):
        raise ValueError("Invalid excluded foods.")
    bounds = payload.get("calorie_range")
    bounds = [number(v) for v in bounds] if isinstance(bounds, list) and len(bounds) == 2 else None
    return {"app": "RR CalTracker", "demo": False, "estimated": True,
            "partial": bool(excluded) or payload.get("partial") is True,
            "generated_at": text(payload.get("generated_at"), 80),
            "foods": foods, "totals": nutrients(payload.get("totals")),
            "excluded_foods": [text(v) for v in excluded[:15]], "calorie_range": bounds,
            "assumptions": [], "method": "Reviewed photo estimate with USDA nutrition data."}


def render(mode="history", payload=None, saved=None):
    diary = components.component(
        "rr_browser_diary_v1", html='<div id="diary-root"></div>',
        js=(ROOT / "browser_history.js").read_text(encoding="utf-8"),
        css=(ROOT / "browser_history.css").read_text(encoding="utf-8"),
    )
    data = {"mode": mode}
    if payload and not payload.get("demo"):
        if "browser_meal_token" not in saved:
            saved["browser_meal_token"] = uuid.uuid4().hex
        data.update(snapshot=clean_snapshot(payload), token=saved["browser_meal_token"])
    # Only an explicit PDF request crosses from local history back to Python.
    response = st.session_state.pop("browser_pdf_response", None)
    if response:
        data["pdf"] = response
    result = diary(key="browser-diary", data=data, on_export_change=lambda: None)
    request = result.export
    if request and isinstance(request, dict):
        response = {"requestId": str(request.get("requestId", ""))[:80]}
        try:
            snapshot = clean_snapshot(request.get("snapshot"))
            response["base64"] = base64.b64encode(build_meal_pdf(snapshot)).decode("ascii")
        except (ValueError, TypeError, AttributeError):
            response["error"] = "That saved meal could not be exported. Try another meal."
        st.session_state["browser_pdf_response"] = response
        st.rerun()

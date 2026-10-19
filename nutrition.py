"""USDA nutrient identities, units, portion scaling, and honest coverage totals.

IDs/units verified against USDA FoodData Central nutrient.csv. Food search and
food-detail amounts are per 100 g. Different vitamin forms are never added.
"""
import math

_ROWS = [
    (1008, "Calories", "Calories", "kcal", "Macros"),
    (1003, "Protein", "Protein", "g", "Macros"),
    (1005, "Carbs", "Carbs", "g", "Macros"),
    (1004, "Fat", "Fat", "g", "Macros"),
    (1079, "Fiber", "Fiber", "g", "Macros"),
    (1106, "Vitamin A", "Vitamin A (RAE)", "mcg", "Vitamins"),
    (1162, "Vitamin C", "Vitamin C", "mg", "Vitamins"),
    (1114, "Vitamin D", "Vitamin D (D2 + D3)", "mcg", "Vitamins"),
    (1109, "Vitamin E", "Vitamin E (alpha-tocopherol)", "mg", "Vitamins"),
    (1185, "Vitamin K", "Vitamin K (phylloquinone)", "mcg", "Vitamins"),
    (1165, "Vitamin B1", "Vitamin B1 (thiamin)", "mg", "Vitamins"),
    (1166, "Vitamin B2", "Vitamin B2 (riboflavin)", "mg", "Vitamins"),
    (1167, "Vitamin B3", "Vitamin B3 (niacin)", "mg", "Vitamins"),
    (1170, "Vitamin B5", "Vitamin B5 (pantothenic acid)", "mg", "Vitamins"),
    (1175, "Vitamin B6", "Vitamin B6", "mg", "Vitamins"),
    (1176, "Vitamin B7", "Vitamin B7 (biotin)", "mcg", "Vitamins"),
    (1177, "Vitamin B9", "Vitamin B9 (total folate)", "mcg", "Vitamins"),
    (1178, "Vitamin B12", "Vitamin B12", "mcg", "Vitamins"),
    (1087, "Calcium", "Calcium", "mg", "Minerals"),
    (1089, "Iron", "Iron", "mg", "Minerals"),
    (1090, "Magnesium", "Magnesium", "mg", "Minerals"),
    (1091, "Phosphorus", "Phosphorus", "mg", "Minerals"),
    (1092, "Potassium", "Potassium", "mg", "Minerals"),
    (1093, "Sodium", "Sodium", "mg", "Minerals"),
    (1095, "Zinc", "Zinc", "mg", "Minerals"),
    (1098, "Copper", "Copper", "mg", "Minerals"),
    (1101, "Manganese", "Manganese", "mg", "Minerals"),
    (1103, "Selenium", "Selenium", "mcg", "Minerals"),
    (1100, "Iodine", "Iodine", "mcg", "Minerals"),
    (1180, "Choline", "Choline", "mg", "Other"),
]
CATALOG = [dict(id=i, key=k, label=l, unit=u, group=g) for i, k, l, u, g in _ROWS]
NAMES = tuple(n[1] for n in _ROWS)
BY_KEY = {n["key"]: n for n in CATALOG}
BY_ID = {n["id"]: n for n in CATALOG}


def valid_amount(value):
    return (not isinstance(value, bool) and isinstance(value, (int, float))
            and math.isfinite(value) and 0 <= value <= 10_000_000)


def nutrient_values(food):
    result = dict.fromkeys(NAMES)
    units = {"G": "g", "MG": "mg", "UG": "mcg", "MCG": "mcg", "KCAL": "kcal"}
    factors = {"g": 1, "mg": .001, "mcg": .000001}
    for row in food.get("foodNutrients", []):
        if not isinstance(row, dict):
            continue
        nested = row.get("nutrient", {})
        if not isinstance(nested, dict):
            nested = {}
        spec = BY_ID.get(row.get("nutrientId", nested.get("id")))
        value = row.get("value", row.get("amount"))
        raw_unit = str(row.get("unitName", nested.get("unitName", ""))).upper().replace("Μ", "U").replace("µ", "U")
        unit = units.get(raw_unit)
        if not spec or not valid_amount(value) or not unit:
            continue
        target = spec["unit"]
        if unit == target:
            result[spec["key"]] = float(value)
        elif unit in factors and target in factors:
            converted = value * factors[unit] / factors[target]
            if valid_amount(converted):
                result[spec["key"]] = converted
    return result


def scale_nutrients(food, grams):
    if not valid_amount(grams) or grams > 5000:
        raise ValueError("Invalid portion weight.")
    return {k: 0.0 if grams == 0 else None if v is None else v * grams / 100
            for k, v in nutrient_values(food).items()}


def calculate_totals(items):
    """Preserve strict totals for exports/macros; coverage views show known sums."""
    scaled = [scale_nutrients(food, grams) for grams, food in items]
    return {k: None if any(row[k] is None for row in scaled)
            else sum(row[k] for row in scaled) for k in NAMES}


def summarize_foods(foods, excluded_foods=(), partial=False):
    """Sum known amounts and count missing foods, including excluded matches."""
    rows = [f.get("nutrients", {}) for f in foods if f.get("grams") != 0]
    rows += [{} for _ in excluded_foods]
    if partial and not excluded_foods:
        rows.append({})
    summary = {}
    for key in NAMES:
        known = [r.get(key) for r in rows if isinstance(r, dict) and valid_amount(r.get(key))]
        summary[key] = {"value": sum(known) if known else None,
                        "known": len(known), "total": len(rows)}
    return summary


def format_amount(value, unit):
    if not valid_amount(value):
        return "Not available"
    if 0 < value < .01:
        return f"<0.01 {unit}"
    number = f"{value:,.0f}" if unit == "kcal" else f"{value:,.2f}".rstrip("0").rstrip(".")
    return f"{number} {unit}"


def coverage_label(entry):
    known, total = entry["known"], entry["total"]
    if not total:
        return "No foods logged"
    if not known:
        return "Not reported"
    return f"{'Partial · ' if known < total else ''}{known}/{total} foods"

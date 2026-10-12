"""Persistent, local meal snapshots. Uses only Python's standard library."""
import json
import math
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

CATEGORIES = ("Breakfast", "Lunch", "Dinner", "Snack")
NUTRIENTS = ("Calories", "Protein", "Carbs", "Fat")
DEFAULT_DB = Path(__file__).with_name("data") / "meals.sqlite3"


@contextmanager
def connection(db_path=None):
    path = Path(db_path) if db_path is not None else DEFAULT_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(path), timeout=10)
    db.row_factory = sqlite3.Row
    try:
        db.execute("""CREATE TABLE IF NOT EXISTS meals (
            id INTEGER PRIMARY KEY,
            log_token TEXT NOT NULL UNIQUE,
            meal_date TEXT NOT NULL,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            snapshot TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL)""")
        db.execute("CREATE INDEX IF NOT EXISTS meals_date ON meals(meal_date)")
        with db:
            yield db
    finally:
        db.close()


def valid_date(value):
    return date.fromisoformat(str(value)).isoformat()


def snapshot_for_storage(payload):
    """Store reviewed nutrition only: no photos, provider keys, or requests."""
    if payload.get("demo"):
        raise ValueError("Sample meals cannot be saved in your real meal history.")
    if not payload.get("foods"):
        raise ValueError("Review at least one food before saving.")
    for name in NUTRIENTS:
        value = payload.get("totals", {}).get(name)
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                                  or not math.isfinite(value) or value < 0):
            raise ValueError("Nutrition totals must be nonnegative numbers or unavailable.")
    keys = ("app", "estimated", "partial", "generated_at", "calorie_range", "foods",
            "excluded_foods", "totals", "assumptions", "method")
    clean = {key: payload[key] for key in keys if key in payload}
    clean["demo"] = False
    food_keys = ("name", "grams", "weighed", "portion_low_g", "portion_high_g",
                 "portion_notes", "nutrients", "usda_fdc_id", "nutrition_match")
    clean["foods"] = [{key: food[key] for key in food_keys if key in food}
                      for food in payload["foods"]]
    return json.dumps(clean, ensure_ascii=False, allow_nan=False)


def save_meal(log_token, meal_date, category, title, payload, db_path=None):
    meal_date = valid_date(meal_date)
    if category not in CATEGORIES:
        raise ValueError("Choose breakfast, lunch, dinner, or snack.")
    if not isinstance(log_token, str) or not 1 <= len(log_token) <= 100:
        raise ValueError("Invalid meal identifier.")
    title = str(title).strip()[:120] or category
    snapshot = snapshot_for_storage(payload)
    now = datetime.now(timezone.utc).isoformat()
    with connection(db_path) as db:
        # Repeated saves of the same reviewed meal update it instead of duplicating it.
        db.execute("""INSERT INTO meals
            (log_token, meal_date, category, title, snapshot, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(log_token) DO UPDATE SET
            meal_date=excluded.meal_date, category=excluded.category,
            title=excluded.title, snapshot=excluded.snapshot, updated_at=excluded.updated_at""",
            (log_token, meal_date, category, title, snapshot, now, now))
        return db.execute("SELECT id FROM meals WHERE log_token=?", (log_token,)).fetchone()[0]


def list_meals(start, end, db_path=None):
    start, end = valid_date(start), valid_date(end)
    if start > end:
        raise ValueError("The start date must be before the end date.")
    with connection(db_path) as db:
        rows = db.execute("SELECT * FROM meals WHERE meal_date BETWEEN ? AND ? ORDER BY meal_date, id",
                          (start, end)).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["snapshot"] = json.loads(item["snapshot"])
        result.append(item)
    return result


def change_meal_details(meal_id, meal_date, category, title, db_path=None):
    if category not in CATEGORIES:
        raise ValueError("Invalid meal category.")
    with connection(db_path) as db:
        db.execute("UPDATE meals SET meal_date=?, category=?, title=?, updated_at=? WHERE id=?",
                   (valid_date(meal_date), category, str(title).strip()[:120] or category,
                    datetime.now(timezone.utc).isoformat(), meal_id))


def delete_meal(meal_id, db_path=None):
    with connection(db_path) as db:
        db.execute("DELETE FROM meals WHERE id=?", (meal_id,))


def summarize(meals):
    """Unknown nutrients stay unknown. No logged meals does not mean no food eaten."""
    result = {"Meals": len(meals), "Partial": any(m["snapshot"].get("partial", False) for m in meals)}
    for name in NUTRIENTS:
        values = [m["snapshot"].get("totals", {}).get(name) for m in meals]
        result[name] = None if not values or any(v is None for v in values) else sum(values)
    return result


def daily_summaries(meals, start, end):
    current, last = date.fromisoformat(valid_date(start)), date.fromisoformat(valid_date(end))
    grouped = {}
    for meal in meals:
        grouped.setdefault(meal["meal_date"], []).append(meal)
    rows = []
    while current <= last:
        rows.append({"Date": current.isoformat(), **summarize(grouped.get(current.isoformat(), []))})
        current += timedelta(days=1)
    return rows

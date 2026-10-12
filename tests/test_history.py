"""Persistent-history tests using temporary databases and mocked analysis only."""
import io
import json
import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
import meal_store as store
from PIL import Image
from streamlit.testing.v1 import AppTest


def payload(calories=195, partial=False):
    return {"demo": False, "estimated": True, "partial": partial,
            "foods": [{"name": "Rice", "grams": 150, "nutrients": {"Calories": calories}}],
            "totals": {"Calories": calories, "Protein": 4.05, "Carbs": 42, "Fat": .45},
            "assumptions": ["Estimated portion."], "excluded_foods": ["Sauce"] if partial else []}


class StorageChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "nested" / "meals.sqlite3"

    def tearDown(self):
        self.temp.cleanup()

    def save(self, token="a", day="2026-10-12", category="Lunch", data=None):
        return store.save_meal(token, day, category, "Rice lunch", data or payload(), self.db)

    def test_restart_and_duplicate_save_and_new_serving(self):
        first = self.save()
        again = self.save(data=payload(260))
        self.assertEqual(first, again)
        self.save("b")
        # Each call opens/closes a fresh connection, equivalent to a restart.
        meals = store.list_meals("2026-10-12", "2026-10-12", self.db)
        self.assertEqual(len(meals), 2)
        self.assertEqual(store.summarize(meals)["Calories"], 455)

    def test_calendar_range_categories_and_unlogged_days(self):
        for token, day, category in [("a", "2026-10-01", "Breakfast"),
                                     ("b", "2026-10-12", "Snack"), ("c", "2026-10-12", "Snack"),
                                     ("d", "2026-10-12", "Dinner")]:
            self.save(token, day, category)
        self.assertEqual(len(store.list_meals("2026-10-06", "2026-10-12", self.db)), 3)
        meals = store.list_meals("2026-09-29", "2026-10-12", self.db)
        rows = store.daily_summaries(meals, "2026-09-29", "2026-10-12")
        self.assertEqual(len(rows), 14)
        self.assertEqual(rows[-1]["Calories"], 585)
        self.assertEqual(rows[0]["Meals"], 0)
        self.assertIsNone(rows[0]["Calories"])

    def test_missing_and_partial_values_stay_distinguishable(self):
        self.save(data=payload(None, True))
        result = store.summarize(store.list_meals("2026-10-12", "2026-10-12", self.db))
        self.assertIsNone(result["Calories"])
        self.assertTrue(result["Partial"])

    def test_edit_date_category_title_and_delete(self):
        ident = self.save()
        store.change_meal_details(ident, "2026-10-11", "Dinner", "New name", self.db)
        self.assertEqual(store.list_meals("2026-10-12", "2026-10-12", self.db), [])
        entry = store.list_meals("2026-10-11", "2026-10-11", self.db)[0]
        self.assertEqual((entry["category"], entry["title"]), ("Dinner", "New name"))
        store.delete_meal(ident, self.db)
        self.assertEqual(store.list_meals("2026-10-11", "2026-10-11", self.db), [])

    def test_demo_invalid_date_category_and_nonfinite_rejected(self):
        for data in [{**payload(), "demo": True}, payload(float("nan")), payload(-1)]:
            with self.assertRaises(ValueError):
                self.save(data=data)
        for day, category in [("2026-02-30", "Lunch"), ("2026-10-12", "Bad")]:
            with self.assertRaises(ValueError):
                self.save(day=day, category=category)

    def test_unrelated_payload_fields_are_not_persisted(self):
        self.save(data={**payload(), "api_key": "not-to-save", "image": "not-to-save"})
        item = store.list_meals("2026-10-12", "2026-10-12", self.db)[0]
        self.assertNotIn("not-to-save", json.dumps(item))


class HistoryUI(unittest.TestCase):
    def test_real_review_save_history_restart_pdf_and_delete(self):
        raw = io.BytesIO()
        Image.new("RGB", (32, 32), "white").save(raw, format="JPEG")
        def upload(label, **kwargs):
            return None if label.startswith("Side") else io.BytesIO(raw.getvalue())
        identified = app.Meal(foods=[app.Food(name="Rice", search_query="rice", grams=150)], assumptions=[])
        nutrients = [{"nutrientId": n, "unitName": u, "value": v} for n, u, v in
                     [(1008, "KCAL", 130), (1003, "G", 2.7), (1005, "G", 28), (1004, "G", .3)]]
        matches = [{"fdcId": 1, "description": "Cooked rice", "foodNutrients": nutrients}]
        gemini_response = {"candidates": [{"finishReason": "STOP", "content": {"parts": [
            {"text": identified.model_dump_json()}]}}]}
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(store, "DEFAULT_DB", Path(tmp) / "meals.sqlite3"), \
             patch.dict(os.environ, {"GEMINI_API_KEY": "fake", "USDA_API_KEY": "fake"}), \
             patch("meal_history.local_today", return_value=date(2026, 10, 12)), \
             patch.object(app.st, "file_uploader", side_effect=upload), \
             patch.object(app.urllib.request, "urlopen", side_effect=[
                 io.BytesIO(json.dumps(gemini_response).encode()),
                 io.BytesIO(json.dumps({"foods": matches}).encode())]):
            app.search_foods.clear()
            page = AppTest.from_file(str(Path(app.__file__))).run()
            next(b for b in page.button if b.label == "Analyze meal").click().run()
            next(n for n in page.number_input if n.label == "Estimated portion (grams)").set_value(200).run()
            next(d for d in page.date_input if d.label == "Meal date").set_value(date(2026, 10, 11))
            next(s for s in page.selectbox if s.label == "Meal category").set_value("Snack")
            next(b for b in page.button if b.label == "Save meal to history").click().run()
            self.assertEqual(len(page.exception), 0)
            next(b for b in page.button if b.label == "Save meal to history").click().run()
            entries = store.list_meals("2026-10-11", "2026-10-11")
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["snapshot"]["totals"]["Calories"], 260)
            self.assertEqual(entries[0]["category"], "Snack")
            # A fresh page has no analysis in memory but can read persisted history.
            fresh = AppTest.from_file(str(Path(app.__file__))).run()
            next(r for r in fresh.radio if r.label == "Open").set_value("Meal history").run()
            next(d for d in fresh.date_input if d.label.startswith("Calendar")).set_value(date(2026, 10, 11)).run()
            self.assertEqual(len(fresh.exception), 0)
            self.assertEqual(fresh.metric[0].value, "260 kcal")
            next(r for r in fresh.radio if r.label.startswith("Review period")).set_value("14 days").run()
            self.assertEqual(len(fresh.exception), 0)
            self.assertEqual(len(fresh.dataframe[-1].value), 14)
            next(c for c in fresh.checkbox if c.label.startswith("Confirm deletion")).check().run()
            next(b for b in fresh.button if b.label == "Delete meal").click().run()
            self.assertEqual(len(fresh.exception), 0)
            self.assertEqual(store.list_meals("2026-10-11", "2026-10-11"), [])


if __name__ == "__main__":
    unittest.main()

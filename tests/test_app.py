"""Offline checks; no real credentials, photos, or API calls required."""
import base64
import io
import json
import os
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
from PIL import Image
from streamlit.testing.v1 import AppTest


class AppChecks(unittest.TestCase):
    def setUp(self):
        self.portion_mode = patch.dict(os.environ, {"RR_PORTION_MODE": "visual"})
        self.portion_mode.start()
        self.addCleanup(self.portion_mode.stop)

    def response(self, grams=150, finish="STOP"):
        meal = {"foods": [{"name": "Cooked rice", "search_query": "rice cooked", "grams": grams,
                           "grams_low": 100, "grams_high": 200, "portion_notes": "Rice mound; depth uncertain."}],
                "assumptions": ["Portion estimated from photo."]}
        return io.BytesIO(json.dumps({"candidates": [{"finishReason": finish,
            "content": {"parts": [{"text": json.dumps(meal)}]}}]}).encode())

    def test_image_request_and_food_response(self):
        with patch.dict(os.environ, {"GEMINI_MODEL": "gemini-3.5-flash-lite"}), \
             patch.object(app.urllib.request, "urlopen", return_value=self.response()) as send:
            result = app.identify_foods(b"sample-image-bytes", "rice", "fake-test-key")
        self.assertEqual(result.foods[0].grams, 150)
        request = send.call_args.args[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("X-goog-api-key"), "fake-test-key")
        self.assertNotIn("fake-test-key", request.full_url)
        body = json.loads(request.data)
        self.assertEqual(body["generationConfig"]["responseMimeType"], "application/json")
        self.assertIn("rice", body["contents"][0]["parts"][0]["text"])
        image = next(p["inlineData"] for p in body["contents"][0]["parts"] if "inlineData" in p)
        self.assertEqual(base64.b64decode(image["data"]), b"sample-image-bytes")
        self.assertEqual(image["mimeType"], "image/jpeg")

    def test_invalid_portion_is_rejected(self):
        with patch.object(app.urllib.request, "urlopen", return_value=self.response(grams=-10)):
            with self.assertRaisesRegex(ValueError, "valid food list"):
                app.identify_foods(b"image", "", "fake-test-key")

    def test_incomplete_response_is_rejected(self):
        with patch.object(app.urllib.request, "urlopen", return_value=self.response(finish="MAX_TOKENS")):
            with self.assertRaises(ValueError):
                app.identify_foods(b"image", "", "fake-test-key")

    def test_quota_error_is_safe_and_not_retried(self):
        failure = urllib.error.HTTPError("https://example.invalid", 429, "fake-test-key", {}, io.BytesIO())
        with patch.object(app.urllib.request, "urlopen", side_effect=failure) as send:
            with self.assertRaisesRegex(ValueError, "quota limit") as caught:
                app.identify_foods(b"image", "", "fake-test-key")
        self.assertNotIn("fake-test-key", str(caught.exception))
        self.assertEqual(send.call_count, 1)

    def test_scaling_and_unknown_nutrients(self):
        food = {"foodNutrients": [
            {"nutrientId": 1008, "unitName": "KCAL", "value": 130},
            {"nutrientId": 1003, "unitName": "G", "value": 2.7},
        ]}
        totals = app.calculate_totals([(150, food)])
        self.assertEqual(totals["Calories"], 195)
        self.assertAlmostEqual(totals["Protein"], 4.05)
        self.assertIsNone(totals["Fiber"])

    def test_startup_without_keys(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "", "USDA_API_KEY": ""}):
            page = AppTest.from_file(str(Path(app.__file__))).run()
        self.assertEqual(len(page.exception), 0)
        self.assertEqual(page.title[0].value, "RR CalTracker")
        self.assertIn("Analysis is not set up yet", page.info[0].value)

    def test_usda_search_uses_array_and_header(self):
        app.search_foods.clear()
        response = io.BytesIO(json.dumps({"foods": [{"fdcId": 1, "description": "Cooked rice"}]}).encode())
        with patch.object(app.urllib.request, "urlopen", return_value=response) as send:
            foods = app.search_foods("rice cooked", "fake-usda-key")
        self.assertEqual(foods[0]["fdcId"], 1)
        request = send.call_args.args[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("X-api-key"), "fake-usda-key")
        self.assertNotIn("fake-usda-key", request.full_url)
        self.assertEqual(json.loads(request.data)["dataType"], ["Survey (FNDDS)", "SR Legacy"])

    def test_usda_key_error_does_not_expose_credentials(self):
        app.search_foods.clear()
        response = io.BytesIO(json.dumps({"error": {"code": "API_KEY_INVALID", "message": "fake-usda-key"}}).encode())
        failure = urllib.error.HTTPError("https://example.invalid", 403, "error", {}, response)
        with patch.object(app.urllib.request, "urlopen", side_effect=failure):
            with self.assertRaisesRegex(ValueError, "USDA rejected the key") as caught:
                app.search_foods("rice cooked", "fake-usda-key")
        self.assertNotIn("fake-usda-key", str(caught.exception))

    def test_multiple_views_are_sent_together_without_counting_extra_servings(self):
        with patch.object(app.urllib.request, "urlopen", return_value=self.response()) as send:
            app.identify_foods([b"top-photo", b"side-photo", b"other-angle"], "same plate", "fake-test-key")
        body = json.loads(send.call_args.args[0].data)
        parts = body["contents"][0]["parts"]
        images = [base64.b64decode(p["inlineData"]["data"]) for p in parts if "inlineData" in p]
        self.assertEqual(images, [b"top-photo", b"side-photo", b"other-angle"])
        self.assertIn("not an additional serving", " ".join(p.get("text", "") for p in parts))
        self.assertIn("SAME unchanged meal", body["systemInstruction"]["parts"][0]["text"])
        self.assertIn("do not invent", body["systemInstruction"]["parts"][0]["text"].lower())

    def test_inconsistent_or_nonfinite_portions_are_rejected(self):
        for extra in [{"grams_low": 200, "grams_high": 300},
                      {"grams_low": 100}, {"grams": float("nan")}]:
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                app.Food.model_validate({"name": "Rice", "search_query": "rice cooked", "grams": 150, **extra})

    def test_weighed_portions_override_photo_range(self):
        food = app.Food(name="Rice", search_query="rice cooked", grams=150, grams_low=100, grams_high=200)
        self.assertEqual(app.portion_bounds(food, 300), (200, 400))
        self.assertEqual(app.portion_bounds(food, 300, weighed=True), (300, 300))
        self.assertEqual(app.portion_bounds(food, 0), (0, 0))

    def test_all_analysis_inputs_invalidate_saved_result(self):
        original = app.analysis_signature([b"top", b"side", b"third"], "rice")
        for images, description in [([b"other", b"side", b"third"], "rice"),
                                    ([b"top", b"side", b"third"], "chicken"),
                                    ([b"top", b"other", b"third"], "rice"),
                                    ([b"top", b"side"], "rice"),
                                    ([b"side", b"top", b"third"], "rice")]:
            self.assertNotEqual(original, app.analysis_signature(images, description))

    def test_poc_upload_analyze_review_and_recalculate(self):
        """Exercise the actual Streamlit flow with a generated image and mocked APIs."""
        raw = io.BytesIO()
        Image.new("RGB", (32, 32), "white").save(raw, format="JPEG")
        def upload(label, **kwargs):
            return [io.BytesIO(raw.getvalue())]
        nutrients = [{"nutrientId": n, "unitName": u, "value": v} for n, u, v in
                     [(1008, "KCAL", 130), (1003, "G", 2.7), (1005, "G", 28), (1004, "G", 0.3), (1079, "G", 0.4)]]
        usda = {"foods": [{"fdcId": 1, "description": "Cooked rice", "foodNutrients": nutrients}]}
        app.search_foods.clear()
        with patch.dict(os.environ, {"GEMINI_API_KEY": "fake-poc-key", "USDA_API_KEY": "fake-poc-usda"}), \
             patch.object(app.st, "file_uploader", side_effect=upload), \
             patch.object(app.urllib.request, "urlopen", side_effect=[self.response(), io.BytesIO(json.dumps(usda).encode())]) as send:
            page = AppTest.from_file(str(Path(app.__file__))).run()
            page.button[0].click().run()
            self.assertEqual(len(page.exception), 0)
            self.assertEqual([m.label for m in page.metric], ["Calories", "Protein", "Carbs", "Fat"])
            self.assertEqual(page.metric[0].value, "195 kcal")
            self.assertTrue(any("130–260 kcal" in i.value for i in page.info))
            next(n for n in page.number_input if n.label == "Portion weight (grams)").set_value(200).run()
            self.assertEqual(len(page.exception), 0)
            self.assertEqual(page.metric[0].value, "260 kcal")
            self.assertTrue(any("173–347 kcal" in i.value for i in page.info))
            self.assertEqual(send.call_count, 2)

    def test_failed_nutrition_lookup_keeps_foods_for_retry(self):
        raw = io.BytesIO()
        Image.new("RGB", (32, 32), "white").save(raw, format="JPEG")
        def upload(label, **kwargs):
            return [io.BytesIO(raw.getvalue())]
        app.search_foods.clear()
        failure = urllib.error.HTTPError("https://example.invalid", 403, "error", {}, io.BytesIO())
        with patch.dict(os.environ, {"GEMINI_API_KEY": "fake-poc-key", "USDA_API_KEY": "fake-retry-usda"}), \
             patch.object(app.st, "file_uploader", side_effect=upload), \
             patch.object(app.urllib.request, "urlopen", side_effect=[self.response(), failure]) as send:
            page = AppTest.from_file(str(Path(app.__file__))).run()
            page.button[0].click().run()
            self.assertEqual(len(page.exception), 0)
            self.assertEqual(page.session_state["meal_result"]["meal"].foods[0].name, "Cooked rice")
            self.assertIn("Retry missing nutrition lookups", [b.label for b in page.button])
            self.assertEqual(send.call_count, 2)

    def test_sample_meal_is_interactive_without_provider_calls(self):
        """The sample can be edited and closed without credentials or API usage."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "", "USDA_API_KEY": ""}), \
             patch.object(app.urllib.request, "urlopen") as send:
            page = AppTest.from_file(str(Path(app.__file__))).run()
            next(b for b in page.button if b.label == "Try a sample meal").click().run()
            self.assertEqual(len(page.exception), 0)
            self.assertTrue(page.session_state["meal_result"]["demo"])
            self.assertEqual(page.metric[0].value, "461 kcal")
            page.number_input[0].set_value(200).run()
            self.assertEqual(page.metric[0].value, "526 kcal")
            next(b for b in page.button if b.label == "Close sample meal").click().run()
            self.assertNotIn("meal_result", page.session_state)
            next(b for b in page.button if b.label == "Try a sample meal").click().run()
            self.assertEqual(page.metric[0].value, "461 kcal")
            send.assert_not_called()

    def test_pdf_download_uses_current_reviewed_portions(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "", "USDA_API_KEY": ""}), \
             patch("report_export.build_meal_pdf", wraps=app.build_meal_pdf) as build, \
             patch.object(app.st, "download_button", wraps=app.st.download_button) as download:
            page = AppTest.from_file(str(Path(app.__file__))).run()
            next(b for b in page.button if b.label == "Try a sample meal").click().run()
            page.number_input[0].set_value(200).run()
            self.assertEqual(len(page.exception), 0)
            payload = build.call_args.args[0]
            self.assertEqual(payload["totals"]["Calories"], 526)
            self.assertEqual(payload["foods"][0]["grams"], 200)
            self.assertEqual(payload["foods"][0]["nutrients"]["Calories"], 260)
            self.assertTrue(payload["demo"])
            self.assertEqual(download.call_args.kwargs["mime"], "application/pdf")
            self.assertTrue(download.call_args.kwargs["data"].startswith(b"%PDF-"))
            self.assertEqual(download.call_args.kwargs["file_name"], "RR_CalTracker_sample.pdf")


if __name__ == "__main__":
    unittest.main()

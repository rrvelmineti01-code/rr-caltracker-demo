"""USDA recovery checks. All network responses are simulated."""
import io
import json
import os
from pathlib import Path
import socket
import ssl
import sys
import unittest
import urllib.error
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
from PIL import Image
from streamlit.testing.v1 import AppTest


class USDARecoveryChecks(unittest.TestCase):
    def setUp(self):
        app.search_foods.clear()

    def response(self, name="Rice cooked", calories=130):
        return io.BytesIO(json.dumps({"foods": [{"fdcId": 1, "description": name,
            "foodNutrients": [{"nutrientId": 1008, "unitName": "KCAL", "value": calories}]}]}).encode())

    def http_error(self, code, retry_after=None):
        headers = {"Retry-After": retry_after} if retry_after is not None else {}
        return urllib.error.HTTPError("https://example.invalid", code, "fake-private-key", headers,
                                       io.BytesIO(b'{"error":{"message":"fake-private-key"}}'))

    def test_timeout_recovers_and_success_is_cached(self):
        with patch.object(app.urllib.request, "urlopen", side_effect=[
                TimeoutError("fake-private-key"), self.response()]) as send, \
             patch.object(app.time, "sleep") as pause:
            self.assertEqual(app.search_foods("rice cooked", "fake-key")[0]["fdcId"], 1)
            self.assertEqual(app.search_foods("rice cooked", "fake-key")[0]["fdcId"], 1)
        self.assertEqual(send.call_count, 2)
        pause.assert_called_once_with(0.5)
        self.assertTrue(all(c.kwargs["timeout"] == 12 for c in send.call_args_list))

    def test_temporary_dns_failure_recovers(self):
        failure = urllib.error.URLError(socket.gaierror(socket.EAI_AGAIN, "fake-private-key"))
        with patch.object(app.urllib.request, "urlopen", side_effect=[failure, self.response()]) as send, \
             patch.object(app.time, "sleep"):
            self.assertEqual(len(app.search_foods("rice", "fake-key")), 1)
        self.assertEqual(send.call_count, 2)

    def test_three_connection_attempts_then_one_batch_warning(self):
        foods = [app.Food(name=f"Food {i}", search_query=f"food {i}", grams=100) for i in range(5)]
        failure = urllib.error.URLError(ConnectionResetError("fake-private-key"))
        with patch.object(app.urllib.request, "urlopen", side_effect=failure) as send, \
             patch.object(app.time, "sleep") as pause:
            candidates, errors = app.lookup_nutrition(foods, "fake-key")
        self.assertEqual(send.call_count, 3)  # Not three attempts for each of five foods.
        self.assertEqual(pause.call_count, 2)
        self.assertEqual(candidates, [[], [], [], [], []])
        self.assertEqual(len(errors), 1)
        self.assertIn("USDA code: connection", errors[0])
        self.assertNotIn("fake-private-key", errors[0])

    def test_service_503_recovers_and_respects_short_retry_after(self):
        with patch.object(app.urllib.request, "urlopen", side_effect=[self.http_error(503, "2"), self.response()]) as send, \
             patch.object(app.time, "sleep") as pause:
            self.assertEqual(len(app.search_foods("rice", "fake-key")), 1)
        self.assertEqual(send.call_count, 2)
        pause.assert_called_once_with(2.0)

    def test_long_retry_after_is_not_retried_early(self):
        with patch.object(app.urllib.request, "urlopen", side_effect=self.http_error(503, "120")) as send, \
             patch.object(app.time, "sleep") as pause:
            with self.assertRaisesRegex(ValueError, "http_503"):
                app.search_foods("rice", "fake-key")
        self.assertEqual(send.call_count, 1)
        pause.assert_not_called()

    def test_key_quota_and_query_errors_are_not_retried(self):
        for status in (400, 401, 403, 429):
            app.search_foods.clear()
            with self.subTest(status=status), \
                 patch.object(app.urllib.request, "urlopen", side_effect=self.http_error(status)) as send, \
                 patch.object(app.time, "sleep") as pause:
                with self.assertRaisesRegex(ValueError, f"http_{status}") as caught:
                    app.search_foods("rice", "fake-key")
                self.assertNotIn("fake-private-key", str(caught.exception))
                self.assertEqual(send.call_count, 1)
                pause.assert_not_called()

    def test_certificate_error_does_not_disable_verification_or_retry(self):
        failure = urllib.error.URLError(ssl.SSLCertVerificationError("fake-private-key"))
        with patch.object(app.urllib.request, "urlopen", side_effect=failure) as send, \
             patch.object(app.time, "sleep") as pause:
            with self.assertRaisesRegex(ValueError, "tls_certificate"):
                app.search_foods("rice", "fake-key")
        self.assertEqual(send.call_count, 1)
        self.assertNotIn("context", send.call_args.kwargs)
        pause.assert_not_called()

    def test_failed_search_is_not_cached(self):
        with patch.object(app.urllib.request, "urlopen", side_effect=TimeoutError("timeout")), \
             patch.object(app.time, "sleep"):
            with self.assertRaisesRegex(ValueError, "attempts: 3"):
                app.search_foods("rice", "fake-key")
        with patch.object(app.urllib.request, "urlopen", return_value=self.response()) as send:
            self.assertEqual(len(app.search_foods("rice", "fake-key")), 1)
            send.assert_called_once()

    def test_unreadable_response_recovers_but_invalid_shape_is_reported(self):
        with patch.object(app.urllib.request, "urlopen", side_effect=[io.BytesIO(b'<html>upstream error</html>'), self.response()]), \
             patch.object(app.time, "sleep"):
            self.assertEqual(len(app.search_foods("rice", "fake-key")), 1)
        app.search_foods.clear()
        with patch.object(app.urllib.request, "urlopen", return_value=io.BytesIO(b'{"foods":null}')):
            with self.assertRaisesRegex(ValueError, "invalid_response"):
                app.search_foods("rice", "fake-key")

    def test_retry_skips_successful_foods_and_recovers_without_gemini(self):
        raw = io.BytesIO()
        Image.new("RGB", (32, 32), "white").save(raw, format="JPEG")
        def upload(label, **kwargs):
            return [io.BytesIO(raw.getvalue())]
        meal = {"foods": [
            {"name": "Rice", "search_query": "rice cooked", "grams": 150, "grams_low": 100, "grams_high": 200},
            {"name": "Chicken", "search_query": "chicken cooked", "grams": 200, "grams_low": 150, "grams_high": 250}],
            "assumptions": []}
        gemini = io.BytesIO(json.dumps({"candidates": [{"finishReason": "STOP", "content": {
            "parts": [{"text": json.dumps(meal)}]}}]}).encode())
        failures = [TimeoutError("timeout") for _ in range(3)]
        with patch.dict(os.environ, {"GEMINI_API_KEY": "fake-key", "USDA_API_KEY": "fake-recovery-key", "RR_PORTION_MODE": "visual"}), \
             patch.object(app.st, "file_uploader", side_effect=upload), \
             patch.object(app.urllib.request, "urlopen", side_effect=[gemini, self.response(), *failures, self.response("Chicken cooked", 165)]) as send, \
             patch.object(app.time, "sleep"):
            page = AppTest.from_file(str(Path(app.__file__))).run()
            next(b for b in page.button if b.label == "Analyze meal").click().run()
            self.assertEqual(len(page.exception), 0)
            self.assertEqual(len(page.session_state["meal_result"]["meal"].foods), 2)
            self.assertEqual(sum("Nutrition lookup paused" in w.value for w in page.warning), 1)
            next(n for n in page.number_input if n.label == "Portion weight (grams)").set_value(180).run()
            next(b for b in page.button if b.label == "Retry nutrition").click().run()
            self.assertEqual(len(page.exception), 0)
            self.assertEqual(page.metric[0].value, "564 kcal")
            self.assertEqual(next(n for n in page.number_input if n.label == "Portion weight (grams)").value, 180)
            self.assertEqual(page.session_state["meal_result"]["lookup_errors"], [])
            self.assertEqual(send.call_count, 6)
            self.assertEqual(sum("generativelanguage" in c.args[0].full_url for c in send.call_args_list), 1)


if __name__ == "__main__":
    unittest.main()


from provider_fixture import use_gemini

def setUpModule():
    use_gemini()

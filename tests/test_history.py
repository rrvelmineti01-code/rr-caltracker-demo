"""Private browser history boundary checks; no legacy server database calls."""
import json
import sys
import unittest
import base64
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
import browser_history as history
from streamlit.testing.v1 import AppTest


def payload():
    return {"demo": False, "foods": [{"name":"Rice", "grams":150,
        "nutrients":{"Calories":195,"Protein":4,"Carbs":42,"Fat":.5}}],
        "totals":{"Calories":195,"Protein":4,"Carbs":42,"Fat":.5},
        "assumptions":["Unneeded context"], "excluded_foods":[]}


class BrowserBoundaryChecks(unittest.TestCase):
    def test_allowlist_removes_images_keys_and_freeform_notes(self):
        p=payload();p.update(image="must-not-save",api_key="must-not-save",description="must-not-save")
        p["foods"][0].update(image="must-not-save",portion_notes="must-not-save",email="must-not-save")
        clean=history.clean_snapshot(p)
        self.assertNotIn("must-not-save",json.dumps(clean))
        self.assertEqual(clean["totals"]["Calories"],195)
        self.assertEqual(clean["assumptions"],[])

    def test_demo_empty_and_invalid_nutrition_rejected(self):
        for p in [{**payload(),"demo":True},{**payload(),"foods":[]},
                  {**payload(),"totals":{"Calories":float('nan')}},None]:
            with self.subTest(p=p), self.assertRaises(ValueError): history.clean_snapshot(p)

    def test_pdf_supports_sanitized_browser_snapshot(self):
        report=history.build_meal_pdf(history.clean_snapshot(payload()))
        self.assertTrue(report.startswith(b'%PDF-'))

    def test_scaled_portion_bounds_remain_valid(self):
        p=payload();p['foods'][0].update(grams=5000,portion_low_g=3000,portion_high_g=10000)
        self.assertEqual(history.clean_snapshot(p)['foods'][0]['portion_high_g'],10000)

    def test_no_legacy_database_dependency(self):
        source=Path(app.__file__).read_text()
        self.assertNotIn('import meal_history',source)
        self.assertNotIn('import meal_store',source)
        self.assertNotIn('sqlite',Path(history.__file__).read_text())

    def test_history_navigation_mounts_private_component(self):
        page=AppTest.from_file(str(Path(app.__file__))).run()
        page.segmented_control(key='app-page').set_value('History').run()
        self.assertEqual(len(page.exception),0)
        self.assertFalse(page.text_input)
        self.assertFalse(page.date_input) # dates are selected locally, not on the server
        self.assertEqual(page.subheader[0].value,'History')

    def test_camera_mode_mounts_capture_without_personal_fields(self):
        with patch.object(app.st,'camera_input',return_value=None) as camera:
            page=AppTest.from_file(str(Path(app.__file__))).run()
            page.segmented_control(key='photo_source').set_value('Take photo').run()
            self.assertEqual(len(page.exception),0)
            camera.assert_called_once()
            self.assertEqual([x.label for x in page.text_input],['Food names or ingredients (optional)'])

    def test_explicit_saved_pdf_request_round_trip_without_provider_call(self):
        mounts=[]
        sent=False
        def mount(**kwargs):
            nonlocal sent
            mounts.append(kwargs["data"])
            request=None
            if kwargs["data"]["mode"]=="history" and not sent:
                sent=True
                request={"requestId":"test-request", "snapshot":payload()}
            return SimpleNamespace(export=request)
        with patch.object(history.components,"component",return_value=mount), \
             patch.object(app.urllib.request,"urlopen") as network:
            page=AppTest.from_file(str(Path(app.__file__))).run()
            page.segmented_control(key='app-page').set_value('History').run()
            self.assertEqual(len(page.exception),0)
            response=next(d['pdf'] for d in mounts if 'pdf' in d)
            self.assertEqual(response['requestId'],'test-request')
            self.assertTrue(base64.b64decode(response['base64']).startswith(b'%PDF-'))
            network.assert_not_called()
            self.assertNotIn('browser_pdf_response',page.session_state)

    def test_headline_expresses_user_goal(self):
        source=Path(app.ui.__file__).read_text()
        self.assertIn('Snap your meal.',source)
        self.assertIn('Know your calories.',source)
        self.assertIn('No profile needed.',source)


if __name__=='__main__': unittest.main()

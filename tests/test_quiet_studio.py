"""Check the approved two-step workflow with mocked providers and generated photos."""
import io
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
from streamlit.testing.v1 import AppTest
from test_multiphoto import photo, answer, usda


class QuietStudioChecks(unittest.TestCase):
    def test_review_step_is_disabled_until_analysis(self):
        with patch.dict(os.environ,{'GEMINI_API_KEY':'','USDA_API_KEY':''}):
            page=AppTest.from_file(str(Path(app.__file__))).run()
            self.assertEqual(len(page.exception),0)
            self.assertTrue(page.button(key='phase_review').disabled)
            self.assertEqual(page.session_state['meal_phase'],'Photos')

    def test_photo_review_and_history_preserve_inputs_without_new_provider_calls(self):
        image=photo('white');app.search_foods.clear()
        with patch.dict(os.environ,{'GEMINI_API_KEY':'fake','USDA_API_KEY':'studio-flow','RR_PORTION_MODE':'visual'}), \
             patch.object(app.st,'file_uploader',side_effect=lambda *a,**k:[io.BytesIO(image)]), \
             patch.object(app.urllib.request,'urlopen',side_effect=[answer(),usda()]) as send:
            page=AppTest.from_file(str(Path(app.__file__))).run()
            next(b for b in page.button if b.label=='Analyze meal').click().run()
            self.assertEqual(page.session_state['meal_phase'],'Review')
            self.assertFalse(page.button(key='phase_review').disabled)
            next(n for n in page.number_input if n.label=='Portion weight (grams)').set_value(200).run()
            self.assertEqual(page.metric[0].value,'260 kcal')
            page.button(key='phase_photos').click().run()
            self.assertEqual(page.session_state['meal_phase'],'Photos')
            page.button(key='phase_review').click().run()
            self.assertEqual(page.metric[0].value,'260 kcal')
            page.button(key='nav_toggle').click().run()
            self.assertEqual(page.session_state['app-page'],'History')
            self.assertFalse(page.metric)
            page.button(key='nav_toggle').click().run()
            self.assertEqual(len(page.exception),0)
            self.assertEqual(page.session_state['meal_phase'],'Review')
            self.assertEqual(page.metric[0].value,'260 kcal')
            self.assertEqual(send.call_count,2)

    def test_changed_photo_returns_to_photos_and_requires_new_analysis(self):
        batch=[photo('white')];app.search_foods.clear()
        with patch.dict(os.environ,{'GEMINI_API_KEY':'fake','USDA_API_KEY':'studio-change','RR_PORTION_MODE':'visual'}), \
             patch.object(app.st,'file_uploader',side_effect=lambda *a,**k:[io.BytesIO(b) for b in batch]), \
             patch.object(app.urllib.request,'urlopen',side_effect=[answer(),usda()]) as send:
            page=AppTest.from_file(str(Path(app.__file__))).run()
            next(b for b in page.button if b.label=='Analyze meal').click().run()
            page.button(key='phase_photos').click().run()
            batch.append(photo('red'));page.run()
            self.assertEqual(page.session_state['meal_phase'],'Photos')
            self.assertNotIn('meal_result',page.session_state)
            self.assertTrue(page.button(key='phase_review').disabled)
            self.assertEqual(send.call_count,2)

    def test_live_camera_is_unmounted_in_review(self):
        image=photo('white');app.search_foods.clear()
        with patch.dict(os.environ,{'GEMINI_API_KEY':'fake','USDA_API_KEY':'studio-camera','RR_PORTION_MODE':'visual'}), \
             patch.object(app.st,'camera_input',side_effect=lambda *a,**k:io.BytesIO(image)) as camera, \
             patch.object(app.urllib.request,'urlopen',side_effect=[answer(),usda()]):
            page=AppTest.from_file(str(Path(app.__file__))).run()
            page.segmented_control(key='photo_source').set_value('Take photos').run()
            next(b for b in page.button if b.label=='Add photo').click().run()
            next(b for b in page.button if b.label=='Analyze meal').click().run()
            self.assertEqual(page.session_state['meal_phase'],'Review')
            previous=camera.call_count
            page.run()
            self.assertEqual(camera.call_count,previous)
            self.assertEqual(len(page.session_state['camera_meal_photos']),1)


if __name__=='__main__':unittest.main()


from provider_fixture import use_gemini

def setUpModule():
    use_gemini()

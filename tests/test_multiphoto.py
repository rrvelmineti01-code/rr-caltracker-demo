"""Multi-view requests, camera batches and stale-result boundaries (offline)."""
import base64
import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from streamlit.testing.v1 import AppTest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
import portion_estimator


def photo(color):
    out=io.BytesIO()
    image=Image.new('RGB',(40,30),color)
    exif=image.getexif();exif[270]='private image metadata'
    image.save(out,format='JPEG',exif=exif)
    return out.getvalue()


def answer():
    meal={'foods':[{'name':'Rice','search_query':'rice cooked','grams':150,
                   'grams_low':100,'grams_high':200,'portion_notes':'Visual estimate.'}], 'assumptions':[]}
    return io.BytesIO(json.dumps({'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(meal)}]}}]}).encode())


def usda():
    return io.BytesIO(json.dumps({'foods':[{'fdcId':101,'description':'Rice cooked',
        'foodNutrients':[{'nutrientId':1008,'unitName':'KCAL','value':130}]}]}).encode())


class MultiPhotoChecks(unittest.TestCase):
    def test_invalid_request_batches_stop_before_provider_call(self):
        for images in [[],[b'image']*6,[b'image',None],[b''],[b'a'*(app.MAX_PREPARED_PHOTO_BYTES+1)]]:
            with self.subTest(count=len(images)),patch.object(app.gemini_transport,'request_json') as send:
                with self.assertRaises(ValueError): app.identify_foods(images,'','fake')
                send.assert_not_called()

    def test_all_images_are_prepared_and_duplicates_are_removed(self):
        a,b=photo('white'),photo('red')
        images=app.prepare_meal_photos([io.BytesIO(a),io.BytesIO(b),io.BytesIO(a)])
        self.assertEqual(len(images),2)
        for image in images:
            with Image.open(io.BytesIO(image)) as loaded:
                self.assertEqual(loaded.format,'JPEG')
                self.assertFalse(loaded.getexif())
            self.assertNotIn(b'private image metadata',image)

    def test_invalid_file_rejects_whole_batch_and_oversize_checks_remain(self):
        with self.assertRaises((ValueError,OSError)):
            app.prepare_meal_photos([io.BytesIO(photo('white')),io.BytesIO(b'not an image')])
        with self.assertRaises(ValueError): app.prepare_meal_photos([io.BytesIO(b'x'*(10*1024*1024+1))])
        with self.assertRaises(ValueError): app.prepare_meal_photos([io.BytesIO(photo('white'))]*6)

    def test_five_views_share_one_request_and_keep_nutrition_and_editing(self):
        raws=[photo(c) for c in ['white','red','green','blue','gray']]
        expected=[app.prepare_image(r) for r in raws]
        uploads=lambda *a,**k:[io.BytesIO(r) for r in raws]
        app.search_foods.clear()
        with patch.dict(os.environ,{'GEMINI_API_KEY':'fake','USDA_API_KEY':'multi-five','RR_PORTION_MODE':'hybrid'}), \
             patch.object(app.st,'file_uploader',side_effect=uploads) as picker, \
             patch.object(app.portion_estimator,'predict_mass',return_value=portion_estimator.PortionEstimate(300)) as mass, \
             patch.object(app.urllib.request,'urlopen',side_effect=[answer(),usda()]) as send:
            page=AppTest.from_file(str(Path(app.__file__))).run()
            self.assertEqual(len(page.exception),0)
            self.assertTrue(picker.call_args.kwargs['accept_multiple_files'])
            self.assertEqual(picker.call_args.kwargs['max_upload_size'],10)
            self.assertFalse(page.selectbox)
            self.assertFalse(page.number_input)
            self.assertNotIn('Extra photo & portion options',[e.label for e in page.expander])
            next(b for b in page.button if b.label=='Analyze meal').click().run()
            self.assertEqual(len(page.exception),0)
            payload=json.loads(send.call_args_list[0].args[0].data)
            images=[base64.b64decode(p['inlineData']['data']) for p in payload['contents'][0]['parts'] if 'inlineData' in p]
            self.assertEqual(images,expected)
            self.assertEqual(send.call_count,2)
            mass.assert_called_once_with(expected[0])
            self.assertEqual(page.metric[0].value,'390 kcal') # one serving, not five
            next(n for n in page.number_input if n.label=='Portion weight (grams)').set_value(200).run()
            self.assertEqual(page.metric[0].value,'260 kcal')
            self.assertEqual(send.call_count,2)
            self.assertEqual(mass.call_count,1)

    def test_changing_or_removing_later_view_invalidates_current_result(self):
        batch=[photo('white'),photo('red'),photo('green')]
        app.search_foods.clear()
        with patch.dict(os.environ,{'GEMINI_API_KEY':'fake','USDA_API_KEY':'multi-change','RR_PORTION_MODE':'visual'}), \
             patch.object(app.st,'file_uploader',side_effect=lambda *a,**k:[io.BytesIO(r) for r in batch]), \
             patch.object(app.urllib.request,'urlopen',side_effect=[answer(),usda(),answer()]) as send:
            page=AppTest.from_file(str(Path(app.__file__))).run()
            next(b for b in page.button if b.label=='Analyze meal').click().run()
            first=page.session_state['meal_result']['signature']
            batch[2]=photo('blue');page.run()
            self.assertNotIn('meal_result',page.session_state)
            self.assertFalse(page.metric)
            self.assertEqual(send.call_count,2) # no hidden analysis on file changes
            next(b for b in page.button if b.label=='Analyze meal').click().run()
            self.assertNotEqual(first,page.session_state['meal_result']['signature'])
            batch.pop(1);page.run()
            self.assertNotIn('meal_result',page.session_state)
            self.assertEqual(send.call_count,3)

    def test_excess_photos_block_analysis_and_clear_stale_results(self):
        batch=[photo('white')]
        app.search_foods.clear()
        with patch.dict(os.environ,{'GEMINI_API_KEY':'fake','USDA_API_KEY':'multi-limit','RR_PORTION_MODE':'visual'}), \
             patch.object(app.st,'file_uploader',side_effect=lambda *a,**k:[io.BytesIO(r) for r in batch]), \
             patch.object(app.urllib.request,'urlopen',side_effect=[answer(),usda()]) as send:
            page=AppTest.from_file(str(Path(app.__file__))).run()
            next(b for b in page.button if b.label=='Analyze meal').click().run()
            batch.extend([photo('red')]*5);page.run()
            self.assertEqual(len(page.exception),0)
            self.assertNotIn('meal_result',page.session_state)
            self.assertTrue(next(b for b in page.button if b.label=='Analyze meal').disabled)
            self.assertTrue(any('up to 5' in e.value for e in page.error))
            self.assertEqual(send.call_count,2)

    def test_camera_adds_several_views_and_removes_them_without_network(self):
        raw=photo('white')
        with patch.object(app.st,'camera_input',side_effect=lambda *a,**k:io.BytesIO(raw)), \
             patch.object(app.urllib.request,'urlopen') as send:
            page=AppTest.from_file(str(Path(app.__file__))).run()
            page.segmented_control(key='photo_source').set_value('Take photos').run()
            next(b for b in page.button if b.label=='Add photo').click().run()
            self.assertEqual(len(page.exception),0)
            self.assertEqual(len(page.session_state['camera_meal_photos']),1)
            raw=photo('red');page.run()
            next(b for b in page.button if b.label=='Add photo').click().run()
            self.assertEqual(len(page.session_state['camera_meal_photos']),2)
            page.button(key='remove_camera_0').click().run()
            self.assertEqual(page.session_state['camera_meal_photos'],[app.prepare_image(raw)])
            page.button(key='remove_camera_0').click().run()
            self.assertEqual(page.session_state['camera_meal_photos'],[])
            self.assertTrue(next(b for b in page.button if b.label=='Analyze meal').disabled)
            send.assert_not_called()

    def test_camera_duplicates_and_limit_are_rejected(self):
        a=photo('white');prepared=app.prepare_image(a)
        with self.assertRaisesRegex(ValueError,'already added'): app.add_camera_photo(a,[prepared])
        with self.assertRaises(ValueError): app.add_camera_photo(photo('red'),[prepared]*5)


if __name__=='__main__': unittest.main()


from provider_fixture import use_gemini

def setUpModule():
    use_gemini()

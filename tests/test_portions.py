"""Model execution and hybrid boundaries; these are not accuracy benchmarks."""
import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
import portion_estimator as portion
from streamlit.testing.v1 import AppTest


def photo(color='white'):
    buffer=io.BytesIO()
    Image.new('RGB',(128,96),color).save(buffer,format='JPEG')
    return buffer.getvalue()


def food_response():
    meal={'foods':[{'name':'Rice','search_query':'rice cooked','grams':100,
                   'grams_low':80,'grams_high':120,'portion_notes':'Visual estimate.'}],
          'assumptions':['Example']}
    return io.BytesIO(json.dumps({'candidates':[{'finishReason':'STOP',
                       'content':{'parts':[{'text':json.dumps(meal)}]}}]}).encode())


class PortionChecks(unittest.TestCase):
    def test_public_model_runs_fresh_and_repeatably(self):
        image=photo('gray')
        session=portion.model_session()
        with patch.object(portion,'model_session',return_value=session):
            results=[portion.predict_mass(image).grams for _ in range(5)]
        self.assertTrue(all(np.isfinite(r) for r in results))
        self.assertLess(max(results)-min(results),.001)

    def test_no_prediction_cache_is_used(self):
        class Session:
            calls=0
            def run(self,*args):
                self.calls+=1
                return [np.array([[100.+self.calls]],dtype=np.float32)]
        session=Session()
        with patch.object(portion,'model_session',return_value=session):
            first=portion.predict_mass(photo()).grams
            second=portion.predict_mass(photo()).grams
        self.assertEqual((session.calls,first,second),(2,101,102))

    def test_preprocessing_matches_published_weight_contract(self):
        tensor=portion.image_tensor(photo('white'))
        self.assertEqual(tensor.shape,(1,3,224,224))
        self.assertEqual(tensor.dtype,np.float32)
        self.assertTrue(np.all(tensor==1))

    def test_invalid_model_predictions_do_not_become_food_weights(self):
        for mass in [float('nan'),float('inf'),-10,0,8000]:
            session=type('Session',(),{'run':lambda self,*args:[np.array([[mass]])]})()
            with self.subTest(mass=mass),patch.object(portion,'model_session',return_value=session):
                with self.assertRaises(portion.PortionError): portion.predict_mass(photo())

    def test_allocation_preserves_sum_and_relative_weights(self):
        weights=portion.allocate_mass([100,300],600)
        self.assertEqual(weights,[150,450])
        self.assertAlmostEqual(sum(weights),600)
        small=portion.allocate_mass([1,999],100)
        self.assertAlmostEqual(sum(small),100)
        self.assertGreaterEqual(min(small),1)

    def test_unsafe_allocation_is_rejected(self):
        for weights,total in [([0,1],100),([float('nan')],100),([1,1],1),([1],6000)]:
            with self.subTest(weights=weights,total=total),self.assertRaises(portion.PortionError):
                portion.allocate_mass(weights,total)

    def test_hybrid_clears_unvalidated_ranges_and_identifies_allocation(self):
        meal=app.Meal(foods=[app.Food(name='Rice',search_query='rice cooked',grams=100,
                                    grams_low=80,grams_high=120)],assumptions=[])
        changed,diagnostic=portion.apply_portions(meal,portion.PortionEstimate(300))
        self.assertEqual(changed.foods[0].grams,300)
        self.assertIsNone(changed.foods[0].grams_low)
        self.assertFalse(diagnostic['validated_accuracy'])
        self.assertIn('not weighed individually',changed.foods[0].portion_notes)
        self.assertEqual(meal.foods[0].grams,100)

    def test_hybrid_flow_recalculates_pdf_and_repeats_both_stages(self):
        usda={'foods':[{'fdcId':1,'description':'Cooked rice','foodNutrients':[
            {'nutrientId':1008,'unitName':'KCAL','value':130}]}]}
        def upload(label,**kwargs): return [io.BytesIO(photo())]
        app.search_foods.clear()
        with patch.dict(os.environ,{'GEMINI_API_KEY':'fake-key','USDA_API_KEY':'fake-usda','RR_PORTION_MODE':'hybrid'}), \
             patch.object(app.st,'file_uploader',side_effect=upload), \
             patch.object(app.portion_estimator,'predict_mass',return_value=portion.PortionEstimate(300)) as predict, \
             patch.object(app.urllib.request,'urlopen',side_effect=[food_response(),io.BytesIO(json.dumps(usda).encode()),food_response()]) as send:
            page=AppTest.from_file(str(Path(app.__file__))).run()
            next(b for b in page.button if b.label=='Analyze meal').click().run()
            self.assertEqual(len(page.exception),0)
            self.assertEqual(page.metric[0].value,'390 kcal')
            self.assertEqual(page.session_state['meal_result']['portion']['mode'],'hybrid')
            number=next(n for n in page.number_input if n.label=='Portion weight (grams)')
            number.set_value(200).run()
            self.assertEqual(page.metric[0].value,'260 kcal')
            self.assertEqual(predict.call_count,1)
            next(b for b in page.button if b.label=='Analyze meal').click().run()
            self.assertEqual(len(page.exception),0)
            self.assertEqual(page.metric[0].value,'390 kcal')
            self.assertEqual(predict.call_count,2)
            self.assertEqual(send.call_count,3)

    def test_unavailable_model_is_an_explicit_visual_fallback(self):
        def upload(label,**kwargs): return [io.BytesIO(photo())]
        app.search_foods.clear()
        usda={'foods':[{'fdcId':2,'description':'Rice','foodNutrients':[{'nutrientId':1008,'unitName':'KCAL','value':130}]}]}
        with patch.dict(os.environ,{'GEMINI_API_KEY':'fake-key','USDA_API_KEY':'fallback-usda','RR_PORTION_MODE':'hybrid'}), \
             patch.object(app.st,'file_uploader',side_effect=upload), \
             patch.object(app.portion_estimator,'predict_mass',side_effect=portion.PortionError('model missing')), \
             patch.object(app.urllib.request,'urlopen',side_effect=[food_response(),io.BytesIO(json.dumps(usda).encode())]):
            page=AppTest.from_file(str(Path(app.__file__))).run()
            next(b for b in page.button if b.label=='Analyze meal').click().run()
            self.assertEqual(len(page.exception),0)
            self.assertEqual(page.session_state['meal_result']['portion']['mode'],'visual')
            self.assertTrue(any('Using visual portions' in w.value for w in page.warning))
            self.assertEqual(page.metric[0].value,'130 kcal')

    def test_no_food_skips_portion_inference(self):
        def upload(label,**kwargs): return [io.BytesIO(photo())]
        answer={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'{"foods":[],"assumptions":[]}'}]}}]}
        with patch.dict(os.environ,{'GEMINI_API_KEY':'fake-key','USDA_API_KEY':'fake-usda','RR_PORTION_MODE':'hybrid'}), \
             patch.object(app.st,'file_uploader',side_effect=upload), \
             patch.object(app.portion_estimator,'predict_mass') as predict, \
             patch.object(app.urllib.request,'urlopen',return_value=io.BytesIO(json.dumps(answer).encode())):
            page=AppTest.from_file(str(Path(app.__file__))).run()
            next(b for b in page.button if b.label=='Analyze meal').click().run()
            self.assertEqual(len(page.exception),0)
            predict.assert_not_called()


if __name__=='__main__': unittest.main()

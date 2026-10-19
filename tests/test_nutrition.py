"""Micronutrients, units, coverage and the live app path with offline providers."""
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import app
import browser_history
import nutrition as n
from streamlit.testing.v1 import AppTest
from PIL import Image


def food(*rows):
    return {"fdcId": 1, "description": "Test food", "foodNutrients": [
        {"nutrientId": key, "value": value, "unitName": unit} for key, value, unit in rows]}


class NutrientChecks(unittest.TestCase):
    def test_search_and_detail_shapes_use_same_units(self):
        a=food((1114,2.5,"UG"),(1178,.08,"UG"),(1089,1.2,"MG"))
        b={"foodNutrients":[{"nutrient":{"id":1114,"unitName":"µg"},"amount":2.5}]}
        self.assertEqual(n.nutrient_values(a)["Vitamin D"],2.5)
        self.assertEqual(n.nutrient_values(b)["Vitamin D"],2.5)
        self.assertAlmostEqual(n.scale_nutrients(a,150)["Vitamin B12"],.12)
        self.assertAlmostEqual(n.scale_nutrients(a,150)["Iron"],1.8)

    def test_folate_forms_and_vitamin_a_forms_are_not_added(self):
        a=food((1177,100,"UG"),(1190,200,"UG"),(1106,20,"UG"),(1104,1000,"IU"))
        self.assertEqual(n.nutrient_values(a)["Vitamin B9"],100)
        self.assertEqual(n.nutrient_values(a)["Vitamin A"],20)

    def test_mass_units_convert_but_iu_is_never_used_as_micrograms(self):
        a=food((1178,.002,"MG"),(1114,30,"IU"))
        self.assertAlmostEqual(n.nutrient_values(a)["Vitamin B12"],2)
        self.assertIsNone(n.nutrient_values(a)["Vitamin D"])

    def test_missing_zero_and_invalid_values_are_different(self):
        for bad in [True,-1,float("nan"),float("inf"),"1",None]:
            with self.subTest(bad=bad):
                self.assertIsNone(n.nutrient_values(food((1114,bad,"UG")))["Vitamin D"])
        self.assertEqual(n.nutrient_values(food((1114,0,"UG")))["Vitamin D"],0)
        self.assertIsNone(n.nutrient_values(food())["Vitamin D"])

    def test_strict_totals_and_partial_known_amounts(self):
        a=food((1114,2,"UG"),(1089,0,"MG"));b=food((1089,1,"MG"))
        self.assertIsNone(n.calculate_totals([(150,a),(100,b)])["Vitamin D"])
        rows=[{"grams":150,"nutrients":n.scale_nutrients(a,150)},
              {"grams":100,"nutrients":n.scale_nutrients(b,100)}]
        summary=n.summarize_foods(rows,["Unmatched sauce"])
        self.assertEqual(summary["Vitamin D"],{"value":3,"known":1,"total":3})
        self.assertEqual(summary["Iron"],{"value":1,"known":2,"total":3})
        self.assertEqual(n.coverage_label(summary["Vitamin D"]),"Partial · 1/3 foods")
        self.assertIsNone(summary["Vitamin B12"]["value"])

    def test_zero_portion_does_not_make_consumed_nutrients_unknown(self):
        a=food((1114,2,"UG"))
        self.assertEqual(n.calculate_totals([(100,a),(0,food())])["Vitamin D"],2)
        summary=n.summarize_foods([{"grams":0,"nutrients":{}}])
        self.assertEqual(summary["Vitamin D"]["total"],0)

    def test_small_amounts_never_display_as_zero(self):
        self.assertEqual(n.format_amount(.004,"mcg"),"<0.01 mcg")
        self.assertEqual(n.format_amount(.12,"mcg"),"0.12 mcg")
        self.assertEqual(n.format_amount(0,"mg"),"0 mg")

    def test_snapshot_keeps_micros_and_old_snapshot_remains_readable(self):
        payload={"foods":[{"name":"Egg","grams":100,"nutrients":{"Vitamin D":2,"Vitamin B12":.12}}],
                 "totals":{"Vitamin D":2,"Vitamin B12":.12},"api_key":"do-not-save"}
        saved=browser_history.clean_snapshot(payload)
        self.assertEqual(saved["foods"][0]["nutrients"]["Vitamin B12"],.12)
        self.assertNotIn("do-not-save",json.dumps(saved))
        old={"foods":[{"name":"Rice","grams":100,"nutrients":{"Calories":130}}],"totals":{"Calories":130}}
        old=browser_history.clean_snapshot(old)
        self.assertEqual(old["totals"]["Calories"],130)
        self.assertIsNone(old["totals"]["Vitamin D"])
        self.assertEqual(n.summarize_foods(old["foods"])["Vitamin D"]["known"],0)

    def test_groq_review_portion_change_and_saved_snapshot(self):
        raw=io.BytesIO();Image.new("RGB",(32,32),"white").save(raw,format="JPEG")
        meal={"foods":[{"name":"Egg","search_query":"egg cooked","grams":100,"grams_low":80,
                       "grams_high":120,"portion_notes":"Test portion"}],"assumptions":[]}
        vision={"choices":[{"finish_reason":"stop","message":{"content":json.dumps(meal)}}]}
        matched=food((1008,150,"KCAL"),(1003,12,"G"),(1004,10,"G"),(1005,1,"G"),(1079,0,"G"),
                     (1114,2,"UG"),(1178,.12,"UG"),(1087,50,"MG"),(1089,1,"MG"))
        captured=[]
        def mount(**kwargs):
            captured.append(kwargs["data"])
            return SimpleNamespace(export=None)
        app.search_foods.clear()
        with patch.dict(os.environ,{"RR_VISION_PROVIDER":"groq","GROQ_API_KEY":"fake","USDA_API_KEY":"nutrition-test","RR_PORTION_MODE":"visual"}), \
             patch.object(app.st,"file_uploader",side_effect=lambda *a,**k:[io.BytesIO(raw.getvalue())]), \
             patch.object(browser_history.components,"component",return_value=mount), \
             patch.object(app.urllib.request,"urlopen",side_effect=[io.BytesIO(json.dumps(vision).encode()),io.BytesIO(json.dumps({"foods":[matched]}).encode())]) as network:
            page=AppTest.from_file(str(Path(app.__file__))).run()
            next(b for b in page.button if b.label=="Analyze meal").click().run()
            self.assertFalse(page.exception)
            saved=[d["snapshot"] for d in captured if "snapshot" in d][-1]
            self.assertEqual(saved["totals"]["Vitamin D"],2)
            next(x for x in page.number_input if x.label=="Portion weight (grams)").set_value(250).run()
            self.assertFalse(page.exception)
            saved=[d["snapshot"] for d in captured if "snapshot" in d][-1]
            self.assertEqual(saved["totals"]["Vitamin D"],5)
            self.assertAlmostEqual(saved["foods"][0]["nutrients"]["Vitamin B12"],.3)
            self.assertEqual(network.call_count,2)
            self.assertEqual(len([d for d in captured if d.get("nutrients")]),len(captured))

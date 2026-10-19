"""Offline integration tests: mock providers, no credentials or meal photos needed."""
import ast
import base64
import http.client
import io
import json
import os
from pathlib import Path
import types
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request
import hashlib
from pydantic import BaseModel, Field, model_validator
from branding import REPORT_PREFIX, VERSION

tree = ast.parse((Path(__file__).resolve().parents[1] / 'app.py').read_text())
names = {'app_setting', 'Food', 'Meal', 'validate_meal_images', 'identify_foods', 'identify_with_groq', 'analysis_signature', 'groq_http_error_message'}
nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
ns = dict(globals(), st=types.SimpleNamespace(secrets={}), VISION_PROVIDER='groq',
          MAX_MEAL_PHOTOS=3, MAX_PREPARED_PHOTO_BYTES=12 * 1024 * 1024,
          gemini_transport=types.SimpleNamespace())
exec(compile(ast.Module(body=nodes, type_ignores=[]), 'app.py', 'exec'), ns)

FOOD = {'name':'tofu', 'search_query':'tofu cooked', 'grams':100,
        'grams_low':60, 'grams_high':150, 'portion_notes':'Visual estimate.'}

def response(meal=None, finish='stop'):
    return io.BytesIO(json.dumps({'choices':[{'finish_reason':finish, 'message':{
        'content':json.dumps(meal if meal is not None else {'foods':[FOOD], 'assumptions':[]})}}]}).encode())

class IntegrationTests(unittest.TestCase):
    def test_groq_dispatch_and_payload(self):
        with patch.object(urllib.request, 'urlopen', return_value=response()) as call:
            result = ns['identify_foods']([b'jpeg1', b'jpeg2'], 'meal', 'fake-test-key')
        self.assertEqual(result.foods[0].name, 'tofu')
        req = call.call_args.args[0]
        self.assertEqual(req.full_url, 'https://api.groq.com/openai/v1/chat/completions')
        self.assertEqual(req.get_header('Authorization'), 'Bearer fake-test-key')
        data = json.loads(req.data)
        self.assertEqual(data['response_format'], {'type':'json_object'})
        images = [x for x in data['messages'][1]['content'] if x['type']=='image_url']
        self.assertEqual(len(images), 2)
        self.assertEqual(base64.b64decode(images[0]['image_url']['url'].split(',')[1]), b'jpeg1')

    def test_photo_limit_before_network(self):
        with patch.object(urllib.request, 'urlopen') as call:
            with self.assertRaises(ValueError):
                ns['identify_foods']([b'x']*4, '', 'key')
            call.assert_not_called()

    def test_invalid_and_truncated_results(self):
        cases = [({'foods':[dict(FOOD, grams=-1)], 'assumptions':[]}, 'stop'),
                 ({'foods':[dict(FOOD, grams_low=110)], 'assumptions':[]}, 'stop'),
                 ({'foods':[dict(FOOD, grams_low=None, grams_high=None)], 'assumptions':[]}, 'stop'),
                 (None, 'length'), ({}, 'stop')]
        for meal, finish in cases:
            with self.subTest(meal=meal, finish=finish):
                with patch.object(urllib.request, 'urlopen', return_value=response(meal, finish)):
                    with self.assertRaisesRegex(ValueError, 'valid food list'):
                        ns['identify_foods']([b'x'], '', 'key')

    def test_empty_meal(self):
        with patch.object(urllib.request, 'urlopen', return_value=response({'foods':[], 'assumptions':['No food']})):
            self.assertEqual(ns['identify_foods']([b'x'], '', 'key').foods, [])

    def test_safe_http_errors(self):
        for status in [400,401,403,404,413,429,500]:
            error = urllib.error.HTTPError('https://private.invalid', status, 'SECRET', {}, io.BytesIO(b'SECRET'))
            with patch.object(urllib.request, 'urlopen', side_effect=error) as call:
                with self.assertRaises(ValueError) as caught:
                    ns['identify_foods']([b'x'], '', 'key')
                self.assertNotIn('SECRET', str(caught.exception))
                self.assertEqual(call.call_count, 1)

    def test_timeout_and_invalid_json(self):
        with patch.object(urllib.request, 'urlopen', side_effect=TimeoutError('SECRET')):
            with self.assertRaisesRegex(ValueError, 'secure connection'):
                ns['identify_foods']([b'x'], '', 'key')
        with patch.object(urllib.request, 'urlopen', return_value=io.BytesIO(b'not json')):
            with self.assertRaisesRegex(ValueError, 'unreadable'):
                ns['identify_foods']([b'x'], '', 'key')

    def test_secret_lookup(self):
        with patch.dict(os.environ, {}, clear=True):
            ns['st'].secrets = {'GROQ_API_KEY':' fake '}
            self.assertEqual(ns['app_setting']('GROQ_API_KEY'), 'fake')
            self.assertEqual(ns['app_setting']('MISSING','default'), 'default')
            ns['st'].secrets = {}

    def test_gemini_rollback_dispatch(self):
        ns['VISION_PROVIDER'] = 'gemini'
        ns['gemini_transport'].request_json = lambda *a, **kw: {'candidates':[{
            'finishReason':'STOP','content':{'parts':[{'text':json.dumps({'foods':[FOOD],'assumptions':[]})}]}}]}
        try:
            with patch.object(urllib.request, 'urlopen') as call:
                self.assertEqual(ns['identify_foods']([b'x'], '', 'key').foods[0].grams, 100)
                call.assert_not_called()
        finally:
            ns['VISION_PROVIDER'] = 'groq'

    def test_provider_changes_signature(self):
        first = ns['analysis_signature']([b'x'], '')
        ns['VISION_PROVIDER'] = 'gemini'
        try:
            self.assertNotEqual(first, ns['analysis_signature']([b'x'], ''))
        finally:
            ns['VISION_PROVIDER'] = 'groq'

if __name__ == '__main__':
    unittest.main()

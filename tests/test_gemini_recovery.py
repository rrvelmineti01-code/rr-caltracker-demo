"""Exercise transient recovery, credential protection and retry limits offline."""
import io
import json
import socket
import ssl
import sys
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gemini_transport as client


def response():
    return io.BytesIO(b'{"ok":true}')


def http(code, headers=None, body=None):
    return urllib.error.HTTPError('https://example.invalid/key-must-not-leak', code,
                                  'key-must-not-leak', headers or {},
                                  io.BytesIO(json.dumps(body or {}).encode()))


class GeminiRecoveryChecks(unittest.TestCase):
    def setUp(self):
        self.request = urllib.request.Request('https://example.invalid', data=b'private-photo',
                                              headers={'x-goog-api-key':'key-must-not-leak'})
        sleeper = patch.object(client.time, 'sleep')
        self.sleep = sleeper.start()
        self.addCleanup(sleeper.stop)

    def test_timeout_then_success_uses_identical_request(self):
        events = []
        with patch.object(client.urllib.request, 'urlopen', side_effect=[TimeoutError(),response()]) as send:
            self.assertTrue(client.request_json(self.request, progress=events.append)['ok'])
        self.assertEqual(send.call_count,2)
        self.assertIs(send.call_args_list[0].args[0],send.call_args_list[1].args[0])
        self.assertEqual(len(events),1)
        self.assertEqual(self.sleep.call_count,1)

    def test_failures_stop_after_three_attempts_without_exposure(self):
        with patch.object(client.urllib.request,'urlopen',side_effect=TimeoutError('key-must-not-leak')) as send:
            with self.assertRaises(client.GeminiRequestError) as caught:
                client.request_json(self.request)
        self.assertEqual((caught.exception.kind,caught.exception.attempts),('timeout',3))
        self.assertEqual(send.call_count,3)
        self.assertEqual(self.sleep.call_count,2)
        self.assertNotIn('key-must-not-leak',str(caught.exception))
        self.assertIn('app server',str(caught.exception))

    def test_503_recovery(self):
        with patch.object(client.urllib.request,'urlopen',side_effect=[http(503),response()]) as send:
            self.assertTrue(client.request_json(self.request)['ok'])
        self.assertEqual(send.call_count,2)

    def test_permanent_http_errors_are_not_retried(self):
        for code in [400,401,402,403,404,501]:
            with self.subTest(code=code),patch.object(client.urllib.request,'urlopen',side_effect=http(code)) as send:
                with self.assertRaises(client.GeminiRequestError) as caught:
                    client.request_json(self.request)
                self.assertEqual(send.call_count,1)
                self.assertNotIn('key-must-not-leak',str(caught.exception))

    def test_quota_without_short_retry_hint_is_not_retried(self):
        with patch.object(client.urllib.request,'urlopen',side_effect=http(429)) as send:
            with self.assertRaises(client.GeminiRequestError) as caught: client.request_json(self.request)
        self.assertEqual(caught.exception.kind,'quota')
        self.assertEqual(send.call_count,1)

    def test_daily_quota_is_not_retried_even_with_short_header(self):
        failure=http(429,{'Retry-After':'2'},{'error':{'message':'daily quota exhausted'}})
        with patch.object(client.urllib.request,'urlopen',side_effect=failure) as send:
            with self.assertRaises(client.GeminiRequestError): client.request_json(self.request)
        self.assertEqual(send.call_count,1)

    def test_explicit_short_rate_limit_can_recover(self):
        failure=http(429,{'Retry-After':'2'},{'error':{'message':'requests per minute limit reached'}})
        with patch.object(client.urllib.request,'urlopen',side_effect=[failure,response()]) as send:
            self.assertTrue(client.request_json(self.request)['ok'])
        self.assertEqual(send.call_count,2)
        self.assertGreaterEqual(self.sleep.call_args.args[0],2)

    def test_long_retry_after_stops_without_retrying_early(self):
        with patch.object(client.urllib.request,'urlopen',side_effect=http(503,{'Retry-After':'90'})) as send:
            with self.assertRaises(client.GeminiRequestError): client.request_json(self.request)
        self.assertEqual(send.call_count,1)

    def test_certificate_failure_is_not_retried(self):
        failure=urllib.error.URLError(ssl.SSLCertVerificationError('key-must-not-leak'))
        with patch.object(client.urllib.request,'urlopen',side_effect=failure) as send:
            with self.assertRaises(client.GeminiRequestError) as caught: client.request_json(self.request)
        self.assertEqual((caught.exception.kind,send.call_count),('tls_certificate',1))

    def test_temporary_dns_can_recover_permanent_dns_does_not_retry(self):
        failure=urllib.error.URLError(socket.gaierror(socket.EAI_AGAIN,'private detail'))
        with patch.object(client.urllib.request,'urlopen',side_effect=[failure,response()]):
            self.assertTrue(client.request_json(self.request)['ok'])
        failure=urllib.error.URLError(socket.gaierror(socket.EAI_NONAME,'private detail'))
        with patch.object(client.urllib.request,'urlopen',side_effect=failure) as send:
            with self.assertRaises(client.GeminiRequestError) as caught: client.request_json(self.request)
        self.assertEqual((caught.exception.kind,send.call_count),('dns',1))

    def test_invalid_json_is_not_retried(self):
        with patch.object(client.urllib.request,'urlopen',return_value=io.BytesIO(b'not-json')) as send:
            with self.assertRaises(client.GeminiRequestError) as caught: client.request_json(self.request)
        self.assertEqual((caught.exception.kind,send.call_count),('unreadable_response',1))

    def test_budget_bounds_timeout_and_backoff(self):
        with patch.object(client.time,'monotonic',side_effect=[0,0,2]), \
             patch.object(client.urllib.request,'urlopen',side_effect=TimeoutError()) as send:
            with self.assertRaises(client.GeminiRequestError): client.request_json(self.request,budget_seconds=1)
        self.assertEqual(send.call_args.kwargs['timeout'],1)
        self.assertEqual(send.call_count,1)
        self.sleep.assert_not_called()


if __name__=='__main__': unittest.main()

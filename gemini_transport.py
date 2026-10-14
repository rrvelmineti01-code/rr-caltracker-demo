"""Bounded Gemini REST recovery; never log photos, keys, URLs or raw bodies."""
import errno
import http.client
import json
import logging
import random
import socket
import ssl
import time
import urllib.error
import urllib.request


class GeminiRequestError(ValueError):
    def __init__(self, message, kind, attempts=1):
        self.kind, self.attempts = kind, attempts
        super().__init__(f"{message} (Gemini code: {kind}; attempts: {attempts}.)")


def transport_kind(error):
    reason = error.reason if isinstance(error, urllib.error.URLError) else error
    if isinstance(reason, ssl.SSLCertVerificationError):
        return "tls_certificate", False
    if isinstance(reason, ssl.SSLError):
        return "tls", False
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return "timeout", True
    if isinstance(reason, socket.gaierror):
        return "dns", reason.errno == socket.EAI_AGAIN
    if isinstance(reason, (ConnectionError, http.client.HTTPException)):
        return "connection", True
    if isinstance(reason, OSError):
        return "connection", reason.errno in {
            errno.ECONNRESET, errno.ECONNREFUSED, errno.ECONNABORTED,
            errno.ENETUNREACH, errno.EHOSTUNREACH, errno.ETIMEDOUT,
        }
    return "connection", False


def http_failure(error):
    code = error.code
    names = {
        400: ("request", "Gemini rejected the analysis request. The app owner should check the model and request settings."),
        401: ("authentication", "Gemini could not authenticate. The app owner should check the API key."),
        402: ("billing", "Gemini billing or credit access needs attention from the app owner."),
        403: ("access", "Gemini access was denied. The app owner should check the key and project access."),
        404: ("model", "This Gemini model is unavailable. The app owner should check GEMINI_MODEL."),
        429: ("quota", "Gemini's request or free-tier quota limit was reached. Check AI Studio usage and try again when your quota is available."),
        408: ("http_408", "Gemini did not finish the request in time. Try analysis again later."),
        500: ("http_500", "Gemini reported a temporary server error. Try analysis again later."),
        502: ("http_502", "Gemini's gateway could not complete the request. Try analysis again later."),
        503: ("http_503", "Gemini is temporarily busy or unavailable. Try analysis again later."),
        504: ("http_504", "Gemini's gateway timed out. Try analysis again later."),
    }
    kind, message = names.get(code, (f"http_{code}", "Gemini could not complete the request. The app owner can check the diagnostic code."))
    retry = code in {408, 500, 502, 503, 504}
    wait = None
    if code == 429:
        # Retry a short, explicitly signaled rate limit. Unknown/daily quota is not retried.
        try:
            payload = json.loads(error.read(65536))
            problem = payload.get("error", {})
            provider_message = str(problem.get("message", "")).lower()
            blocked = any(s in provider_message for s in
                          ("per day", "per_day", "perday", "daily", "billing", "credit", "spend", "limit: 0"))
            retry_after = error.headers.get("Retry-After") if error.headers else None
            if retry_after is not None and not blocked:
                wait = float(retry_after)
                retry = 0 <= wait <= 4
                if retry:
                    kind, message = "rate_limit", "Gemini's short-term request limit was reached. Wait briefly before trying analysis again."
        except (ValueError, TypeError, AttributeError, OSError):
            retry = False
    elif error.headers:
        # Respect an advertised delay; stop instead of retrying sooner than requested.
        header = error.headers.get("Retry-After")
        if header is not None:
            try:
                wait = float(header)
                retry = retry and 0 <= wait <= 4
            except (TypeError, ValueError):
                retry = False
    error.close()
    return kind, message, retry, wait


def request_json(request, progress=None, max_attempts=3, budget_seconds=75):
    """At most three attempts, with a shared time budget and short backoff."""
    deadline = time.monotonic() + budget_seconds
    for attempt in range(1, max_attempts + 1):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise GeminiRequestError("The app server reached its analysis time limit. Try analysis again later.", "time_budget", attempt - 1)
        wait = None
        try:
            with urllib.request.urlopen(request, timeout=min(30, remaining)) as response:
                raw = response.read(2 * 1024 * 1024 + 1)
                if len(raw) > 2 * 1024 * 1024:
                    raise GeminiRequestError("Gemini returned an unexpectedly large response.", "response_size", attempt)
                return json.loads(raw)
        except urllib.error.HTTPError as error:
            kind, message, retry, wait = http_failure(error)
        except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException) as error:
            kind, retry = transport_kind(error)
            message = {
                "timeout": "The app server timed out waiting for Gemini. Try analysis again later.",
                "dns": "The app server could not resolve Gemini's address. Try again later; persistent failures need a hosting check.",
                "tls_certificate": "The app server could not verify Gemini's secure connection. The app owner should check hosting certificates.",
                "tls": "The app server could not establish Gemini's secure connection. The app owner should check hosting connectivity.",
                "connection": "The app server could not connect to Gemini. Try analysis again later.",
            }[kind]
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise GeminiRequestError("Gemini returned an unreadable response. Try analysis again.", "unreadable_response", attempt) from None
        if not retry or attempt == max_attempts:
            raise GeminiRequestError(message, kind, attempt) from None
        delay = max(wait or 0, 2 ** (attempt - 1) + random.uniform(0, .25))
        if delay >= deadline - time.monotonic():
            raise GeminiRequestError(message, kind, attempt) from None
        logging.getLogger(__name__).info("Gemini retry: kind=%s completed_attempts=%d", kind, attempt)
        if progress:
            progress(f"Retrying meal analysis: attempt {attempt + 1} of {max_attempts}…")
        time.sleep(delay)


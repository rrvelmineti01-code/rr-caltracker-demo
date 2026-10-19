"""Explicit Gemini scope for the pre-existing Gemini-only fixtures."""
import os
import unittest
from unittest.mock import patch
import app


def use_gemini():
    unittest.enterModuleContext(patch.dict(os.environ, {"RR_VISION_PROVIDER": "gemini"}))
    unittest.enterModuleContext(patch.object(app, "VISION_PROVIDER", "gemini"))
    unittest.enterModuleContext(patch.object(app, "MAX_MEAL_PHOTOS", 5))

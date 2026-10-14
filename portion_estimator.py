"""Experimental total-dish regression with explicit visual component allocation.

Only the compiled model session is reused. Each call runs fresh inference.
Images and predictions are never written to disk or looked up from a cache.
"""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import io
import math
from pathlib import Path

import numpy as np
from PIL import Image

MODEL_SHA256 = "ac53c053ee61861d58e74251ad582ccb8bd231ce26ff829a7e5e06e71057bdbd"
MODEL_PATH = Path(__file__).with_name("models") / "foodcnn_weight.onnx"


class PortionError(ValueError):
    pass


@dataclass(frozen=True)
class PortionEstimate:
    grams: float
    method: str = "FoodCNN DeepWeightCNN whole-dish regression"


@lru_cache(maxsize=1)
def model_session():
    try:
        import onnxruntime as ort
    except ImportError:
        raise PortionError("The portion model is not installed. Upload the new requirements.txt and reboot the app.") from None
    try:
        raw = MODEL_PATH.read_bytes()
    except OSError:
        raise PortionError("The portion model file is missing. Upload models/foodcnn_weight.onnx and reboot the app.") from None
    if hashlib.sha256(raw).hexdigest() != MODEL_SHA256:
        raise PortionError("The portion model file does not match this release. Upload the supplied model file again.")
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    try:
        return ort.InferenceSession(raw, sess_options=options, providers=["CPUExecutionProvider"])
    except Exception:
        raise PortionError("The app could not load the portion model. The owner should check the installation.") from None


def image_tensor(raw):
    # Match the published weight branch: Pillow bilinear resize; RGB floats [0, 1].
    with Image.open(io.BytesIO(raw)) as image:
        image = image.convert("RGB").resize((224, 224), Image.Resampling.BILINEAR)
        pixels = np.asarray(image, dtype=np.float32) / np.float32(255)
    return np.ascontiguousarray(pixels.transpose(2, 0, 1)[None])


def predict_mass(raw):
    session = model_session()
    try:
        grams = float(session.run(["mass_g"], {"image": image_tensor(raw)})[0].item())
    except Exception:
        raise PortionError("The portion model could not analyze this photo. Try a clear overhead photo of the whole plate.") from None
    if not math.isfinite(grams) or not 1 <= grams <= 5000:
        raise PortionError("The portion model returned an unusable weight. Review this meal using visual portions instead.")
    return PortionEstimate(grams)


def allocate_mass(weights, total):
    """Preserve visual shares; do not pretend the regression measures each ingredient."""
    if not weights:
        return []
    if not math.isfinite(total) or not len(weights) <= total <= 5000:
        raise PortionError("The two portion estimates cannot be combined safely. Review visual portions instead.")
    if any(not math.isfinite(w) or w <= 0 for w in weights):
        raise PortionError("The food split is incomplete. Review visual portions instead.")
    result = [0.] * len(weights)
    active = list(range(len(weights)))
    remaining = total
    while active:
        denominator = sum(weights[i] for i in active)
        small = [i for i in active if remaining * weights[i] / denominator < 1]
        if not small:
            for i in active:
                result[i] = remaining * weights[i] / denominator
            break
        for i in small:
            result[i] = 1.
            remaining -= 1
            active.remove(i)
    return result


def apply_portions(meal, estimate):
    original = [food.grams for food in meal.foods]
    allocated = allocate_mass(original, estimate.grams)
    foods = []
    for food, grams in zip(meal.foods, allocated):
        data = food.model_dump()
        data.update(grams=grams, grams_low=None, grams_high=None,
                    portion_notes="Estimated share of the model's total meal weight. Review this food's portion; it was not weighed individually.")
        foods.append(type(food).model_validate(data))
    data = meal.model_dump()
    data["foods"] = [food.model_dump() for food in foods]
    changed = type(meal).model_validate(data)
    original_total = sum(original)
    discrepancy = abs(estimate.grams - original_total) / original_total if original_total else 0
    return changed, {
        "model": estimate.method, "total_g": estimate.grams,
        "visual_total_g": original_total, "disagreement": discrepancy,
        "component_method": "visual shares normalized to whole-dish model weight",
        "validated_accuracy": False,
    }

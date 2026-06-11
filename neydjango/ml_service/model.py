"""
ml_service/model.py

Loads and manages the PlantVillage disease detection model.

Model: linkanjarad/mobilenet_V2_1.0_224-plant-disease-identification
  - Fine-tuned MobileNetV2 on PlantVillage dataset
  - 38 classes covering tomato, pepper, potato, grape, cucumber diseases
  - ~14MB — lightweight, loads fast on CPU
  - HuggingFace: https://huggingface.co/linkanjarad/mobilenet_V2_1.0_224-plant-disease-identification

The model is loaded once at startup and reused for all requests.
Inference runs on CPU — GPU not required for localhost dev.
"""

import logging
from functools import lru_cache
from io import BytesIO

import torch
from PIL import Image
from transformers import AutoFeatureExtractor, AutoModelForImageClassification

logger = logging.getLogger(__name__)

MODEL_NAME = "linkanjarad/mobilenet_V2_1.0_224-plant-disease-identification"
MODEL_VERSION = "mobilenetv2-plantvillage-v1"


@lru_cache(maxsize=1)
def load_model():
    """
    Load model and feature extractor from HuggingFace.
    Called once at startup; cached for all subsequent requests.
    Downloads ~14MB on first run.
    """
    logger.info(f"Loading model: {MODEL_NAME}")
    extractor = AutoFeatureExtractor.from_pretrained(MODEL_NAME)
    model = AutoModelForImageClassification.from_pretrained(MODEL_NAME)
    model.eval()
    logger.info("Model loaded successfully.")
    return extractor, model


def predict_image(image_bytes: bytes) -> list[dict]:
    """
    Run inference on a single image.

    Args:
        image_bytes: Raw bytes of the uploaded image file.

    Returns:
        List of top-3 predictions, each with:
          - label: PlantVillage class label (e.g. "Tomato___Early_blight")
          - confidence: float 0.0-1.0
    """
    extractor, model = load_model()

    # Open and convert image
    try:
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
    except Exception as e:
        raise ValueError(f"Cannot read image: {e}")

    # Preprocess
    inputs = extractor(images=image, return_tensors="pt")

    # Inference — no gradient needed
    with torch.no_grad():
        outputs = model(**inputs)
        logits = outputs.logits

    # Softmax to get probabilities
    probs = torch.nn.functional.softmax(logits, dim=-1)[0]

    # Top 3 predictions
    top_k = torch.topk(probs, k=3)
    results = []
    for score, idx in zip(top_k.values.tolist(), top_k.indices.tolist()):
        label = model.config.id2label[idx]
        results.append({
            "label": label,
            "confidence": round(score, 4),
        })

    return results

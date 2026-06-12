"""
ml_service/main.py

FastAPI inference service for plant disease detection.
Runs independently on localhost:8001.
Called by Django at POST /api/v1/diagnose/.

Endpoints:
  GET  /health          — liveness check
  GET  /ready           — readiness check (model loaded?)
  POST /predict         — run inference on one or more images

Changelog:
  - Added `disease_label` field to DiagnosisResult response.
    This is the raw PlantVillage label (e.g. "Tomato___Early_blight") which
    Django needs to look up / generate knowledge base entries.
    `disease` remains the human-readable English name.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from model import predict_image, load_model, MODEL_VERSION
from disease_data import get_disease_info

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── Startup: pre-load model ───────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-load the model at startup so first request is fast."""
    logger.info("Pre-loading ML model...")
    load_model()
    logger.info("ML model ready.")
    yield
    logger.info("Shutting down ML service.")


app = FastAPI(
    title="Greenhouse OS — Disease Detection Service",
    description="PlantVillage-based plant disease detection for greenhouse crops.",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Response schemas ──────────────────────────────────────────────────────────

class PesticideRecommendation(BaseModel):
    name: str
    active_ingredient: str
    dose: str


class DiagnosisResult(BaseModel):
    disease_label: str   # Raw PlantVillage label — e.g. "Tomato___Early_blight"
    disease: str         # Human-readable English name
    disease_fa: str      # Human-readable Farsi name
    confidence: float
    cause: str
    remedies: list[str]
    recommended_pesticides: list[PesticideRecommendation]


class PredictResponse(BaseModel):
    diagnoses: list[DiagnosisResult]
    model_version: str
    images_processed: int


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    """Returns 200 if the model is loaded, 503 if not."""
    try:
        load_model()
        return {"status": "ready", "model": MODEL_VERSION}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "error": str(e)}
        )


@app.post("/predict", response_model=PredictResponse)
async def predict(images: list[UploadFile] = File(...)):
    """
    Run disease detection on one or more plant images.

    Accepts: multipart/form-data with field name 'images' (multiple files allowed)
    Returns: top diagnosis per image merged into a deduplicated result list

    The Django service calls this internally — it is not exposed directly
    to end users.
    """
    if not images:
        raise HTTPException(status_code=400, detail="No images provided.")

    if len(images) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 images per request.")

    # Validate file types
    allowed_types = {"image/jpeg", "image/png", "image/webp", "image/jpg"}
    for img in images:
        if img.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {img.content_type}. Use JPEG or PNG."
            )

    # Run inference on each image, collect all predictions
    all_predictions: list[dict] = []

    for img in images:
        image_bytes = await img.read()
        try:
            preds = predict_image(image_bytes)
            all_predictions.extend(preds)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

    # Deduplicate: if same label appears from multiple images, keep highest confidence
    seen: dict[str, float] = {}
    for pred in all_predictions:
        label = pred["label"]
        if label not in seen or pred["confidence"] > seen[label]:
            seen[label] = pred["confidence"]

    # Sort by confidence, take top 3 unique diagnoses
    top_diagnoses = sorted(seen.items(), key=lambda x: x[1], reverse=True)[:3]

    # Build response — disease_label is the raw label, disease is the enriched name
    diagnoses: list[DiagnosisResult] = []
    for label, confidence in top_diagnoses:
        info = get_disease_info(label)
        diagnoses.append(DiagnosisResult(
            disease_label=label,                  # raw: "Tomato___Leaf_Mold"
            disease=info["name_en"],              # human: "Tomato Leaf Mold"
            disease_fa=info["name_fa"],           # farsi: "کپک برگ گوجه‌فرنگی"
            confidence=confidence,
            cause=info["cause"],
            remedies=info["remedies"],
            recommended_pesticides=[
                PesticideRecommendation(**p) for p in info["recommended_pesticides"]
            ],
        ))

    return PredictResponse(
        diagnoses=diagnoses,
        model_version=MODEL_VERSION,
        images_processed=len(images),
    )
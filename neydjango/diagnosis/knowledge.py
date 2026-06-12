"""
diagnosis/knowledge.py

Knowledge base management for disease detection.

This module is the single entry point for getting disease information.
It replaces the static disease_data.py approach with a DB-backed system
that auto-generates entries via OpenAI gpt-4o-mini for unknown labels.

Public API:
  get_or_create_knowledge(label, name_en, name_fa) -> DiseaseKnowledge
  seed_from_static_data()   -> called once at startup via AppConfig

Flow:
  1. Check DB for existing entry by label
  2. If found → return it (instant, no API call)
  3. If not found → call OpenAI to generate cause/remedies/pesticides
  4. Save to DB with source='openai'
  5. Return the new entry

The OpenAI call happens synchronously (Option A) so the farmer
sees the complete result on first diagnosis.
Subsequent diagnoses of the same disease are instant (DB cache).
"""

import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


# ── OpenAI prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert plant pathologist and agronomist specialising in greenhouse crops in Iran.
You provide accurate, practical disease management advice tailored to the Iranian agricultural market.
You always respond in valid JSON only — no markdown, no explanation, no preamble."""

USER_PROMPT_TEMPLATE = """A greenhouse management system has detected the following plant disease:

Disease label: {label}
Disease name (English): {name_en}

Generate a complete knowledge base entry for this disease. Respond with ONLY this JSON structure:

{{
  "name_en": "Full English name of the disease",
  "name_fa": "Full Farsi name of the disease (Persian script)",
  "cause": "One paragraph explaining what causes this disease — pathogen type, conditions that favour it, how it spreads.",
  "remedies": [
    "Specific action step 1",
    "Specific action step 2",
    "Specific action step 3",
    "Specific action step 4",
    "Specific action step 5"
  ],
  "recommended_pesticides": [
    {{
      "name": "Product name (Farsi name in parentheses if available)",
      "active_ingredient": "Active ingredient name",
      "dose": "Dose per litre of water, e.g. 2 g/L"
    }},
    {{
      "name": "Second product",
      "active_ingredient": "Active ingredient",
      "dose": "Dose"
    }}
  ]
}}

Rules:
- remedies must be 4-6 concrete action steps a greenhouse farmer can take immediately
- recommended_pesticides must list 2-3 products available in Iran
- If this is a healthy plant label (contains "healthy"), set cause to "No disease detected." and use empty arrays for remedies and recommended_pesticides
- name_fa must be in Persian script
- Return ONLY the JSON object, nothing else"""


def _call_openai(label: str, name_en: str) -> dict:
    """
    Call OpenAI gpt-4o-mini to generate a knowledge base entry.
    Returns a dict with name_en, name_fa, cause, remedies, recommended_pesticides.
    Raises ValueError if the API call fails or returns invalid JSON.
    """
    try:
        from openai import OpenAI
    except ImportError:
        raise ValueError(
            "openai package not installed. Run: pip install openai"
        )

    api_key = getattr(settings, 'OPENAI_API_KEY', None)
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY not set in settings.py. "
            "Add: OPENAI_API_KEY = 'sk-...'"
        )

    client = OpenAI(api_key=api_key)

    prompt = USER_PROMPT_TEMPLATE.format(label=label, name_en=name_en)

    logger.info(f"Calling OpenAI for unknown label: {label}")

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,      # low temperature = consistent, factual output
        max_tokens=1000,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"OpenAI returned invalid JSON: {e}\nRaw: {raw[:200]}")

    # Validate required keys
    required = ['name_en', 'name_fa', 'cause', 'remedies', 'recommended_pesticides']
    for key in required:
        if key not in data:
            raise ValueError(f"OpenAI response missing key: {key}")

    logger.info(f"OpenAI generated knowledge for: {label}")
    return data


def get_or_create_knowledge(label: str, name_en: str, name_fa: str = '') -> 'DiseaseKnowledge':
    """
    Main entry point. Returns a DiseaseKnowledge instance for the given label.

    - If an entry exists in DB: returns it immediately (no API call)
    - If not: calls OpenAI, saves to DB, returns new entry

    Args:
        label:   Raw PlantVillage label, e.g. "Tomato___Early_blight"
        name_en: Human-readable English name from the ML service
        name_fa: Human-readable Farsi name from the ML service (optional)

    Returns:
        DiseaseKnowledge instance (always, even if OpenAI fails — uses fallback)
    """
    from .models import DiseaseKnowledge

    # ── 1. Check DB cache ─────────────────────────────────────────────
    try:
        existing = DiseaseKnowledge.objects.get(disease_label=label)
        logger.debug(f"Knowledge cache hit for: {label}")
        return existing
    except DiseaseKnowledge.DoesNotExist:
        pass

    # ── 2. Generate via OpenAI ────────────────────────────────────────
    try:
        data = _call_openai(label, name_en)
        knowledge = DiseaseKnowledge.objects.create(
            disease_label=label,
            name_en=data.get('name_en', name_en),
            name_fa=data.get('name_fa', name_fa),
            cause=data.get('cause', ''),
            remedies=data.get('remedies', []),
            recommended_pesticides=data.get('recommended_pesticides', []),
            source=DiseaseKnowledge.Source.OPENAI,
        )
        logger.info(f"Created knowledge entry via OpenAI for: {label}")
        return knowledge

    except Exception as e:
        logger.error(f"OpenAI knowledge generation failed for {label}: {e}")

    # ── 3. Fallback: save a stub so we don't retry on every request ───
    # The stub shows a helpful message and can be edited later in admin.
    knowledge = DiseaseKnowledge.objects.create(
        disease_label=label,
        name_en=name_en or label.replace('___', ' — ').replace('_', ' '),
        name_fa=name_fa or '',
        cause='Detailed information is being generated. Please check back shortly.',
        remedies=[
            'Consult a plant pathologist or agronomist.',
            'Remove and isolate affected plants.',
            'Monitor surrounding plants closely.',
        ],
        recommended_pesticides=[],
        source=DiseaseKnowledge.Source.OPENAI,
    )
    logger.warning(f"Created fallback knowledge stub for: {label}")
    return knowledge


def update_feedback_counts(label: str, confirmed: bool) -> None:
    """
    Increment confirmed_count or rejected_count on a knowledge entry.
    Called when a farmer submits feedback on a diagnosis result.
    """
    from .models import DiseaseKnowledge
    try:
        knowledge = DiseaseKnowledge.objects.get(disease_label=label)
        if confirmed:
            knowledge.confirmed_count += 1
        else:
            knowledge.rejected_count += 1
        knowledge.save(update_fields=['confirmed_count', 'rejected_count', 'updated_at'])
    except DiseaseKnowledge.DoesNotExist:
        pass


def seed_from_static_data() -> None:
    """
    Seed the knowledge base from disease_data.py on first run.
    Called once from DiagnosisConfig.ready() in apps.py.
    Only creates entries that don't already exist — safe to call repeatedly.
    """
    try:
        # Import here to avoid circular imports at module load time
        import sys
        import os
        # disease_data.py is in ml_service/, not in the Django app
        # We re-define the static data inline here so Django doesn't
        # depend on the ml_service directory being on the Python path.
        from .models import DiseaseKnowledge
        from .static_knowledge import STATIC_KNOWLEDGE
    except ImportError:
        logger.warning("static_knowledge.py not found — skipping seed.")
        return

    created = 0
    for label, data in STATIC_KNOWLEDGE.items():
        _, was_created = DiseaseKnowledge.objects.get_or_create(
            disease_label=label,
            defaults={
                'name_en': data['name_en'],
                'name_fa': data['name_fa'],
                'cause': data['cause'],
                'remedies': data['remedies'],
                'recommended_pesticides': data['recommended_pesticides'],
                'source': DiseaseKnowledge.Source.STATIC,
            }
        )
        if was_created:
            created += 1

    if created:
        logger.info(f"Seeded {created} knowledge entries from static data.")
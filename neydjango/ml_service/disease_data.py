"""
ml_service/disease_data.py

Static knowledge base mapping PlantVillage class labels to:
  - Human-readable disease name (English + Farsi)
  - Cause description
  - Treatment remedies
  - Recommended pesticides available in Iran

PlantVillage label format: "Crop___Disease" (e.g. "Tomato___Early_blight")
Healthy label format:      "Crop___healthy"

This file is the Iranian market localisation layer — the ML model
identifies the disease; this file translates that into actionable
advice with locally available products.
"""

DISEASE_KNOWLEDGE: dict = {
    # ── Tomato ────────────────────────────────────────────────────────
    "Tomato___Bacterial_spot": {
        "name_en": "Tomato Bacterial Spot",
        "name_fa": "لکه باکتریایی گوجه‌فرنگی",
        "cause": "Caused by Xanthomonas bacteria, spread by rain splash and contaminated tools.",
        "remedies": [
            "Remove and destroy infected plant material immediately.",
            "Avoid overhead irrigation; use drip irrigation.",
            "Disinfect tools with 10% bleach solution between uses.",
            "Apply copper-based bactericide at first sign of infection.",
            "Improve air circulation by proper plant spacing.",
        ],
        "recommended_pesticides": [
            {"name": "Kocide 2000 (کوساید 2000)", "active_ingredient": "Copper hydroxide", "dose": "2-3 g/L"},
            {"name": "Bordeaux Mixture (مخلوط بوردو)", "active_ingredient": "Copper sulfate + lime", "dose": "1%"},
            {"name": "Cupravit (کوپراویت)", "active_ingredient": "Copper oxychloride", "dose": "2.5 g/L"},
        ],
    },
    "Tomato___Early_blight": {
        "name_en": "Tomato Early Blight",
        "name_fa": "بلایت اولیه گوجه‌فرنگی",
        "cause": "Caused by Alternaria solani fungus. Favoured by warm, humid conditions and plant stress.",
        "remedies": [
            "Remove lower infected leaves to reduce spread.",
            "Mulch around plants to prevent soil splash.",
            "Water at the base of plants in the morning.",
            "Apply fungicide preventively at 7-10 day intervals.",
            "Ensure adequate potassium fertilisation for plant vigour.",
        ],
        "recommended_pesticides": [
            {"name": "Rovral (روورال)", "active_ingredient": "Iprodione", "dose": "1.5 g/L"},
            {"name": "Score (اسکور)", "active_ingredient": "Difenoconazole", "dose": "0.5 mL/L"},
            {"name": "Dithane M-45 (دیتان M-45)", "active_ingredient": "Mancozeb", "dose": "2.5 g/L"},
        ],
    },
    "Tomato___Late_blight": {
        "name_en": "Tomato Late Blight",
        "name_fa": "بلایت انتهایی گوجه‌فرنگی",
        "cause": "Caused by Phytophthora infestans oomycete. Rapid in cool, wet conditions.",
        "remedies": [
            "Destroy all infected plant debris immediately — do not compost.",
            "Apply fungicide at first sign and repeat every 5-7 days.",
            "Avoid wetting foliage when irrigating.",
            "Improve greenhouse ventilation to reduce humidity.",
            "Use resistant varieties in future plantings.",
        ],
        "recommended_pesticides": [
            {"name": "Ridomil Gold (ریدومیل گلد)", "active_ingredient": "Mefenoxam + Mancozeb", "dose": "2.5 g/L"},
            {"name": "Infinito (اینفینیتو)", "active_ingredient": "Propamocarb + Fluopicolide", "dose": "1.5 mL/L"},
            {"name": "Acrobat MZ (آکروبات MZ)", "active_ingredient": "Dimethomorph + Mancozeb", "dose": "2 g/L"},
        ],
    },
    "Tomato___Leaf_Mold": {
        "name_en": "Tomato Leaf Mold",
        "name_fa": "کپک برگ گوجه‌فرنگی",
        "cause": "Caused by Passalora fulva fungus. Common in greenhouses with high humidity (>85%).",
        "remedies": [
            "Reduce humidity below 85% through ventilation.",
            "Remove and destroy affected leaves.",
            "Space plants adequately for air circulation.",
            "Avoid watering late in the day.",
        ],
        "recommended_pesticides": [
            {"name": "Topsin M (توپسین M)", "active_ingredient": "Thiophanate-methyl", "dose": "1 g/L"},
            {"name": "Bravo (براوو)", "active_ingredient": "Chlorothalonil", "dose": "2 mL/L"},
            {"name": "Switch (سوئیچ)", "active_ingredient": "Cyprodinil + Fludioxonil", "dose": "0.8 g/L"},
        ],
    },
    "Tomato___Septoria_leaf_spot": {
        "name_en": "Tomato Septoria Leaf Spot",
        "name_fa": "لکه برگی سپتوریایی گوجه‌فرنگی",
        "cause": "Caused by Septoria lycopersici fungus. Spreads in wet conditions from soil.",
        "remedies": [
            "Remove infected lower leaves promptly.",
            "Mulch soil to prevent spore splash.",
            "Apply preventive fungicide spray.",
            "Practice crop rotation.",
        ],
        "recommended_pesticides": [
            {"name": "Dithane M-45 (دیتان M-45)", "active_ingredient": "Mancozeb", "dose": "2.5 g/L"},
            {"name": "Daconil (داکونیل)", "active_ingredient": "Chlorothalonil", "dose": "2 mL/L"},
            {"name": "Cabrio Top (کابریو تاپ)", "active_ingredient": "Pyraclostrobin + Metiram", "dose": "1.5 g/L"},
        ],
    },
    "Tomato___Spider_mites Two-spotted_spider_mite": {
        "name_en": "Two-Spotted Spider Mite",
        "name_fa": "کنه دو نقطه‌ای",
        "cause": "Tetranychus urticae mite. Thrives in hot, dry conditions. Causes yellow stippling.",
        "remedies": [
            "Increase humidity — spider mites hate moisture.",
            "Remove heavily infested leaves.",
            "Introduce predatory mites (Phytoseiulus persimilis) for biological control.",
            "Apply miticide spray, covering undersides of leaves.",
        ],
        "recommended_pesticides": [
            {"name": "Vertimec (ورتیمک)", "active_ingredient": "Abamectin", "dose": "0.5 mL/L"},
            {"name": "Nissorum (نیسورام)", "active_ingredient": "Hexythiazox", "dose": "0.5 g/L"},
            {"name": "Apollo (آپولو)", "active_ingredient": "Clofentezine", "dose": "0.5 mL/L"},
        ],
    },
    "Tomato___Target_Spot": {
        "name_en": "Tomato Target Spot",
        "name_fa": "لکه هدف گوجه‌فرنگی",
        "cause": "Caused by Corynespora cassiicola fungus in warm, humid greenhouse conditions.",
        "remedies": [
            "Improve ventilation and reduce leaf wetness.",
            "Remove infected plant material.",
            "Apply fungicide preventively.",
        ],
        "recommended_pesticides": [
            {"name": "Quadris (کوادریس)", "active_ingredient": "Azoxystrobin", "dose": "1 mL/L"},
            {"name": "Rovral (روورال)", "active_ingredient": "Iprodione", "dose": "1.5 g/L"},
        ],
    },
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus": {
        "name_en": "Tomato Yellow Leaf Curl Virus (TYLCV)",
        "name_fa": "ویروس پیچیدگی زرد برگ گوجه‌فرنگی",
        "cause": "Transmitted by whitefly (Bemisia tabaci). No cure; prevention is critical.",
        "remedies": [
            "Remove and destroy infected plants immediately.",
            "Control whitefly population aggressively.",
            "Use reflective mulches to repel whiteflies.",
            "Install fine insect screens on greenhouse vents.",
            "Use TYLCV-resistant varieties in future.",
        ],
        "recommended_pesticides": [
            {"name": "Actara (اکتارا)", "active_ingredient": "Thiamethoxam", "dose": "0.2 g/L"},
            {"name": "Confidor (کانفیدور)", "active_ingredient": "Imidacloprid", "dose": "0.5 mL/L"},
            {"name": "Movento (موونتو)", "active_ingredient": "Spirotetramat", "dose": "0.75 mL/L"},
        ],
    },
    "Tomato___Tomato_mosaic_virus": {
        "name_en": "Tomato Mosaic Virus (ToMV)",
        "name_fa": "ویروس موزاییک گوجه‌فرنگی",
        "cause": "Highly contagious virus spread by contact (hands, tools). No chemical cure.",
        "remedies": [
            "Remove and destroy infected plants.",
            "Wash hands thoroughly before handling plants.",
            "Disinfect all tools with 10% bleach or 70% ethanol.",
            "Control aphid vectors.",
            "Use virus-free certified seed.",
        ],
        "recommended_pesticides": [
            {"name": "Pirimor (پیریمور)", "active_ingredient": "Pirimicarb (aphid control)", "dose": "0.5 g/L"},
            {"name": "Actara (اکتارا)", "active_ingredient": "Thiamethoxam (vector control)", "dose": "0.2 g/L"},
        ],
    },
    "Tomato___healthy": {
        "name_en": "Healthy Tomato",
        "name_fa": "گوجه‌فرنگی سالم",
        "cause": "No disease detected.",
        "remedies": [
            "Continue current management practices.",
            "Monitor regularly for early signs of disease.",
            "Maintain optimal temperature (18-25°C) and humidity (60-70%).",
        ],
        "recommended_pesticides": [],
    },

    # ── Pepper ────────────────────────────────────────────────────────
    "Pepper,_bell___Bacterial_spot": {
        "name_en": "Pepper Bacterial Spot",
        "name_fa": "لکه باکتریایی فلفل",
        "cause": "Caused by Xanthomonas bacteria. Spreads in warm, wet conditions.",
        "remedies": [
            "Remove infected leaves and fruit.",
            "Apply copper-based bactericide.",
            "Avoid overhead irrigation.",
            "Disinfect tools between uses.",
        ],
        "recommended_pesticides": [
            {"name": "Kocide 2000 (کوساید 2000)", "active_ingredient": "Copper hydroxide", "dose": "2-3 g/L"},
            {"name": "Cupravit (کوپراویت)", "active_ingredient": "Copper oxychloride", "dose": "2.5 g/L"},
        ],
    },
    "Pepper,_bell___healthy": {
        "name_en": "Healthy Pepper",
        "name_fa": "فلفل سالم",
        "cause": "No disease detected.",
        "remedies": ["Continue current management practices.", "Monitor regularly."],
        "recommended_pesticides": [],
    },

    # ── Cucumber ──────────────────────────────────────────────────────
    "Cucumber___Powdery_mildew": {
        "name_en": "Cucumber Powdery Mildew",
        "name_fa": "سفیدک پودری خیار",
        "cause": "Caused by Podosphaera xanthii or Erysiphe cichoracearum. Common in dry conditions.",
        "remedies": [
            "Improve air circulation.",
            "Avoid excess nitrogen fertilisation.",
            "Remove heavily infected leaves.",
            "Apply sulfur or potassium bicarbonate sprays.",
        ],
        "recommended_pesticides": [
            {"name": "Topsin M (توپسین M)", "active_ingredient": "Thiophanate-methyl", "dose": "1 g/L"},
            {"name": "Nimrod (نیمرود)", "active_ingredient": "Bupirimate", "dose": "0.5 mL/L"},
            {"name": "Sulfur WG (گوگرد WG)", "active_ingredient": "Sulfur", "dose": "3 g/L"},
        ],
    },
    "Cucumber___healthy": {
        "name_en": "Healthy Cucumber",
        "name_fa": "خیار سالم",
        "cause": "No disease detected.",
        "remedies": ["Continue current management practices.", "Monitor regularly."],
        "recommended_pesticides": [],
    },

    # ── Potato ────────────────────────────────────────────────────────
    "Potato___Early_blight": {
        "name_en": "Potato Early Blight",
        "name_fa": "بلایت اولیه سیب‌زمینی",
        "cause": "Caused by Alternaria solani. Common during warm weather with heavy dew.",
        "remedies": [
            "Apply fungicide at first sign.",
            "Remove infected foliage.",
            "Avoid wetting foliage.",
            "Ensure balanced nutrition.",
        ],
        "recommended_pesticides": [
            {"name": "Dithane M-45 (دیتان M-45)", "active_ingredient": "Mancozeb", "dose": "2.5 g/L"},
            {"name": "Score (اسکور)", "active_ingredient": "Difenoconazole", "dose": "0.5 mL/L"},
        ],
    },
    "Potato___Late_blight": {
        "name_en": "Potato Late Blight",
        "name_fa": "بلایت انتهایی سیب‌زمینی",
        "cause": "Caused by Phytophthora infestans. Extremely destructive in cool, wet conditions.",
        "remedies": [
            "Destroy infected plants immediately.",
            "Apply systemic fungicide.",
            "Avoid overhead irrigation.",
            "Ensure good drainage.",
        ],
        "recommended_pesticides": [
            {"name": "Ridomil Gold (ریدومیل گلد)", "active_ingredient": "Mefenoxam + Mancozeb", "dose": "2.5 g/L"},
            {"name": "Infinito (اینفینیتو)", "active_ingredient": "Propamocarb + Fluopicolide", "dose": "1.5 mL/L"},
        ],
    },
    "Potato___healthy": {
        "name_en": "Healthy Potato",
        "name_fa": "سیب‌زمینی سالم",
        "cause": "No disease detected.",
        "remedies": ["Continue current management practices.", "Monitor regularly."],
        "recommended_pesticides": [],
    },

    # ── Grape ─────────────────────────────────────────────────────────
    "Grape___Black_rot": {
        "name_en": "Grape Black Rot",
        "name_fa": "پوسیدگی سیاه انگور",
        "cause": "Caused by Guignardia bidwellii fungus. Spreads in warm, wet weather.",
        "remedies": [
            "Remove and destroy all mummified fruit.",
            "Apply fungicide from bud break.",
            "Prune for good air circulation.",
        ],
        "recommended_pesticides": [
            {"name": "Cabrio Top (کابریو تاپ)", "active_ingredient": "Pyraclostrobin + Metiram", "dose": "1.5 g/L"},
            {"name": "Dithane M-45 (دیتان M-45)", "active_ingredient": "Mancozeb", "dose": "2.5 g/L"},
        ],
    },
    "Grape___healthy": {
        "name_en": "Healthy Grape",
        "name_fa": "انگور سالم",
        "cause": "No disease detected.",
        "remedies": ["Continue current management practices.", "Monitor regularly."],
        "recommended_pesticides": [],
    },
}


def get_disease_info(label: str) -> dict:
    """
    Return disease knowledge for a given PlantVillage label.
    Falls back to a generic unknown entry if label not in database.
    """
    if label in DISEASE_KNOWLEDGE:
        return DISEASE_KNOWLEDGE[label]

    # Graceful fallback for labels not yet in the knowledge base
    crop = label.split("___")[0].replace("_", " ") if "___" in label else "Unknown crop"
    disease = label.split("___")[1].replace("_", " ") if "___" in label else label

    return {
        "name_en": f"{crop} — {disease}",
        "name_fa": f"{disease} در {crop}",
        "cause": "Detailed information not yet available in the knowledge base.",
        "remedies": [
            "Consult a plant pathologist or agronomist.",
            "Remove and isolate affected plants.",
            "Monitor surrounding plants closely.",
        ],
        "recommended_pesticides": [],
    }

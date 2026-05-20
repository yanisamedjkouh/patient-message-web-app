import re
import base64
import hashlib
from pathlib import Path
from html import escape

import streamlit as st
import streamlit.components.v1 as components

try:
    from deep_translator import GoogleTranslator
except ImportError:
    GoogleTranslator = None

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────

st.set_page_config(
    page_title="Patient Message Formatter",
    page_icon="🥼",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────
# LANGUAGE DATA
# ─────────────────────────────────────────────

PATIENT_LANGUAGES = [
    "English",
    "Dutch",
    "French",
    "Romanian",
    "Spanish",
    "Italian",
    "German",
    "Turkish",
]

DOCTOR_MESSAGE_LANGUAGES = ["English", "Turkish"]

LANGUAGE_CODES = {
    "English": "en",
    "Dutch": "nl",
    "French": "fr",
    "Romanian": "ro",
    "Spanish": "es",
    "Italian": "it",
    "German": "de",
    "Turkish": "tr",
}

QUESTION_HEADERS = [
    "personal information", "medical history", "medications and allergies", "patient requirements",
    "informations personnelles", "antécédents médicaux", "médicaments et allergies", "exigences du patient",
    "informatii personale", "informații personale", "istoric medical", "medicamente si alergii", "medicamente și alergii",
    "información personal", "historial médico", "medicamentos y alergias", "requisitos del paciente",
    "informazioni personali", "storia medica", "farmaci e allergie", "richieste del paziente",
    "persönliche informationen", "krankengeschichte", "medikamente und allergien", "patientenwünsche",
    "kişisel bilgiler", "tıbbi geçmiş", "ilaçlar ve alerjiler", "hasta talepleri",
    "persoonlijke informatie", "medische geschiedenis", "medicijnen en allergieën", "patiëntvereisten",
]

QUESTION_KEYWORDS = [
    "full name", "age", "height", "weight", "bmi", "chronic", "disease", "infectious", "infection",
    "surgeries", "surgery", "medications", "medication", "allergies", "allergy", "smoke", "alcohol",
    "patient wants", "patient requirements", "requirements", "procedure", "treatment",
    "nom", "âge", "taille", "poids", "maladie", "infection", "chirurgie", "opération", "médicament", "allergie", "fume", "alcool",
    "nume", "vârstă", "varsta", "înălțime", "inaltime", "greutate", "boală", "boala", "infecție", "infectie", "operație", "operatie", "medicamente", "alergie", "fumez", "alcool",
    "nombre", "edad", "altura", "peso", "enfermedad", "infección", "infeccion", "cirugía", "cirugia", "medicamento", "alergia", "fumar", "alcohol",
    "nome", "età", "eta", "altezza", "peso", "malattia", "infezione", "chirurgia", "intervento", "farmaco", "allergia", "fumo", "alcol",
    "name", "alter", "größe", "grosse", "gewicht", "krankheit", "infektion", "operation", "medikament", "allergie", "rauchen", "alkohol",
    "isim", "ad", "yaş", "yas", "boy", "kilo", "hastalık", "hastalik", "enfeksiyon", "ameliyat", "ilaç", "ilac", "alerji", "sigara", "alkol",
    "naam", "leeftijd", "lengte", "gewicht", "ziekte", "infectie", "operatie", "medicijn", "allergie", "roken", "alcohol",
]

# Field-specific label patterns for smart field mapping
FIELD_LABEL_PATTERNS = {
    "name": [
        r"(?:full\s+)?name", r"naam", r"nom(?:\s+complet)?", r"(?:ad\s+)?soyad", r"nome(?:\s+completo)?",
        r"nombre(?:\s+completo)?", r"name\s*(?:und\s+vorname)?", r"isim", r"ad",
    ],
    "age": [
        r"age", r"âge", r"leeftijd", r"vârst[aă]", r"edad", r"et[àa]", r"alter", r"ya[şs]",
    ],
    "height": [
        r"height", r"tall", r"lengte", r"taille", r"în[aă]l[tț]ime", r"inaltime", r"altura", r"altezza",
        r"gr[öo][sß]e", r"boy",
    ],
    "weight": [
        r"weight", r"gewicht", r"poids", r"greutate", r"peso", r"peso", r"gewicht", r"kilo(?:gram)?",
    ],
    "chronic": [
        r"chronic", r"chronische?", r"chronique", r"cronice?", r"cronica", r"crónica?",
        r"kronik", r"kalıcı", r"süreğen",
    ],
    "infection": [
        r"infect", r"infectious", r"infecti(?:e|ous|on)", r"bula[şs]ıcı",
    ],
    "surgery": [
        r"surger(?:y|ies)", r"operat(?:ion|ed|ie|ies)", r"chirurgi[ae]?", r"ameliyat",
        r"operatie", r"opération",
    ],
    "medication": [
        r"medicat(?:ion|ions)", r"medicijnen?", r"médicaments?", r"medicamente", r"medicamento",
        r"farmac[oi]", r"medikamente?", r"ila[çc]", r"drugs?",
    ],
    "allergy": [
        r"allerg(?:y|ies|ie|ies|en|ia)", r"allergieën", r"allergi(?:e|es|en)", r"alergi(?:i|a)?",
        r"alerg(?:ie|ii)?",
    ],
    "smoke_alcohol": [
        r"smok(?:e|ing)", r"alcohol", r"sigara", r"alkol", r"rauchen", r"fume(?:r|z)?",
        r"tabac", r"roken", r"drink(?:ing)?", r"içki",
    ],
}

# ─── NONE / YES / SMOKE phrases ────────────────────────────────────────────────

NONE_PHRASES = {
    "English": ["no", "none", "nothing", "nope", "nil", "negative", "not any", "no any",
                "no disease", "no diseases", "no infection", "no infections",
                "no allergy", "no allergies", "no medication", "no medications",
                "i don't have", "i dont have", "i don't take", "i dont take",
                "i do not have", "i do not take", "i have no", "i have none"],
    "Dutch": ["nee", "geen", "niets", "niks", "niet van toepassing",
              "ik heb geen", "ik gebruik geen", "ik neem geen",
              "geen ziekten", "geen infecties", "geen allergieën", "geen medicijnen", "geen medicatie"],
    "French": ["non", "aucun", "aucune", "rien", "néant",
               "je n'ai pas", "je nai pas", "je ne prends pas",
               "pas de maladie", "pas d'infection", "pas dinfection",
               "pas d'allergie", "pas dallergie", "pas de médicaments", "pas de medicaments"],
    "Romanian": ["nu", "niciuna", "niciun", "nimic", "nu am", "nu iau",
                 "fără", "fara", "nu am boli", "nu am infecții", "nu am infectii", "nu am alergii"],
    "Spanish": ["no", "ninguno", "ninguna", "nada", "no tengo", "no tomo",
                "sin", "no enfermedades", "no infecciones", "no alergias", "no medicamentos"],
    "Italian": ["no", "nessuno", "nessuna", "niente", "non ho", "non prendo",
                "senza", "nessuna malattia", "nessuna infezione", "nessuna allergia", "nessun farmaco"],
    "German": ["nein", "keine", "keiner", "nichts", "ich habe keine", "ich nehme keine",
               "keine krankheiten", "keine infektionen", "keine allergien", "keine medikamente"],
    "Turkish": ["hayır", "hayir", "yok", "hiç yok", "hic yok", "yoktur",
                "kullanmıyorum", "kullanmiyorum", "almıyorum", "almiyorum",
                "hastalığım yok", "hastalik yok", "enfeksiyon yok",
                "alerji yok", "ilaç kullanmıyorum", "ilac kullanmiyorum",
                "herhangi bir", "bulunmamaktadır"],
}

YES_SURGERY_PHRASES = {
    "English": ["yes", "i had", "had", "before", "surgery", "operation", "operated"],
    "Dutch": ["ja", "ik had", "gehad", "eerder", "operatie", "geopereerd"],
    "French": ["oui", "j'ai eu", "jai eu", "chirurgie", "opération", "operation", "opéré", "operee", "avant"],
    "Romanian": ["da", "am avut", "operație", "operatie", "chirurgie", "operat", "înainte", "inainte"],
    "Spanish": ["sí", "si", "tuve", "cirugía", "cirugia", "operación", "operacion", "operado", "antes"],
    "Italian": ["sì", "si", "ho avuto", "chirurgia", "intervento", "operazione", "operato", "prima"],
    "German": ["ja", "hatte", "operation", "operiert", "chirurgie", "vorher"],
    "Turkish": ["evet", "oldum", "ameliyat", "operasyon", "daha önce", "daha once", "geçirdim", "gecirdim"],
}

SMOKE_WORDS = {
    "English": ["smok", "cigarette", "cigaret"],
    "Dutch": ["rook", "roken", "sigaret", "tabak"],
    "French": ["fume", "fumer", "cigarette", "tabac"],
    "Romanian": ["fumez", "fumat", "țigări", "tigari", "țigară", "tigara"],
    "Spanish": ["fum", "cigarrillo", "tabaco"],
    "Italian": ["fum", "sigarett", "tabacco"],
    "German": ["rauche", "rauchen", "zigarette"],
    "Turkish": ["sigara"],
}

ALCOHOL_WORDS = {
    "English": ["alcohol", "drink", "wine", "beer", "spirits"],
    "Dutch": ["alcohol", "drinken", "wijn", "bier"],
    "French": ["alcool", "bois", "boire", "vin", "bière"],
    "Romanian": ["alcool", "beau", "băut", "baut", "vin", "bere"],
    "Spanish": ["alcohol", "bebo", "beber", "vino", "cerveza"],
    "Italian": ["alcol", "alcool", "bevo", "bere", "vino", "birra"],
    "German": ["alkohol", "trinke", "trinken", "wein", "bier"],
    "Turkish": ["alkol", "içki", "şarap", "sarap", "bira"],
}

OCCASIONAL_WORDS = {
    "English": ["sometimes", "occasionally", "social", "socially", "rarely", "once in a while", "moderate"],
    "Dutch": ["soms", "af en toe", "zelden", "occasioneel", "sociaal"],
    "French": ["parfois", "occasionnellement", "socialement", "rarement", "de temps en temps"],
    "Romanian": ["uneori", "ocazional", "social", "rar"],
    "Spanish": ["a veces", "ocasionalmente", "socialmente", "rara vez"],
    "Italian": ["a volte", "occasionalmente", "socialmente", "raramente"],
    "German": ["manchmal", "gelegentlich", "sozial", "selten"],
    "Turkish": ["bazen", "ara sıra", "ara sira", "nadiren", "sosyal olarak", "arada sırada"],
}

LABELS = {
    "English": {
        "requirements": "PATIENT REQUIREMENTS",
        "patient_wants": "Patient wants",
        "personal": "PERSONAL INFORMATION",
        "full_name": "Full Name",
        "age": "Age",
        "height": "Height",
        "weight": "Weight",
        "bmi": "BMI",
        "medical": "MEDICAL HISTORY",
        "chronic": "Chronic diseases",
        "infectious": "Infectious diseases",
        "surgery": "Previous surgeries",
        "med_allergy": "MEDICATIONS AND ALLERGIES",
        "medication": "Medications",
        "allergy": "Allergies",
        "smoke_alcohol": "Smoke / Alcohol",
        "none": "None",
        "yes_star": "Yes *",
        "occasionally": "Occasionally",
        "occasionally_smokes": "Occasionally smokes",
        "occasionally_drinks": "Occasionally drinks alcohol",
        "occasionally_smokes_drinks": "Occasionally smokes and drinks alcohol",
        "yo": "yo",
    },
    "Turkish": {
        "requirements": "HASTA TALEPLERİ",
        "patient_wants": "Hasta istiyor",
        "personal": "KİŞİSEL BİLGİLER",
        "full_name": "Ad Soyad",
        "age": "Yaş",
        "height": "Boy",
        "weight": "Kilo",
        "bmi": "BMI",
        "medical": "TIBBİ GEÇMİŞ",
        "chronic": "Kronik hastalık",
        "infectious": "Bulaşıcı hastalık",
        "surgery": "Geçirilmiş ameliyat",
        "med_allergy": "İLAÇLAR & ALERJİLER",
        "medication": "İlaçlar",
        "allergy": "Alerji",
        "smoke_alcohol": "Sigara / Alkol",
        "none": "Yok",
        "yes_star": "Evet *",
        "occasionally": "Ara sıra",
        "occasionally_smokes": "Ara sıra sigara kullanıyor",
        "occasionally_drinks": "Ara sıra alkol kullanıyor",
        "occasionally_smokes_drinks": "Ara sıra sigara ve alkol kullanıyor",
        "yo": "Yaş",
    },
}

# ─────────────────────────────────────────────
# TEXT UTILITIES
# ─────────────────────────────────────────────

def clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", str(line).strip())


def normalize_text(text: str) -> str:
    text = str(text).replace("\r", "\n")
    # Smart quotes → straight
    text = text.replace("\u2019", "'").replace("\u2018", "'").replace("`", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    # "sm" unit → "cm" (with word boundary so "some" is unaffected)
    text = re.sub(r"(?<=\d)\s*\bsm\b", " cm", text, flags=re.IGNORECASE)
    return text.strip()


def strip_leading_number(text: str) -> str:
    return re.sub(r"^\s*\d+\s*[\.)\-]\s*", "", text).strip()


def word_in_text(word: str, text: str) -> bool:
    pattern = r"(?<![a-zA-ZÀ-ÿ])" + re.escape(word) + r"(?![a-zA-ZÀ-ÿ])"
    return bool(re.search(pattern, text, flags=re.IGNORECASE))


def any_word_in_text(words: list, text: str) -> bool:
    return any(word_in_text(w, text) for w in words)


def substr_in_text(substring: str, text: str) -> bool:
    return substring.lower() in text.lower()


# ─────────────────────────────────────────────
# LINE EXTRACTION & PARSING
# ─────────────────────────────────────────────

def get_answer_lines(text: str) -> list:
    text = normalize_text(text)
    raw_lines = [clean_line(line) for line in text.split("\n")]
    lines = []

    for line in raw_lines:
        if not line:
            continue

        lower = line.lower().strip()

        if lower.strip("*: -–—") in QUESTION_HEADERS:
            continue

        if re.match(r"^\d+\s*[\.)\-]\s*", lower):
            after = re.sub(r"^\d+\s*[\.)\-]\s*", "", lower).strip()
            if any(kw in after for kw in QUESTION_KEYWORDS) and (after.endswith(":") or not after):
                continue

        if lower.startswith("(") and lower.endswith(")"):
            continue

        if ":" in line:
            before, after = line.split(":", 1)
            before_lower = before.lower().strip()
            if any(kw in before_lower for kw in QUESTION_KEYWORDS):
                line = clean_line(after)
                if not line:
                    continue

        lines.append(line)

    return lines


def try_label_field_extract(text: str) -> dict:
    found = {}
    text = normalize_text(text)

    for field, patterns in FIELD_LABEL_PATTERNS.items():
        for pattern in patterns:
            m = re.search(
                r"(?:^|\n)\s*(?:\d+\s*[\.)\-]\s*)?" + pattern + r"\s*[:\-–—]\s*(.+?)(?=\n|$)",
                text,
                flags=re.IGNORECASE | re.MULTILINE,
            )
            if m:
                value = clean_line(m.group(1))
                value = strip_leading_number(value)
                if value:
                    found[field] = value
                    break

    return found


# ─────────────────────────────────────────────
# EXTRACTION: NAME
# ─────────────────────────────────────────────

_NAME_SKIP_WORDS = {
    "yes", "no", "none", "sometimes", "occasionally", "cm", "kg", "lb", "lbs",
    "years", "old", "yo", "oui", "non", "aucun", "aucune", "parfois",
    "da", "nu", "sí", "si", "sì", "ja", "nein", "hayır", "hayir",
    "yok", "evet", "nee", "geen", "chronic", "disease", "infection",
    "surgery", "medication", "allergy", "smoke", "alcohol",
}

def extract_name(lines: list) -> str:
    for line in lines:
        candidate = strip_leading_number(line)
        candidate = clean_line(candidate)

        if not candidate:
            continue

        lower = candidate.lower()

        if not re.search(r"[^\W\d]", candidate, re.UNICODE):
            continue

        if re.match(r"^\d[\d\s\.,ckmgftin\'\"]*$", lower):
            continue

        if any(word_in_text(skip, lower) for skip in _NAME_SKIP_WORDS):
            continue

        medical_triggers = [
            "disease", "infection", "surgery", "medication", "allergy",
            "smoke", "alcohol", "chronic", "kg", " cm", "bmi",
        ]
        if any(t in lower for t in medical_triggers):
            continue

        tokens = candidate.split()
        if 1 <= len(tokens) <= 5:
            if all(re.match(r"^[^\W\d]", t, re.UNICODE) for t in tokens):
                return candidate

    return lines[0] if lines else ""


# ─────────────────────────────────────────────
# MEASUREMENT CONVERSION UTILITIES
# ─────────────────────────────────────────────

def stones_lbs_to_kg(stones: float, lbs: float = 0) -> int:
    """Convert stones (and optional extra lbs) to kg."""
    total_lbs = stones * 14 + lbs
    return round(total_lbs * 0.453592)


def lbs_to_kg(lbs: float) -> int:
    return round(lbs * 0.453592)


def feet_inches_to_cm(feet: float, inches: float = 0) -> int:
    return round(feet * 30.48 + inches * 2.54)


# ─────────────────────────────────────────────
# EXTRACTION: AGE / HEIGHT / WEIGHT
# ─────────────────────────────────────────────

def extract_age_with_words(text: str) -> str:
    lower = text.lower()

    label_patterns = [
        r"(?:age|âge|vârst[aă]|varsta|edad|et[àa]|alter|ya[şs]|leeftijd)\s*[:\-]?\s*(\d{1,3})",
        r"(\d{1,3})\s*(?:years?\s*old|yo\b|y/o|ans\b|ani\b|años\b|anos\b|anni\b|jahre\b|yaşında|yasinda|jaar\b)",
    ]
    for p in label_patterns:
        m = re.search(p, lower)
        if m:
            age = int(m.group(1))
            if 1 <= age <= 120:
                return str(age)
    return ""


def extract_height_with_units(text: str) -> int | None:
    """
    Extended height extraction supporting:
    - cm / sm / centimeters
    - m (meters) with decimal or separate
    - ft/feet/′ with inches
    - Single feet value (5'10)
    - Written out: "5 feet 7 inches", "5 foot 7"
    """
    lower = text.lower()

    # ── Feet + inches: 5'7", 5′7, 5 ft 7 in, 5 feet 7 inches, 5 foot 7 ──
    # Pattern 1: 5'7" or 5′7 or 5'7
    m = re.search(r"\b([3-8])\s*[\'′']\s*(\d{1,2})\s*(?:\"|''|″|in\.?|inch(?:es)?)?\b", lower)
    if m:
        feet, inches = int(m.group(1)), int(m.group(2))
        if 0 <= inches <= 11:
            return feet_inches_to_cm(feet, inches)

    # Pattern 2: 5 ft 7 in / 5 feet 7 inches / 5 foot 7
    m = re.search(r"\b([3-8])\s*(?:ft\.?|feet|foot)\s*(\d{1,2})\s*(?:in\.?|inch(?:es)?)?\b", lower)
    if m:
        feet, inches = int(m.group(1)), int(m.group(2))
        if 0 <= inches <= 11:
            return feet_inches_to_cm(feet, inches)

    # Pattern 3: only feet, no inches — 5ft, 6 feet
    m = re.search(r"\b([3-8])\s*(?:ft\.?|feet|foot)\b", lower)
    if m:
        feet = int(m.group(1))
        return feet_inches_to_cm(feet, 0)

    # ── Meters ──
    # "1 m 75", "1,75 m", "1.75 m", "175 cm"
    m = re.search(r"\b([12])\s*(?:m|meter|meters|metre|metri|metro|metros)\s*[,\.]?\s*(\d{1,2})\s*(?:cm|sm)?\b", lower)
    if m:
        return int(m.group(1)) * 100 + int(m.group(2))

    m = re.search(r"\b([12])[\.,](\d{2})\s*(?:m|meter|meters|metre|metri|metro|metros)?\b", lower)
    if m:
        return int(m.group(1)) * 100 + int(m.group(2))

    # ── Centimeters ──
    m = re.search(r"\b(1[2-9]\d|2[0-3]\d)\s*(?:cm|sm|centimeters?|centimetres?)\b", lower)
    if m:
        return int(m.group(1))

    return None


def extract_weight_with_units(text: str) -> int | None:
    """
    Extended weight extraction supporting:
    - kg / kilograms
    - lbs / pounds
    - stone / st (UK measurement)
    - stone + lbs (e.g. "12 stone 4", "12 st 4 lbs")
    """
    lower = text.lower()

    # ── Stones + lbs: "12 stone 4", "12 st 4 lbs", "12 st 4lb" ──
    m = re.search(r"\b(\d{1,2})\s*(?:stones?|st\.?)\s*(\d{1,2})\s*(?:lb|lbs|pounds?)?\b", lower)
    if m:
        stones, extra_lbs = int(m.group(1)), int(m.group(2))
        if 3 <= stones <= 50 and 0 <= extra_lbs <= 13:
            result = stones_lbs_to_kg(stones, extra_lbs)
            if 25 <= result <= 300:
                return result

    # ── Stones only: "12 stone", "11 st" ──
    m = re.search(r"\b(\d{1,2})\s*(?:stones?|st\.?)\b", lower)
    if m:
        stones = int(m.group(1))
        if 3 <= stones <= 50:
            result = stones_lbs_to_kg(stones)
            if 25 <= result <= 300:
                return result

    # ── Pounds only: "150 lbs", "150 lb", "150 pounds" ──
    m = re.search(r"\b(\d{2,3}(?:[.,]\d)?)\s*(?:lb|lbs|pounds?)\b", lower)
    if m:
        lbs_val = float(m.group(1).replace(",", "."))
        if 55 <= lbs_val <= 660:
            result = lbs_to_kg(lbs_val)
            if 25 <= result <= 300:
                return result

    # ── Kilograms: "70 kg", "70.5 kg", "70,5 kg" ──
    m = re.search(r"\b(\d{2,3}(?:[.,]\d)?)\s*(?:kg|kgs|kilograms?|kilogramme|kilograme|kilo)\b", lower)
    if m:
        weight = float(m.group(1).replace(",", "."))
        if 25 <= weight <= 300:
            return round(weight)

    return None


def calculate_bmi(height_cm: int | None, weight_kg: int | None) -> str:
    if not height_cm or not weight_kg:
        return ""
    bmi = weight_kg / (height_cm / 100) ** 2
    return str(round(bmi, 1))


def extract_age_height_weight_by_order(lines: list) -> tuple:
    full_text = "\n".join(lines)
    height_cm = extract_height_with_units(full_text)
    weight_kg = extract_weight_with_units(full_text)
    age = extract_age_with_words(full_text)

    name = extract_name(lines)
    name_index = next((idx for idx, line in enumerate(lines) if line == name), None)
    start = 1 if name_index is None else name_index + 1

    numeric_lines = []
    for idx in range(start, len(lines)):
        candidate = strip_leading_number(lines[idx])
        numbers = re.findall(r"\d+(?:[.,]\d+)?", candidate)
        if numbers:
            numeric_lines.append((idx, float(numbers[0].replace(",", ".")), candidate))
        if len(numeric_lines) >= 4:
            break

    if not age and numeric_lines:
        possible_age = numeric_lines[0][1]
        if 1 <= possible_age <= 120:
            age = str(int(possible_age))

    if height_cm is None and len(numeric_lines) >= 2:
        possible_height = numeric_lines[1][1]
        if 120 <= possible_height <= 230:
            height_cm = int(possible_height)
        elif 1.2 <= possible_height <= 2.3:
            height_cm = round(possible_height * 100)

    if weight_kg is None and len(numeric_lines) >= 3:
        possible_weight = numeric_lines[2][1]
        if 25 <= possible_weight <= 300:
            weight_kg = int(possible_weight)

    return age, height_cm, weight_kg


# ─────────────────────────────────────────────
# NONE DETECTION
# ─────────────────────────────────────────────

def words_for(language: str, dictionary: dict) -> list:
    combined = list(dictionary.get(language, []))
    if language != "English":
        combined += dictionary.get("English", [])
    return combined


def _is_none_answer(answer: str, patient_language: str) -> bool:
    text = answer.lower().strip()
    none_phrases = words_for(patient_language, NONE_PHRASES)

    boundary_words = {"no", "none", "nee", "nu", "nein", "non", "yok", "geen", "nada",
                      "nil", "nope", "ja", "si", "da"}

    for phrase in none_phrases:
        if phrase in boundary_words:
            if word_in_text(phrase, text):
                return True
        else:
            if substr_in_text(phrase, text):
                return True

    return False


def _has_exception_clause(answer: str) -> bool:
    exception_words = [
        "but", "except", "only", "however", "although",
        "mais", "sauf", "pero", "ma", "ama", "maar", "behalve",
        "ancak", "fakat", "sadece", "ama",
    ]
    lower = answer.lower()
    return any(word_in_text(w, lower) for w in exception_words)


# ─────────────────────────────────────────────
# TRANSLATION
# ─────────────────────────────────────────────

@st.cache_data(show_spinner=False, ttl=3600)
def online_translate_text(text: str, patient_language: str, doctor_language: str) -> str:
    text = clean_line(text)
    if not text or patient_language == doctor_language or GoogleTranslator is None:
        return text

    source = LANGUAGE_CODES.get(patient_language, "auto")
    target = LANGUAGE_CODES.get(doctor_language, "en")

    try:
        translated = GoogleTranslator(source=source, target=target).translate(text)
        result = clean_line(translated) if translated else text
        result = strip_leading_number(result)
        return result
    except Exception:
        return text


def translate_patient_detail(answer: str, patient_language: str, doctor_language: str) -> str:
    answer = clean_line(answer)
    if not answer:
        return ""
    translated = online_translate_text(answer, patient_language, doctor_language)
    return strip_leading_number(translated)


# ─────────────────────────────────────────────
# NORMALIZE ANSWERS
# ─────────────────────────────────────────────

def translate_basic_answer(token: str, doctor_language: str) -> str:
    labels = LABELS[doctor_language]
    return {
        "__NONE__": labels["none"],
        "__YES_STAR__": labels["yes_star"],
        "__OCCASIONALLY__": labels["occasionally"],
        "__OCC_SMOKE__": labels["occasionally_smokes"],
        "__OCC_DRINK__": labels["occasionally_drinks"],
        "__OCC_BOTH__": labels["occasionally_smokes_drinks"],
    }.get(token, token)


def normalize_answer(answer: str, patient_language: str, doctor_language: str) -> str:
    answer = clean_line(answer)
    if not answer:
        return ""

    if _is_none_answer(answer, patient_language) and not _has_exception_clause(answer):
        return translate_basic_answer("__NONE__", doctor_language)

    return translate_patient_detail(answer, patient_language, doctor_language)


def normalize_surgery(answer: str, patient_language: str, doctor_language: str) -> str:
    answer = clean_line(answer)
    if not answer:
        return ""

    if _is_none_answer(answer, patient_language) and not _has_exception_clause(answer):
        return translate_basic_answer("__NONE__", doctor_language)

    lower = answer.lower()
    yes_indicators = words_for(patient_language, YES_SURGERY_PHRASES)

    if any(word_in_text(w, lower) if len(w) <= 4 else substr_in_text(w, lower) for w in yes_indicators):
        simple_yes = {"yes", "oui", "da", "sí", "si", "sì", "ja", "evet"}
        if lower.strip() in simple_yes:
            return translate_basic_answer("__YES_STAR__", doctor_language)
        translated = online_translate_text(answer, patient_language, doctor_language)
        translated = strip_leading_number(translated)
        return translated + " *" if "*" not in translated else translated

    return translate_patient_detail(answer, patient_language, doctor_language)


def normalize_smoke_alcohol(answer: str, patient_language: str, doctor_language: str) -> str:
    answer = clean_line(answer)
    if not answer:
        return ""

    if _is_none_answer(answer, patient_language) and not _has_exception_clause(answer):
        return translate_basic_answer("__NONE__", doctor_language)

    lower = answer.lower()

    smoke_words = words_for(patient_language, SMOKE_WORDS)
    alcohol_words = words_for(patient_language, ALCOHOL_WORDS)
    occasional_words = words_for(patient_language, OCCASIONAL_WORDS)

    has_smoke = any(substr_in_text(w, lower) for w in smoke_words)
    has_alcohol = any(substr_in_text(w, lower) for w in alcohol_words)
    occasional = any(substr_in_text(w, lower) for w in occasional_words)

    if occasional and not has_smoke and not has_alcohol:
        return translate_basic_answer("__OCCASIONALLY__", doctor_language)

    if occasional and has_smoke and has_alcohol:
        return translate_basic_answer("__OCC_BOTH__", doctor_language)
    if occasional and has_smoke:
        return translate_basic_answer("__OCC_SMOKE__", doctor_language)
    if occasional and has_alcohol:
        return translate_basic_answer("__OCC_DRINK__", doctor_language)

    return translate_patient_detail(answer, patient_language, doctor_language)


# ─────────────────────────────────────────────
# REQUIREMENT EXTRACTION
# ─────────────────────────────────────────────

def extract_patient_requirement_from_text(lines: list) -> str:
    patterns = [
        r"patient\s+wants?\s+(.+)", r"wants?\s+(.+)", r"interested\s+in\s+(.+)",
        r"looking\s+for\s+(.+)", r"procedure\s*[:\-]?\s*(.+)", r"treatment\s*[:\-]?\s*(.+)",
        r"requirement\s*[:\-]?\s*(.+)", r"souhaite\s+(.+)", r"veut\s+(.+)",
        r"dorește\s+(.+)", r"doreste\s+(.+)", r"quiere\s+(.+)", r"desidera\s+(.+)",
        r"möchte\s+(.+)", r"mochte\s+(.+)", r"istiyor\s+(.+)", r"wil\s+(.+)", r"wenst\s+(.+)",
    ]

    for line in lines:
        lower = line.lower()
        for pattern in patterns:
            m = re.search(pattern, lower, flags=re.IGNORECASE)
            if m:
                requirement = clean_line(m.group(1))
                requirement = re.sub(r"^[\(\[]|[\)\]]$", "", requirement).strip()
                if requirement:
                    return requirement
    return ""


def remove_requirement_lines(lines: list) -> list:
    triggers = [
        "patient wants", "interested in", "looking for", "procedure:", "treatment:", "requirement:",
        "souhaite", "dorește", "doreste", "quiere", "desidera", "möchte", "mochte", "istiyor",
        "wil", "wenst",
    ]
    return [line for line in lines if not any(trigger in line.lower() for trigger in triggers)]


def clean_requirement(requirement: str) -> str:
    requirement = clean_line(requirement)
    if not requirement:
        return ""
    requirement = re.sub(r"^patient\s+wants?\s+", "", requirement, flags=re.IGNORECASE).strip(" .")
    return requirement


# ─────────────────────────────────────────────
# FIELD MAPPING
# ─────────────────────────────────────────────

_FIELD_ORDER = ["name", "age", "height", "weight", "chronic", "infection", "surgery", "medication", "allergy", "smoke_alcohol"]


def get_order_based_answers(lines: list, label_extracted: dict) -> dict:
    answers = {
        "name": label_extracted.get("name", ""),
        "chronic": label_extracted.get("chronic", ""),
        "infection": label_extracted.get("infection", ""),
        "surgery": label_extracted.get("surgery", ""),
        "medication": label_extracted.get("medication", ""),
        "allergy": label_extracted.get("allergy", ""),
        "smoke_alcohol": label_extracted.get("smoke_alcohol", ""),
    }

    filled = sum(1 for v in answers.values() if v)
    if filled >= 4:
        return answers

    name = extract_name(lines) if not answers["name"] else answers["name"]
    answers["name"] = name
    remaining = [line for line in lines if line != name]
    personal_numbers, rest = [], []

    for line in remaining:
        candidate = strip_leading_number(line)
        if len(personal_numbers) < 3 and re.search(r"\d", candidate):
            personal_numbers.append(candidate)
        else:
            rest.append(candidate)

    if len(personal_numbers) < 3:
        personal_numbers = [strip_leading_number(l) for l in remaining[:3]]
        rest = [strip_leading_number(l) for l in remaining[3:]]

    fields = ["chronic", "infection", "surgery", "medication", "allergy", "smoke_alcohol"]
    for i, field in enumerate(fields):
        if not answers[field]:
            answers[field] = rest[i] if i < len(rest) else ""

    return answers


# ─────────────────────────────────────────────
# MAIN FORMATTER
# ─────────────────────────────────────────────

def format_patient_message(
    patient_text: str,
    requirement_text: str = "",
    patient_language: str = "English",
    doctor_language: str = "English",
) -> dict | None:

    if doctor_language not in LABELS:
        doctor_language = "English"

    labels = LABELS[doctor_language]
    lines = get_answer_lines(patient_text)

    if not lines:
        return None

    label_extracted = try_label_field_extract(patient_text)

    detected_requirement = extract_patient_requirement_from_text(lines)
    lines = remove_requirement_lines(lines)

    requirement = clean_requirement(requirement_text) or detected_requirement
    requirement = online_translate_text(requirement, patient_language, doctor_language) if requirement else ""
    requirement = strip_leading_number(requirement)

    answers = get_order_based_answers(lines, label_extracted)
    age, height_cm, weight_kg = extract_age_height_weight_by_order(lines)

    if label_extracted.get("age"):
        age = extract_age_with_words(label_extracted["age"]) or age
    if label_extracted.get("height"):
        h = extract_height_with_units(label_extracted["height"])
        if h:
            height_cm = h
    if label_extracted.get("weight"):
        w = extract_weight_with_units(label_extracted["weight"])
        if w:
            weight_kg = w

    bmi = calculate_bmi(height_cm, weight_kg)

    chronic = normalize_answer(answers["chronic"], patient_language, doctor_language)
    infection = normalize_answer(answers["infection"], patient_language, doctor_language)
    surgery = normalize_surgery(answers["surgery"], patient_language, doctor_language)
    medication = normalize_answer(answers["medication"], patient_language, doctor_language)
    allergy = normalize_answer(answers["allergy"], patient_language, doctor_language)
    smoke_alcohol = normalize_smoke_alcohol(answers["smoke_alcohol"], patient_language, doctor_language)

    return {
        "requirements": labels["requirements"],
        "patient_wants": labels["patient_wants"],
        "requirement": requirement if requirement else "—",
        "personal": labels["personal"],
        "full_name": labels["full_name"],
        "full_name_value": answers["name"] or "—",
        "age": labels["age"],
        "age_value": f"{age} {labels['yo']}" if age else "—",
        "height": labels["height"],
        "height_value": f"{height_cm} cm" if height_cm else "—",
        "weight": labels["weight"],
        "weight_value": f"{weight_kg} kg" if weight_kg else "—",
        "bmi": labels["bmi"],
        "bmi_value": bmi if bmi else "—",
        "medical": labels["medical"],
        "chronic": labels["chronic"],
        "chronic_value": chronic or "—",
        "infectious": labels["infectious"],
        "infection_value": infection or "—",
        "surgery": labels["surgery"],
        "surgery_value": surgery or "—",
        "med_allergy": labels["med_allergy"],
        "medication": labels["medication"],
        "medication_value": medication or "—",
        "allergy": labels["allergy"],
        "allergy_value": allergy or "—",
        "smoke_alcohol": labels["smoke_alcohol"],
        "smoke_value": smoke_alcohol or "—",
    }


def data_to_plain_text(data: dict) -> str:
    if data is None:
        return ""

    return (
        f"*{data['requirements']}*\n"
        f"{data['patient_wants']}: {data['requirement']}\n\n"
        f"*{data['personal']}*\n"
        f"1. {data['full_name']}: {data['full_name_value']}\n"
        f"2. {data['age']}: {data['age_value']}\n"
        f"3. {data['height']}: {data['height_value']}\n"
        f"4. {data['weight']}: {data['weight_value']}\n"
        f"5. {data['bmi']}: {data['bmi_value']}\n\n"
        f"*{data['medical']}*\n"
        f"1. {data['chronic']}: {data['chronic_value']}\n"
        f"2. {data['infectious']}: {data['infection_value']}\n"
        f"3. {data['surgery']}: {data['surgery_value']}\n\n"
        f"*{data['med_allergy']}*\n"
        f"1. {data['medication']}: {data['medication_value']}\n"
        f"2. {data['allergy']}: {data['allergy_value']}\n"
        f"3. {data['smoke_alcohol']}: {data['smoke_value']}"
    )


# ─────────────────────────────────────────────
# UI CSS
# ─────────────────────────────────────────────

st.markdown(
    """
<style>
:root {
    --navy-950: #061433;
    --navy-900: #0a1a3f;
    --navy-800: #122657;
    --navy-700: #1f3265;
    --red: #e30613;
    --red-soft: rgba(227, 6, 19, .12);
    --white: #ffffff;
    --soft: #eaf0fb;
    --muted: #a9b7d4;
    --muted-2: #61708f;
    --border: rgba(255,255,255,.13);
    --card: rgba(6, 20, 51, .72);
    --card-solid: #0b1b42;
    --field: rgba(255,255,255,.08);
    --green: #22c55e;
    --orange: #fb923c;
    --violet: #a78bfa;
}

.stApp {
    background:
        radial-gradient(circle at 10% 12%, rgba(227, 6, 19, 0.18), transparent 28%),
        radial-gradient(circle at 88% 0%, rgba(96, 165, 250, 0.18), transparent 24%),
        linear-gradient(135deg, var(--navy-950), var(--navy-900) 42%, #07112b 100%);
    color: var(--white);
}

.block-container {
    padding-top: 0.7rem;
    padding-bottom: 0.7rem;
    max-width: 1420px;
}

[data-testid="stHeader"] { background: transparent; }
[data-testid="stToolbar"] { display: none; }

.hero { display: none; }

.app-title-card {
    position: relative;
    overflow: hidden;
    width: 100%;
    box-sizing: border-box;
    border: 1px solid var(--border);
    border-radius: 24px;
    background: rgba(6, 20, 51, .78);
    box-shadow: 0 16px 44px rgba(0,0,0,.20);
    padding: 12px 16px;
    margin-bottom: 10px;
    backdrop-filter: blur(18px);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
}

.app-title-card::before {
    content: "";
    position: absolute;
    inset: 0;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,.13), transparent);
    transform: translateX(-100%);
    animation: headerFadeScan 5.8s infinite;
    pointer-events: none;
}

@keyframes headerFadeScan {
    0% { transform: translateX(-100%); opacity: 0; }
    15% { opacity: 1; }
    55% { transform: translateX(100%); opacity: 1; }
    70% { opacity: 0; }
    100% { transform: translateX(100%); opacity: 0; }
}

.app-title-card > * { position: relative; z-index: 1; }

.app-title-card h1 {
    margin: 0;
    color: #ffffff;
    font-size: clamp(1.15rem, 2vw, 1.8rem);
    line-height: 1.05;
    letter-spacing: -0.025em;
    text-transform: uppercase;
}

.app-title-card p {
    margin: 4px 0 0 0;
    max-width: 900px;
    color: #c8d4ec;
    font-size: .84rem;
    line-height: 1.35;
}

.app-title-text {
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 16px;
}

.header-logo {
    width: 56px;
    height: 56px;
    border-radius: 15px;
    background: #ffffff;
    border: 1px solid rgba(255,255,255,.18);
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    flex: 0 0 auto;
    box-shadow: 0 10px 26px rgba(0,0,0,.16);
}

.header-logo img {
    width: 100%;
    height: 100%;
    object-fit: contain;
    padding: 8px;
    box-sizing: border-box;
}

.header-copy { min-width: 0; }

.hero-kicker {
    display: inline-flex;
    align-items: center;
    width: fit-content;
    gap: 8px;
    padding: 6px 10px;
    border-radius: 999px;
    border: 1px solid rgba(255,255,255,.22);
    background: rgba(255,255,255,.10);
    color: #dbeafe;
    font-weight: 800;
    font-size: .70rem;
    letter-spacing: .08em;
    text-transform: uppercase;
    backdrop-filter: blur(12px);
}

.hero-kicker span {
    width: 9px;
    height: 9px;
    border-radius: 999px;
    background: var(--red);
    box-shadow: 0 0 0 0 rgba(227,6,19,.65);
    animation: pulse 1.8s infinite;
}

@keyframes pulse {
    70% { box-shadow: 0 0 0 9px rgba(227,6,19,0); }
    100% { box-shadow: 0 0 0 0 rgba(227,6,19,0); }
}

.glass-card {
    border: 1px solid var(--border);
    border-radius: 24px;
    background: var(--card);
    box-shadow: 0 20px 60px rgba(0,0,0,.22);
    padding: 18px;
    margin-bottom: 14px;
    backdrop-filter: blur(18px);
}

.panel-title {
    display: flex;
    align-items: center;
    gap: 10px;
    color: #eef5ff;
    font-weight: 900;
    letter-spacing: .08em;
    font-size: .78rem;
    text-transform: uppercase;
    margin-bottom: 6px;
}

.panel-dot {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    background: var(--red);
    box-shadow: 0 0 14px rgba(227,6,19,.7);
}

.stTextArea textarea, .stTextInput input {
    background: var(--field) !important;
    color: #f8fbff !important;
    border: 1px solid rgba(255,255,255,0.16) !important;
    border-radius: 18px !important;
    box-shadow: inset 0 0 0 1px rgba(255,255,255,.02) !important;
}

.stTextInput input::placeholder, .stTextArea textarea::placeholder {
    color: rgba(233, 240, 255, .48) !important;
}

.stSelectbox div[data-baseweb="select"] > div {
    background: var(--field) !important;
    border-color: rgba(255,255,255,0.16) !important;
    border-radius: 16px !important;
    color: #f8fbff !important;
}

.stButton > button {
    width: 100%;
    border: 1px solid rgba(255,255,255,.14);
    border-radius: 18px;
    padding: .75rem 1rem;
    color: #ffffff;
    font-weight: 900;
    background: linear-gradient(90deg, var(--red), #ff4050);
    box-shadow: 0 12px 30px rgba(227,6,19,.20);
    transition: transform .15s ease, box-shadow .15s ease, filter .15s ease;
}

.stButton > button:hover {
    transform: translateY(-1px);
    filter: brightness(1.05);
    box-shadow: 0 18px 44px rgba(227,6,19,.26);
    color: #ffffff;
}

.result-card {
    border: 1px solid rgba(255,255,255,0.13);
    border-radius: 22px;
    padding: 0;
    background: transparent;
    min-height: 0;
}

.section {
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 20px;
    padding: 14px 16px;
    margin: 0 0 12px 0;
    background: linear-gradient(135deg, rgba(255,255,255,.08), rgba(255,255,255,.035));
}

.section h3 {
    margin: 0 0 12px 0;
    font-size: .82rem;
    text-transform: uppercase;
    letter-spacing: .10em;
}

.req h3 { color: #ff8a93; }
.personal h3 { color: #93c5fd; }
.medical h3 { color: #fdba74; }
.medallergy h3 { color: #c4b5fd; }

.grid-row {
    display: grid;
    grid-template-columns: minmax(130px, 210px) 1fr;
    gap: 12px;
    padding: 8px 0;
    border-top: 1px solid rgba(255,255,255,0.08);
}

.grid-row:first-of-type { border-top: none; }

.label { color: #9fb0d0; font-size: .90rem; }
.value { color: #f8fbff; font-weight: 700; word-break: break-word; }

.metric-strip {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
    margin-bottom: 12px;
}

.metric-card {
    padding: 12px;
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 18px;
    background: rgba(255,255,255,.06);
}

.metric-card span {
    display: block;
    color: #9fb0d0;
    font-size: .72rem;
    text-transform: uppercase;
    letter-spacing: .08em;
}

.metric-card strong {
    display: block;
    color: #ffffff;
    font-size: 1.1rem;
    margin-top: 4px;
}

.info-note {
    color: #b9c6df;
    font-size: .86rem;
    padding: 10px 12px;
    border: 1px solid rgba(255,255,255,.10);
    border-radius: 16px;
    background: rgba(255,255,255,.06);
}

.auto-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: 999px;
    border: 1px solid rgba(52, 211, 153, .35);
    background: rgba(52, 211, 153, .12);
    color: #6ee7b7;
    font-size: .70rem;
    font-weight: 800;
    letter-spacing: .07em;
    text-transform: uppercase;
    margin-bottom: 8px;
}

.auto-badge-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #34d399;
    animation: pulse 1.8s infinite;
}

hr { border-color: rgba(255,255,255,0.10); }

@media (max-width: 900px) {
    .clean-toolbar { grid-template-columns: 1fr; }
    .metric-strip { grid-template-columns: repeat(2, 1fr); }
    .app-title-card { flex-direction: column; align-items: flex-start; }
    .app-title-text { align-items: flex-start; }
    .header-logo { width: 64px; height: 64px; border-radius: 16px; }
}
</style>
""",
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────
# UI HELPERS
# ─────────────────────────────────────────────

def image_to_data_uri(path: str) -> str:
    file_path = Path(path)
    if not file_path.exists():
        return ""
    suffix = file_path.suffix.lower()
    mime = "image/jpeg" if suffix in [".jpg", ".jpeg"] else "image/webp" if suffix == ".webp" else "image/png"
    encoded = base64.b64encode(file_path.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{encoded}"


def find_logo_data_uri() -> str:
    possible_paths = [
        "logo.png", "logo.jpg", "logo.jpeg",
        "app/static/logo.png", "app/static/logo.jpg", "app/static/logo.jpeg",
        "static/logo.png", "static/logo.jpg", "static/logo.jpeg",
    ]
    for path in possible_paths:
        data_uri = image_to_data_uri(path)
        if data_uri:
            return data_uri
    return ""


def render_hero():
    translator_status = "Online translation ready" if GoogleTranslator else "Offline fallback mode"
    logo_uri = find_logo_data_uri()
    logo_html = (
        f'<div class="header-logo"><img src="{logo_uri}" alt="Hospital logo"></div>'
        if logo_uri else '<div class="header-logo"></div>'
    )

    st.markdown(
        f"""
<div class="app-title-card">
  <div class="app-title-text">
    {logo_html}
    <div class="header-copy">
      <h1>Clinical Intake Formatter</h1>
      <p>Paste patient answers — output formats instantly. Supports cm, m, ft/in, lbs, stones · English &amp; Turkish output.</p>
    </div>
  </div>
  <div class="hero-kicker"><span></span>{translator_status}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_result(data):
    if not data:
        st.markdown(
            """
<div class="result-card">
  <div class="info-note">Your doctor message will appear here automatically as you paste patient data.</div>
</div>
""",
            unsafe_allow_html=True,
        )
        return

    plain_text = data_to_plain_text(data)
    message_key = hashlib.md5(plain_text.encode("utf-8")).hexdigest()[:12]
    st.text_area(
        "Doctor message",
        value=plain_text,
        height=320,
        label_visibility="collapsed",
        key=f"doctor_message_text_area_{message_key}",
    )


def copy_button_component(text: str):
    safe = escape(text).replace("\n", "\\n").replace("'", "&#39;")
    components.html(
        f"""
<style>
.copy-btn {{
    width: 100%;
    border: 1px solid rgba(52, 211, 153, .34);
    border-radius: 18px;
    padding: 13px 18px;
    color: #03130a;
    font-weight: 900;
    font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: linear-gradient(90deg, #34d399, #22c55e);
    box-shadow: 0 12px 30px rgba(52, 211, 153, .16);
    cursor: pointer;
}}
.copy-btn:hover {{ filter: brightness(1.05); }}
.msg {{ margin-top: 8px; color: #94a3b8; font-family: Inter, sans-serif; font-size: 13px; }}
</style>
<button class="copy-btn" onclick="copyText()">Copy doctor message</button>
<div id="msg" class="msg"></div>
<script>
function copyText() {{
    const text = `{safe}`;
    navigator.clipboard.writeText(text).then(function() {{
        document.getElementById('msg').innerHTML = 'Copied. Ready to paste.';
    }}, function() {{
        document.getElementById('msg').innerHTML = 'Copy failed. Select the text manually below.';
    }});
}}
</script>
""",
        height=82,
    )


# ─────────────────────────────────────────────
# AUTO-FORMAT CALLBACK
# ─────────────────────────────────────────────

def run_format():
    """Called on_change of the patient text area — auto-formats immediately."""
    text = st.session_state.get("patient_text_input", "")
    req = st.session_state.get("requirement_input", "")
    pat_lang = st.session_state.get("patient_language_select", "English")
    doc_lang = st.session_state.get("doctor_language_select", "English")

    if text.strip():
        data = format_patient_message(text, req, pat_lang, doc_lang)
        st.session_state.generated_data = data
        st.session_state.plain_message = data_to_plain_text(data) if data else ""
    else:
        st.session_state.generated_data = None
        st.session_state.plain_message = ""


# ─────────────────────────────────────────────
# APP LAYOUT
# ─────────────────────────────────────────────

render_hero()

if "generated_data" not in st.session_state:
    st.session_state.generated_data = None
if "plain_message" not in st.session_state:
    st.session_state.plain_message = ""

top_a, top_b, top_c = st.columns([2.2, 1, 1])
with top_a:
    requirement = st.text_input(
        "Patient wants",
        placeholder="breast lift, rhinoplasty, lipoabdominoplasty…",
        key="requirement_input",
        on_change=run_format,
    )
with top_b:
    patient_language = st.selectbox(
        "Patient language",
        PATIENT_LANGUAGES,
        index=0,
        key="patient_language_select",
        on_change=run_format,
    )
with top_c:
    doctor_language = st.selectbox(
        "Doctor message",
        DOCTOR_MESSAGE_LANGUAGES,
        index=0,
        key="doctor_language_select",
        on_change=run_format,
    )

left, right = st.columns([1, 1], gap="large")

with left:
    st.markdown(
        '<div class="panel-title"><span class="panel-dot"></span>Patient answers</div>'
        '<div class="auto-badge"><span class="auto-badge-dot"></span>Auto-formats on paste</div>',
        unsafe_allow_html=True,
    )
    patient_text = st.text_area(
        "Paste raw patient answer",
        value="",
        placeholder="Paste the patient's answers here — output appears instantly…",
        height=320,
        label_visibility="collapsed",
        key="patient_text_input",
        on_change=run_format,
    )

    b1, b2 = st.columns([1.35, 1])
    with b1:
        # Manual trigger still available as fallback
        if st.button("Generate message", type="primary", use_container_width=True):
            run_format()
            st.rerun()
    with b2:
        if st.button("Clear", use_container_width=True):
            st.session_state.generated_data = None
            st.session_state.plain_message = ""
            st.rerun()

    st.markdown(
        """
<div class="info-note">
<strong>Measurements auto-converted:</strong> cm · m · ft/in · lbs · stones+lbs → kg &amp; cm<br>
<strong>Field order (fallback):</strong> name → age → height → weight → chronic → infections → surgeries → medications → allergies → smoke/alcohol
</div>
""",
        unsafe_allow_html=True,
    )

with right:
    st.markdown(
        '<div class="panel-title"><span class="panel-dot" style="background:#34d399; box-shadow:0 0 14px rgba(52,211,153,.8)"></span>Doctor-ready output</div>',
        unsafe_allow_html=True,
    )

    render_result(st.session_state.generated_data)

    if st.session_state.plain_message:
        copy_button_component(st.session_state.plain_message)


st.markdown(
    """
<div style="color:#64748b; font-size:12px; text-align:center; padding:8px 0 4px 0;">
No patient data is stored by this app. Online translation requires internet and may send translated text to a translation service.
</div>
""",
    unsafe_allow_html=True,
)

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
    page_icon="🏥",
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
    "personal", "personal information", "patient information",
    "medical", "medical history",
    "medications", "allergies", "medications allergies", "medications and allergies",
    "patient requirements", "requirements",

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

NONE_PHRASES = {
    "English": [
        "no", "none", "nothing", "nope", "nil", "negative",
        "i don't", "i dont", "do not", "don't", "dont",
        "no any", "not have", "no disease", "no diseases",
        "no infection", "no infections", "no allergy", "no allergies",
        "no medication", "no medications", "i don't have", "i dont have",
        "i don't take", "i dont take", "not taking",
    ],
    "Dutch": [
        "nee", "geen", "niets", "niks", "niet", "ik heb geen",
        "ik gebruik geen", "ik neem geen", "geen ziekten", "geen infecties",
        "geen allergieën", "geen allergieen", "geen medicijnen", "geen medicatie",
    ],
    "French": [
        "non", "aucun", "aucune", "rien", "pas", "je n'ai pas",
        "je nai pas", "je ne prends pas", "pas de maladie", "pas d'infection",
        "pas dinfection", "pas d'allergie", "pas dallergie",
        "pas de médicaments", "pas de medicaments",
    ],
    "Romanian": [
        "nu", "niciuna", "niciun", "nimic", "nu am", "nu iau",
        "fără", "fara", "nu am boli", "nu am infecții",
        "nu am infectii", "nu am alergii",
    ],
    "Spanish": [
        "no", "ninguno", "ninguna", "nada", "no tengo",
        "no tomo", "sin", "no enfermedades", "no infecciones",
        "no alergias", "no medicamentos",
    ],
    "Italian": [
        "no", "nessuno", "nessuna", "niente", "non ho",
        "non prendo", "senza", "nessuna malattia", "nessuna infezione",
        "nessuna allergia", "nessun farmaco",
    ],
    "German": [
        "nein", "keine", "keiner", "nichts", "ich habe keine",
        "ich nehme keine", "keine krankheiten", "keine infektionen",
        "keine allergien", "keine medikamente",
    ],
    "Turkish": [
        "hayır", "hayir", "yok", "hiç", "hic", "yoktur",
        "kullanmıyorum", "kullanmiyorum", "almıyorum", "almiyorum",
        "hastalığım yok", "hastaligim yok", "hastalik yok",
        "enfeksiyon yok", "alerji yok", "ilaç kullanmıyorum",
        "ilac kullanmiyorum",
    ],
}

YES_SURGERY_PHRASES = {
    "English": ["yes", "i had", "had", "before", "surgery", "operation", "operated"],
    "Dutch": ["ja", "ik had", "gehad", "eerder", "operatie", "geopereerd"],
    "French": ["oui", "j'ai eu", "jai eu", "chirurgie", "opération", "operation", "opéré", "operee", "avant"],
    "Romanian": ["da", "am avut", "operație", "operatie", "chirurgie", "operat", "înainte", "inainte"],
    "Spanish": ["sí", "si", "tuve", "cirugía", "cirugia", "operación", "operacion", "operado", "antes"],
    "Italian": ["sì", "si", "ho avuto", "chirurgia", "intervento", "operazione", "operato", "prima"],
    "German": ["ja", "hatte", "operation", "operiert", "chirurgie", "vorher"],
    "Turkish": ["evet", "oldum", "ameliyat", "operasyon", "daha önce", "daha once"],
}

SMOKE_WORDS = {
    "English": ["smoke", "smoking", "cigarette", "cigarettes"],
    "Dutch": ["rook", "roken", "sigaret", "sigaretten", "tabak"],
    "French": ["fume", "fumer", "cigarette", "cigarettes", "tabac"],
    "Romanian": ["fumez", "fumat", "țigări", "tigari", "țigară", "tigara"],
    "Spanish": ["fumo", "fumar", "cigarrillo", "cigarrillos", "tabaco"],
    "Italian": ["fumo", "fumare", "sigaretta", "sigarette", "tabacco"],
    "German": ["rauche", "rauchen", "zigarette", "zigaretten"],
    "Turkish": ["sigara", "içiyorum", "iciyorum", "sigara kullanıyorum", "sigara kullaniyorum"],
}

ALCOHOL_WORDS = {
    "English": ["alcohol", "drink", "drinks", "drinking", "wine", "beer"],
    "Dutch": ["alcohol", "drink", "drinken", "wijn", "bier"],
    "French": ["alcool", "bois", "boire", "vin", "bière", "biere"],
    "Romanian": ["alcool", "beau", "băut", "baut", "vin", "bere"],
    "Spanish": ["alcohol", "bebo", "beber", "vino", "cerveza"],
    "Italian": ["alcol", "alcool", "bevo", "bere", "vino", "birra"],
    "German": ["alkohol", "trinke", "trinken", "wein", "bier"],
    "Turkish": ["alkol", "içki", "icki", "içiyorum", "iciyorum", "şarap", "sarap", "bira"],
}

OCCASIONAL_WORDS = {
    "English": [
        "sometimes", "occasionally", "social", "socially", "rarely",
        "a little", "little bit", "just a little", "from time to time",
    ],
    "Dutch": ["soms", "af en toe", "zelden", "occasioneel", "sociaal", "een beetje"],
    "French": ["parfois", "occasionnellement", "socialement", "rarement", "de temps en temps", "un peu"],
    "Romanian": ["uneori", "ocazional", "social", "rar", "puțin", "putin"],
    "Spanish": ["a veces", "ocasionalmente", "socialmente", "rara vez", "un poco"],
    "Italian": ["a volte", "occasionalmente", "socialmente", "raramente", "un po"],
    "German": ["manchmal", "gelegentlich", "sozial", "selten", "ein bisschen"],
    "Turkish": ["bazen", "ara sıra", "ara sira", "nadiren", "sosyal olarak", "az", "biraz"],
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
        "med_allergy": "MEDICATIONS & ALLERGIES",
        "medication": "Medications",
        "allergy": "Allergies",
        "smoke_alcohol": "Smoke / Alcohol",
        "none": "None",
        "yes_star": "Yes *",
        "occasionally": "Occasionally",
        "occasionally_smokes": "Occasionally smokes",
        "occasionally_drinks": "Occasionally drinks alcohol",
        "occasionally_smokes_drinks": "Occasionally smokes & drinks alcohol",
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
# LOGIC HELPERS
# ─────────────────────────────────────────────

def words_for(language, dictionary):
    combined = list(dictionary.get(language, []))
    if language != "English":
        combined += dictionary.get("English", [])
    return combined


def clean_line(line):
    line = str(line)
    # Remove hidden WhatsApp / copied text characters.
    line = line.replace(chr(8288), "").replace(chr(65279), "").replace(chr(8203), "")
    line = line.replace("⁠", "").replace("﻿", "")
    return re.sub(r"\s+", " ", line.strip())


def strip_answer_numbering(line):
    """
    Supports:
    1 Erald Legisi
    2 26
    3 183
    4 80kg
    1. No
    2) No

    Avoids breaking height formats like: 1 m 76 cm.
    """
    line = clean_line(line)

    # Clear list markers: 1. / 1) / 1-
    line = re.sub(r"^\s*\d{1,2}\s*[\.)\-]\s*", "", line).strip()

    # Bare list numbering: 1 Name / 2 26 / 3 183 / 4 80kg
    match = re.match(r"^(\d{1,2})\s+(.+)$", line)
    if match:
        number = int(match.group(1))
        rest = match.group(2).strip()
        # Do not turn "1 m 76 cm" into "m 76 cm".
        if 1 <= number <= 10 and not re.match(r"^(m|meter|meters|metre|metri|metro|metros)\b", rest.lower()):
            return rest

    return line


def normalize_text(text):
    text = str(text).replace("\r", "\n")
    text = text.replace("\u2019", "'").replace("\u2018", "'").replace("`", "'")
    # Common typo from some patients: 176 sm / 1 m 76 sm -> cm.
    # This does not touch "smoke".
    text = re.sub(r"(?<=\d)\s*sm\b", " cm", text, flags=re.IGNORECASE)
    return text.strip()


def get_answer_lines(text):
    text = normalize_text(text)
    raw_lines = [clean_line(line) for line in text.split("\n")]
    lines = []

    for raw_line in raw_lines:
        if not raw_line:
            continue

        line = strip_answer_numbering(raw_line)
        if not line:
            continue

        lower = line.lower().strip()
        header_key = lower.strip("*:：- ")

        # Remove section headers like Medical / Medications Allergies.
        if header_key in QUESTION_HEADERS:
            continue

        # Remove explanatory lines from pasted questionnaires.
        if lower.startswith("(") and lower.endswith(")"):
            continue

        # If "Full Name: Erald Legisi", keep only the answer.
        if ":" in line:
            before, after = line.split(":", 1)
            if any(keyword in before.lower() for keyword in QUESTION_KEYWORDS):
                line = clean_line(after)
                if not line:
                    continue

        lowered = line.lower().strip()

        # Skip lines that are clearly copied question labels.
        if any(keyword in lowered for keyword in QUESTION_KEYWORDS) and (lowered.endswith(":") or "?" in lowered):
            continue

        lines.append(line)

    return lines


def extract_patient_requirement_from_text(lines):
    patterns = [
        r"patient\s+wants?\s+(.+)", r"wants?\s+(.+)", r"interested\s+in\s+(.+)",
        r"looking\s+for\s+(.+)", r"procedure\s*[:\-]?\s*(.+)", r"treatment\s*[:\-]?\s*(.+)",
        r"requirement\s*[:\-]?\s*(.+)", r"souhaite\s+(.+)", r"veut\s+(.+)",
        r"dorește\s+(.+)", r"doreste\s+(.+)", r"quiere\s+(.+)", r"desidera\s+(.+)",
        r"möchte\s+(.+)", r"mochte\s+(.+)", r"istiyor\s+(.+)", r"wil\s+(.+)", r"wenst\s+(.+)", r"zoekt\s+(.+)",
    ]

    for line in lines:
        lower = line.lower()
        for pattern in patterns:
            match = re.search(pattern, lower, flags=re.IGNORECASE)
            if match:
                requirement = clean_line(match.group(1))
                requirement = re.sub(r"^[\(\[]|[\)\]]$", "", requirement).strip()
                if requirement:
                    return requirement
    return ""


def remove_requirement_lines(lines):
    triggers = [
        "patient wants", "interested in", "looking for", "procedure:", "treatment:", "requirement:",
        "souhaite", "dorește", "doreste", "quiere", "desidera", "möchte", "mochte", "istiyor",
        "wil", "wenst", "zoekt",
    ]
    return [line for line in lines if not any(trigger in line.lower() for trigger in triggers)]


def extract_name(lines):
    """
    The name is usually the first personal-information answer.
    We avoid substring checks like "si" or "ja" because names can contain them.
    """
    exact_non_names = {
        "yes", "no", "none", "sometimes", "occasionally", "rarely",
        "oui", "non", "aucun", "aucune", "parfois",
        "da", "nu", "niciun", "niciuna",
        "sí", "si", "ninguno", "ninguna",
        "sì", "nessuno", "nessuna",
        "ja", "nein", "keine", "geen", "nee",
        "hayır", "hayir", "yok", "evet",
    }

    for line in lines:
        candidate = strip_answer_numbering(line)
        lower = candidate.lower().strip()

        if not candidate:
            continue

        if lower in QUESTION_HEADERS:
            continue

        if lower in exact_non_names:
            continue

        # Skip pure numbers or measurements.
        if re.fullmatch(r"\d{1,3}\s*(cm|kg|kgs|kilo|years?|yo|jaar|ans|anni|jahre|yaş|yas)?", lower):
            continue

        # Skip question labels only when they look like labels/questions.
        if any(keyword in lower for keyword in QUESTION_KEYWORDS) and (":" in lower or "?" in lower):
            continue

        if re.search(r"[a-zA-ZÀ-ÿ]", candidate):
            return candidate

    return lines[0] if lines else ""


def extract_age_with_words(text):
    lower = text.lower()
    patterns = [
        r"(?:age|âge|vârstă|varsta|edad|età|eta|alter|yaş|yas|leeftijd)\s*[:\-]?\s*(\d{1,3})",
        r"(\d{1,3})\s*(?:years?\s*old|yo|y/o|ans|ani|años|anos|anni|jahre|yaşında|yasinda|jaar)",
    ]

    for pattern in patterns:
        match = re.search(pattern, lower)
        if match:
            age = int(match.group(1))
            if 1 <= age <= 120:
                return str(age)
    return ""


def extract_height_with_units(text):
    lower = text.lower()

    match = re.search(r"\b(\d)\s*(?:m|meter|meters|metre|metri|metro|metros)\s*[,\.]?\s*(\d{1,2})\s*(?:cm|sm)?\b", lower)
    if match:
        return int(match.group(1)) * 100 + int(match.group(2))

    match = re.search(r"\b(\d)[\.,](\d{2})\s*(?:m|meter|meters|metre|metri|metro|metros)?\b", lower)
    if match:
        return int(match.group(1)) * 100 + int(match.group(2))

    match = re.search(r"\b(1[2-9]\d|2[0-3]\d)\s*(?:cm|sm)\b", lower)
    if match:
        return int(match.group(1))

    return None


def extract_weight_with_units(text):
    lower = text.lower()
    match = re.search(r"\b(\d{2,3})\s*(?:kg|kgs|kilograms?|kilogramme|kilograme|kilo)\b", lower)
    if match:
        weight = int(match.group(1))
        if 25 <= weight <= 300:
            return weight
    return None


def calculate_bmi(height_cm, weight_kg):
    if not height_cm or not weight_kg:
        return ""
    bmi = weight_kg / (height_cm / 100) ** 2
    return str(round(bmi, 1))


def extract_age_height_weight_by_order(lines):
    full_text = "\n".join(lines)
    height_cm = extract_height_with_units(full_text)
    weight_kg = extract_weight_with_units(full_text)
    age = extract_age_with_words(full_text)

    name = extract_name(lines)
    name_index = next((idx for idx, line in enumerate(lines) if line == name), None)
    start = 1 if name_index is None else name_index + 1

    numeric_lines = []
    for idx in range(start, len(lines)):
        numbers = re.findall(r"\d{1,3}", lines[idx])
        if numbers:
            numeric_lines.append((idx, int(numbers[0]), lines[idx]))
        if len(numeric_lines) >= 3:
            break

    if not age and numeric_lines:
        possible_age = numeric_lines[0][1]
        if 1 <= possible_age <= 120:
            age = str(possible_age)

    if height_cm is None and len(numeric_lines) >= 2:
        possible_height = numeric_lines[1][1]
        if 120 <= possible_height <= 230:
            height_cm = possible_height
        elif 1 <= possible_height <= 2:
            height_cm = possible_height * 100

    if weight_kg is None and len(numeric_lines) >= 3:
        possible_weight = numeric_lines[2][1]
        if 25 <= possible_weight <= 300:
            weight_kg = possible_weight

    return age, height_cm, weight_kg


def translate_basic_answer(value, doctor_language):
    labels = LABELS[doctor_language]
    return {
        "__NONE__": labels["none"],
        "__YES_STAR__": labels["yes_star"],
        "__OCCASIONALLY__": labels["occasionally"],
        "__OCC_SMOKE__": labels["occasionally_smokes"],
        "__OCC_DRINK__": labels["occasionally_drinks"],
        "__OCC_BOTH__": labels["occasionally_smokes_drinks"],
    }.get(value, value)


@st.cache_data(show_spinner=False, ttl=3600)
def online_translate_text(text, patient_language, doctor_language):
    text = clean_line(text)
    if not text or patient_language == doctor_language or GoogleTranslator is None:
        return text

    source = LANGUAGE_CODES.get(patient_language, "auto")
    target = LANGUAGE_CODES.get(doctor_language, "en")

    try:
        translated = GoogleTranslator(source=source, target=target).translate(text)
        return clean_line(translated) if translated else text
    except Exception:
        return text


def translate_patient_detail(answer, patient_language, doctor_language):
    answer = clean_line(answer)
    if not answer:
        return ""
    return online_translate_text(answer, patient_language, doctor_language)


def normalize_answer(answer, patient_language, doctor_language):
    answer = clean_line(answer)
    lower = answer.lower()
    none_phrases = words_for(patient_language, NONE_PHRASES)

    if lower in none_phrases:
        return translate_basic_answer("__NONE__", doctor_language)

    if any(phrase in lower for phrase in none_phrases):
        # Do not erase useful mixed answers like "no allergy but I smoke".
        if not any(word in lower for word in ["but", "except", "only", "smoke", "alcohol", "drink", "mais", "sauf", "pero", "ma", "ama", "maar", "behalve"]):
            return translate_basic_answer("__NONE__", doctor_language)

    return translate_patient_detail(answer, patient_language, doctor_language)


def normalize_surgery(answer, patient_language, doctor_language):
    answer = clean_line(answer)
    lower = answer.lower()

    if normalize_answer(answer, patient_language, doctor_language) == LABELS[doctor_language]["none"]:
        return LABELS[doctor_language]["none"]

    yes_indicators = words_for(patient_language, YES_SURGERY_PHRASES)
    if any(word in lower for word in yes_indicators):
        simple_yes = ["yes", "oui", "da", "sí", "si", "sì", "ja", "evet"]
        if lower in simple_yes:
            return LABELS[doctor_language]["yes_star"]

        translated = online_translate_text(answer, patient_language, doctor_language)
        return translated + " *" if "*" not in translated else translated

    return online_translate_text(answer, patient_language, doctor_language)


def normalize_smoke_alcohol(answer, patient_language, doctor_language):
    answer = clean_line(answer)
    lower = answer.lower()

    if normalize_answer(answer, patient_language, doctor_language) == LABELS[doctor_language]["none"]:
        return LABELS[doctor_language]["none"]

    smoke_words = words_for(patient_language, SMOKE_WORDS)
    alcohol_words = words_for(patient_language, ALCOHOL_WORDS)
    occasional_words = words_for(patient_language, OCCASIONAL_WORDS)

    if lower in occasional_words:
        return LABELS[doctor_language]["occasionally"]

    has_smoke = any(word in lower for word in smoke_words)
    has_alcohol = any(word in lower for word in alcohol_words)
    occasional = any(word in lower for word in occasional_words)

    if occasional and has_smoke and has_alcohol:
        return LABELS[doctor_language]["occasionally_smokes_drinks"]
    if occasional and has_smoke:
        return LABELS[doctor_language]["occasionally_smokes"]
    if occasional and has_alcohol:
        return LABELS[doctor_language]["occasionally_drinks"]

    return translate_patient_detail(answer, patient_language, doctor_language)


def clean_requirement(requirement):
    requirement = clean_line(requirement)
    if not requirement:
        return ""
    requirement = re.sub(r"^patient\s+wants?\s+", "", requirement, flags=re.IGNORECASE).strip(" .")
    return requirement


def get_order_based_answers(lines):
    name = extract_name(lines)
    remaining = [line for line in lines if line != name]
    personal_numbers, rest = [], []

    # First collect age, height, weight from the top of the remaining answers.
    for line in remaining:
        if len(personal_numbers) < 3 and re.search(r"\d", line):
            personal_numbers.append(line)
        else:
            rest.append(line)

    # Fallback for very compact formats.
    if len(personal_numbers) < 3:
        personal_numbers, rest = remaining[:3], remaining[3:]

    while len(rest) < 6:
        rest.append("")

    return {
        "name": name,
        "chronic": rest[0] if len(rest) > 0 else "",
        "infection": rest[1] if len(rest) > 1 else "",
        "surgery": rest[2] if len(rest) > 2 else "",
        "medication": rest[3] if len(rest) > 3 else "",
        "allergy": rest[4] if len(rest) > 4 else "",
        "smoke_alcohol": rest[5] if len(rest) > 5 else "",
    }


def format_patient_message(patient_text, requirement_text="", patient_language="English", doctor_language="English"):
    if doctor_language not in LABELS:
        doctor_language = "English"

    labels = LABELS[doctor_language]
    lines = get_answer_lines(patient_text)

    if not lines:
        return None

    detected_requirement = extract_patient_requirement_from_text(lines)
    lines = remove_requirement_lines(lines)

    requirement = clean_requirement(requirement_text) or detected_requirement
    requirement = online_translate_text(requirement, patient_language, doctor_language) if requirement else ""

    answers = get_order_based_answers(lines)
    age, height_cm, weight_kg = extract_age_height_weight_by_order(lines)
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


def data_to_plain_text(data):
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
    --white: #ffffff;
    --border: rgba(255,255,255,.13);
    --card: rgba(6, 20, 51, .72);
    --field: rgba(255,255,255,.08);
}

.stApp {
    background:
        radial-gradient(circle at 10% 12%, rgba(227, 6, 19, 0.18), transparent 28%),
        radial-gradient(circle at 88% 0%, rgba(96, 165, 250, 0.18), transparent 24%),
        linear-gradient(135deg, var(--navy-950), var(--navy-900) 42%, #07112b 100%);
    color: var(--white);
}

.block-container {
    padding-top: 1.1rem;
    padding-bottom: 1.2rem;
    max-width: 1420px;
}

[data-testid="stHeader"] { background: transparent; }
[data-testid="stToolbar"] { display: none; }

.hero,
.hero::before,
.hero::after,
.hero-content,
.hero-bg-img {
    display: none;
}

.hero-kicker {
    display: inline-flex;
    align-items: center;
    width: fit-content;
    gap: 8px;
    padding: 8px 11px;
    border-radius: 999px;
    border: 1px solid rgba(255,255,255,.22);
    background: rgba(255,255,255,.10);
    color: #dbeafe;
    font-weight: 800;
    font-size: .78rem;
    letter-spacing: .09em;
    text-transform: uppercase;
    margin-bottom: 16px;
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

.app-title-card {
    position: relative;
    overflow: hidden;
    width: 100%;
    box-sizing: border-box;
    border: 1px solid var(--border);
    border-radius: 30px;
    background: rgba(6, 20, 51, .78);
    box-shadow: 0 20px 60px rgba(0,0,0,.22);
    padding: 18px 22px;
    margin-bottom: 14px;
    backdrop-filter: blur(18px);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 22px;
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

.app-title-card > * {
    position: relative;
    z-index: 1;
}

.app-title-card h1 {
    margin: 0;
    color: #ffffff;
    font-size: clamp(1.45rem, 2.4vw, 2.4rem);
    line-height: 1.05;
    letter-spacing: -0.035em;
    text-transform: uppercase;
}

.app-title-card p {
    margin: 8px 0 0 0;
    max-width: 900px;
    color: #c8d4ec;
    font-size: .98rem;
    line-height: 1.55;
}

.app-title-text {
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 16px;
}

.header-logo {
    width: 78px;
    height: 78px;
    border-radius: 20px;
    background: #ffffff;
    border: 1px solid rgba(255,255,255,.18);
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    flex: 0 0 auto;
    box-shadow: 0 14px 34px rgba(0,0,0,.18);
}

.header-logo img {
    width: 100%;
    height: 100%;
    object-fit: contain;
    padding: 8px;
    box-sizing: border-box;
}

.header-copy {
    min-width: 0;
}

.panel-title {
    display: flex;
    align-items: center;
    gap: 10px;
    color: #eef5ff;
    font-weight: 900;
    letter-spacing: .08em;
    font-size: .82rem;
    text-transform: uppercase;
    margin-bottom: 10px;
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

.info-note {
    color: #b9c6df;
    font-size: .86rem;
    padding: 10px 12px;
    border: 1px solid rgba(255,255,255,.10);
    border-radius: 16px;
    background: rgba(255,255,255,.06);
}

@media (max-width: 900px) {
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
    if suffix in [".jpg", ".jpeg"]:
        mime = "image/jpeg"
    elif suffix == ".webp":
        mime = "image/webp"
    else:
        mime = "image/png"
    encoded = base64.b64encode(file_path.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{encoded}"


def find_logo_data_uri() -> str:
    possible_paths = [
        "logo.png",
        "logo.jpg",
        "logo.jpeg",
        "app/static/logo.png",
        "app/static/logo.jpg",
        "app/static/logo.jpeg",
        "static/logo.png",
        "static/logo.jpg",
        "static/logo.jpeg",
    ]
    for path in possible_paths:
        data_uri = image_to_data_uri(path)
        if data_uri:
            return data_uri
    return ""


def render_hero():
    translator_status = "Online translation ready" if GoogleTranslator else "Offline fallback mode"
    logo_uri = find_logo_data_uri()
    logo_html = f'<div class="header-logo"><img src="{logo_uri}" alt="Hospital logo"></div>' if logo_uri else '<div class="header-logo"></div>'

    st.markdown(
        f"""
<div class="app-title-card">
  <div class="app-title-text">
    {logo_html}
    <div class="header-copy">
      <h1>Clinical Intake Formatter</h1>
      <p>A simple tool for turning multilingual patient answers into a clean doctor message in <strong>English</strong> or <strong>Turkish</strong>.</p>
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
  <div class="info-note">Your doctor message will appear here after you click <b>Generate message</b>.</div>
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
        height=520,
        label_visibility="collapsed",
        key=f"doctor_message_text_area_{message_key}",
    )


def copy_button_component(text):
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
.msg {{
    margin-top: 8px;
    color: #94a3b8;
    font-family: Inter, sans-serif;
    font-size: 13px;
}}
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
# APP LAYOUT
# ─────────────────────────────────────────────

render_hero()

if "generated_data" not in st.session_state:
    st.session_state.generated_data = None
if "plain_message" not in st.session_state:
    st.session_state.plain_message = ""

top_a, top_b, top_c = st.columns([2.2, 1, 1])
with top_a:
    requirement = st.text_input("Patient wants", placeholder="breast lift, rhinoplasty, lipoabdominoplasty…")
with top_b:
    patient_language = st.selectbox("Patient language", PATIENT_LANGUAGES, index=0)
with top_c:
    doctor_language = st.selectbox("Doctor message", DOCTOR_MESSAGE_LANGUAGES, index=0)

left, right = st.columns([1, 1], gap="large")

with left:
    st.markdown('<div class="panel-title"><span class="panel-dot"></span>Patient answers</div>', unsafe_allow_html=True)
    patient_text = st.text_area(
        "Paste raw patient answer",
        value="",
        placeholder="Paste the patient's answers here...",
        height=460,
        label_visibility="collapsed",
    )

    b1, b2 = st.columns([1.35, 1])
    with b1:
        generate = st.button("Generate message", type="primary", use_container_width=True)
    with b2:
        clear = st.button("Clear", use_container_width=True)

    st.markdown(
        """
<div class="info-note">
The app follows the order: name, age, height, weight, chronic diseases, infections, surgeries, medications, allergies, smoke/alcohol. It also supports numbered answers and section headers like Medical or Medications Allergies.
</div>
""",
        unsafe_allow_html=True,
    )

with right:
    st.markdown('<div class="panel-title"><span class="panel-dot" style="background:#34d399; box-shadow:0 0 14px rgba(52,211,153,.8)"></span>Doctor-ready output</div>', unsafe_allow_html=True)

    if clear:
        st.session_state.generated_data = None
        st.session_state.plain_message = ""
        st.rerun()

    if generate:
        # Always clear the previous output first, then generate the new result.
        st.session_state.generated_data = None
        st.session_state.plain_message = ""

        with st.spinner("Formatting and translating…"):
            data = format_patient_message(patient_text, requirement, patient_language, doctor_language)
            st.session_state.generated_data = data
            st.session_state.plain_message = data_to_plain_text(data) if data else ""

    render_result(st.session_state.generated_data)

    if st.session_state.plain_message:
        copy_button_component(st.session_state.plain_message)

st.markdown(
    """
<div style="color:#64748b; font-size:12px; text-align:center; padding:18px 0 6px 0;">
No patient data is stored by this app. Online translation requires internet and may send translated text to a translation service.
</div>
""",
    unsafe_allow_html=True,
)

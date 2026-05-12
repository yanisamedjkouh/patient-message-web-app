import re
import os
import json
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

try:
    import anthropic as _anthropic_sdk
    _anthropic_available = True
except ImportError:
    _anthropic_available = False

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

PATIENT_LANGUAGES = ["English","Dutch","French","Romanian","Spanish","Italian","German","Turkish"]
DOCTOR_MESSAGE_LANGUAGES = ["English", "Turkish"]

LANGUAGE_CODES = {
    "English":"en","Dutch":"nl","French":"fr","Romanian":"ro",
    "Spanish":"es","Italian":"it","German":"de","Turkish":"tr",
}

LABELS = {
    "English": {
        "requirements":"PATIENT REQUIREMENTS","patient_wants":"Patient wants",
        "personal":"PERSONAL INFORMATION","full_name":"Full Name","age":"Age",
        "height":"Height","weight":"Weight","bmi":"BMI",
        "medical":"MEDICAL HISTORY","chronic":"Chronic diseases",
        "infectious":"Infectious diseases","surgery":"Previous surgeries",
        "med_allergy":"MEDICATIONS AND ALLERGIES","medication":"Medications",
        "allergy":"Allergies","smoke_alcohol":"Smoke / Alcohol",
        "none":"None","yes_star":"Yes *","occasionally":"Occasionally",
        "occasionally_smokes":"Occasionally smokes",
        "occasionally_drinks":"Occasionally drinks alcohol",
        "occasionally_smokes_drinks":"Occasionally smokes & drinks alcohol",
        "yo":"yo",
    },
    "Turkish": {
        "requirements":"HASTA TALEPLERİ","patient_wants":"Hasta istiyor",
        "personal":"KİŞİSEL BİLGİLER","full_name":"Ad Soyad","age":"Yaş",
        "height":"Boy","weight":"Kilo","bmi":"BMI",
        "medical":"TIBBİ GEÇMİŞ","chronic":"Kronik hastalık",
        "infectious":"Bulaşıcı hastalık","surgery":"Geçirilmiş ameliyat",
        "med_allergy":"İLAÇLAR & ALERJİLER","medication":"İlaçlar",
        "allergy":"Alerji","smoke_alcohol":"Sigara / Alkol",
        "none":"Yok","yes_star":"Evet *","occasionally":"Ara sıra",
        "occasionally_smokes":"Ara sıra sigara kullanıyor",
        "occasionally_drinks":"Ara sıra alkol kullanıyor",
        "occasionally_smokes_drinks":"Ara sıra sigara ve alkol kullanıyor",
        "yo":"Yaş",
    },
}

# ─────────────────────────────────────────────
# AI EXTRACTION VIA CLAUDE API
# ─────────────────────────────────────────────

_AI_SYSTEM_PROMPT = """You are a clinical intake data extractor for a medical tourism platform.
Extract patient information from the raw text and return ONLY valid JSON — no markdown, no explanation, no extra text.

Return this exact structure:
{
  "name": "",
  "age": "",
  "height_cm": null,
  "weight_kg": null,
  "chronic_diseases": "",
  "infectious_diseases": "",
  "previous_surgeries": "",
  "medications": "",
  "allergies": "",
  "smoke_alcohol": "",
  "patient_requirement": ""
}

Rules:
- name: full name as written
- age: integer as string e.g. "34"
- height_cm: integer in cm. Convert from ANY unit automatically:
    feet+inches: 5'7" or 5 ft 7 in or 5 feet 7 inches → 170
    feet only: 6 feet → 183
    meters: 1.75 m or 1m75 → 175
    cm: 175 cm → 175
- weight_kg: integer in kg. Convert from ANY unit automatically:
    pounds: 154 lbs → 70
    stones: 11 stone → 70
    stones+lbs: 11 st 4 lb → 72
    kg: 70 kg → 70
- chronic_diseases: "None" if none/no/nothing, else keep original text
- infectious_diseases: "None" if none/no/nothing, else keep original text
- previous_surgeries: "None" if none, "Yes *" if just yes with no detail, else keep details
- medications: "None" if none, else list them
- allergies: "None" if none, else list them
- smoke_alcohol: normalize to one of:
    "None" — neither smokes nor drinks
    "Occasionally smokes" — occasional smoker
    "Occasionally drinks alcohol" — occasional drinker
    "Occasionally smokes & drinks alcohol" — both occasionally
    otherwise describe briefly in English
- patient_requirement: the medical procedure/treatment they want (rhinoplasty, breast lift, etc.)
- If a field is genuinely missing use empty string ""
- NEVER invent data
- Input may be ANY language — extract meaning, keep names/drug names in original form
- All measurements MUST be converted to metric integers"""


def _get_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        env_file = Path(".env")
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if line.startswith("ANTHROPIC_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    return key


@st.cache_data(show_spinner=False, ttl=60)
def ai_extract_fields(patient_text: str, patient_language: str) -> dict | None:
    if not _anthropic_available:
        return None
    api_key = _get_api_key()
    if not api_key:
        return None
    try:
        client = _anthropic_sdk.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            system=_AI_SYSTEM_PROMPT,
            messages=[{"role":"user","content":f"Patient language: {patient_language}\n\nPatient text:\n{patient_text}"}],
        )
        raw = response.content[0].text.strip()
        raw = re.sub(r"^```(?:json)?\s*","",raw)
        raw = re.sub(r"\s*```$","",raw)
        return json.loads(raw)
    except Exception:
        return None


def ai_fields_to_formatted(ai: dict, requirement_override: str, patient_language: str, doctor_language: str) -> dict | None:
    if not ai:
        return None
    labels = LABELS[doctor_language]

    requirement = clean_line(requirement_override) or clean_line(ai.get("patient_requirement",""))
    if requirement and patient_language != doctor_language:
        requirement = online_translate_text(requirement, patient_language, doctor_language)
    requirement = requirement or "—"

    name = clean_line(ai.get("name","")) or "—"
    age_raw = str(ai.get("age","")).strip()
    age_str = f"{age_raw} {labels['yo']}" if age_raw and age_raw.isdigit() else "—"

    try: height_cm = int(ai.get("height_cm")) if ai.get("height_cm") else None
    except (ValueError,TypeError): height_cm = None
    try: weight_kg = int(ai.get("weight_kg")) if ai.get("weight_kg") else None
    except (ValueError,TypeError): weight_kg = None

    height_str = f"{height_cm} cm" if height_cm else "—"
    weight_str = f"{weight_kg} kg" if weight_kg else "—"
    bmi_str = calculate_bmi(height_cm, weight_kg) or "—"

    def prep(field_key: str, is_surgery=False) -> str:
        val = clean_line(ai.get(field_key,""))
        if not val: return "—"
        if val.lower() in ("none","yok","geen","aucun","no","nein","nada","nessuno","keine"):
            return labels["none"]
        if val in ("Yes *","Evet *"):
            return labels["yes_star"]
        if patient_language != doctor_language:
            val = online_translate_text(val, patient_language, doctor_language)
        if is_surgery and val and val not in (labels["none"],labels["yes_star"]) and "*" not in val:
            val = val + " *"
        return val or "—"

    def prep_smoke(field_key: str) -> str:
        val = clean_line(ai.get(field_key,""))
        if not val: return "—"
        low = val.lower()
        smoke_map = {
            "none": labels["none"],
            "occasionally smokes & drinks alcohol": labels["occasionally_smokes_drinks"],
            "occasionally smokes and drinks alcohol": labels["occasionally_smokes_drinks"],
            "occasionally smokes": labels["occasionally_smokes"],
            "occasionally drinks alcohol": labels["occasionally_drinks"],
            "occasionally": labels["occasionally"],
        }
        for k,v in smoke_map.items():
            if k in low: return v
        if patient_language != doctor_language:
            val = online_translate_text(val, patient_language, doctor_language)
        return val or "—"

    return {
        "requirements":labels["requirements"],"patient_wants":labels["patient_wants"],
        "requirement":requirement,"personal":labels["personal"],
        "full_name":labels["full_name"],"full_name_value":name,
        "age":labels["age"],"age_value":age_str,
        "height":labels["height"],"height_value":height_str,
        "weight":labels["weight"],"weight_value":weight_str,
        "bmi":labels["bmi"],"bmi_value":bmi_str,
        "medical":labels["medical"],"chronic":labels["chronic"],
        "chronic_value":prep("chronic_diseases"),
        "infectious":labels["infectious"],"infection_value":prep("infectious_diseases"),
        "surgery":labels["surgery"],"surgery_value":prep("previous_surgeries",is_surgery=True),
        "med_allergy":labels["med_allergy"],"medication":labels["medication"],
        "medication_value":prep("medications"),
        "allergy":labels["allergy"],"allergy_value":prep("allergies"),
        "smoke_alcohol":labels["smoke_alcohol"],"smoke_value":prep_smoke("smoke_alcohol"),
    }


# ─────────────────────────────────────────────
# TEXT UTILITIES
# ─────────────────────────────────────────────

def clean_line(line: str) -> str:
    return re.sub(r"\s+"," ",str(line).strip())

def normalize_text(text: str) -> str:
    text = str(text).replace("\r","\n")
    text = text.replace("\u2019","'").replace("\u2018","'").replace("`","'")
    text = text.replace("\u201c",'"').replace("\u201d",'"')
    text = re.sub(r"(?<=\d)\s*\bsm\b"," cm",text,flags=re.IGNORECASE)
    return text.strip()

def strip_leading_number(text: str) -> str:
    return re.sub(r"^\s*\d+\s*[\.)\-]\s*","",text).strip()

def word_in_text(word: str, text: str) -> bool:
    return bool(re.search(r"(?<![a-zA-ZÀ-ÿ])"+re.escape(word)+r"(?![a-zA-ZÀ-ÿ])",text,flags=re.IGNORECASE))

def substr_in_text(substring: str, text: str) -> bool:
    return substring.lower() in text.lower()

# ─────────────────────────────────────────────
# TRANSLATION
# ─────────────────────────────────────────────

@st.cache_data(show_spinner=False, ttl=3600)
def online_translate_text(text: str, patient_language: str, doctor_language: str) -> str:
    text = clean_line(text)
    if not text or patient_language == doctor_language or GoogleTranslator is None:
        return text
    source = LANGUAGE_CODES.get(patient_language,"auto")
    target = LANGUAGE_CODES.get(doctor_language,"en")
    try:
        translated = GoogleTranslator(source=source,target=target).translate(text)
        return strip_leading_number(clean_line(translated) if translated else text)
    except Exception:
        return text

# ─────────────────────────────────────────────
# MEASUREMENT HELPERS
# ─────────────────────────────────────────────

def feet_inches_to_cm(feet: float, inches: float=0) -> int:
    return round(feet*30.48+inches*2.54)

def stones_lbs_to_kg(stones: float, lbs: float=0) -> int:
    return round((stones*14+lbs)*0.453592)

def extract_height_with_units(text: str) -> int | None:
    lower = text.lower()
    m = re.search(r"\b([3-8])\s*[\'′']\s*(\d{1,2})\s*(?:\"|''|″|in\.?|inch(?:es)?)?\b",lower)
    if m:
        f,i = int(m.group(1)),int(m.group(2))
        if 0<=i<=11: return feet_inches_to_cm(f,i)
    m = re.search(r"\b([3-8])\s*(?:ft\.?|feet|foot)\s*(\d{1,2})\s*(?:in\.?|inch(?:es)?)?\b",lower)
    if m:
        f,i = int(m.group(1)),int(m.group(2))
        if 0<=i<=11: return feet_inches_to_cm(f,i)
    m = re.search(r"\b([3-8])\s*(?:ft\.?|feet|foot)\b",lower)
    if m: return feet_inches_to_cm(int(m.group(1)),0)
    m = re.search(r"\b([12])\s*(?:m|meter|meters|metre|metri|metro|metros)\s*[,\.]?\s*(\d{1,2})\s*(?:cm|sm)?\b",lower)
    if m: return int(m.group(1))*100+int(m.group(2))
    m = re.search(r"\b([12])[\.,](\d{2})\s*(?:m|meter|meters|metre|metri|metro|metros)?\b",lower)
    if m: return int(m.group(1))*100+int(m.group(2))
    m = re.search(r"\b(1[2-9]\d|2[0-3]\d)\s*(?:cm|sm|centimeters?|centimetres?)\b",lower)
    if m: return int(m.group(1))
    return None

def extract_weight_with_units(text: str) -> int | None:
    lower = text.lower()
    m = re.search(r"\b(\d{1,2})\s*(?:stones?|st\.?)\s*(\d{1,2})\s*(?:lb|lbs|pounds?)?\b",lower)
    if m:
        s,l = int(m.group(1)),int(m.group(2))
        if 3<=s<=50 and 0<=l<=13:
            r = stones_lbs_to_kg(s,l)
            if 25<=r<=300: return r
    m = re.search(r"\b(\d{1,2})\s*(?:stones?|st\.?)\b",lower)
    if m:
        s = int(m.group(1))
        if 3<=s<=50:
            r = stones_lbs_to_kg(s)
            if 25<=r<=300: return r
    m = re.search(r"\b(\d{2,3}(?:[.,]\d)?)\s*(?:lb|lbs|pounds?)\b",lower)
    if m:
        lbs = float(m.group(1).replace(",","."))
        if 55<=lbs<=660:
            r = round(lbs*0.453592)
            if 25<=r<=300: return r
    m = re.search(r"\b(\d{2,3}(?:[.,]\d)?)\s*(?:kg|kgs|kilograms?|kilogramme|kilograme|kilo)\b",lower)
    if m:
        w = float(m.group(1).replace(",","."))
        if 25<=w<=300: return round(w)
    return None

def calculate_bmi(height_cm, weight_kg) -> str:
    if not height_cm or not weight_kg: return ""
    return str(round(weight_kg/(height_cm/100)**2,1))

# ─────────────────────────────────────────────
# REGEX FALLBACK PARSING
# ─────────────────────────────────────────────

QUESTION_HEADERS = [
    "personal information","medical history","medications and allergies","patient requirements",
    "informations personnelles","antécédents médicaux","médicaments et allergies","exigences du patient",
    "informatii personale","informații personale","istoric medical","medicamente si alergii","medicamente și alergii",
    "información personal","historial médico","medicamentos y alergias","requisitos del paciente",
    "informazioni personali","storia medica","farmaci e allergie","richieste del paziente",
    "persönliche informationen","krankengeschichte","medikamente und allergien","patientenwünsche",
    "kişisel bilgiler","tıbbi geçmiş","ilaçlar ve alerjiler","hasta talepleri",
    "persoonlijke informatie","medische geschiedenis","medicijnen en allergieën","patiëntvereisten",
]

QUESTION_KEYWORDS = [
    "full name","age","height","weight","bmi","chronic","disease","infectious","infection",
    "surgeries","surgery","medications","medication","allergies","allergy","smoke","alcohol",
    "patient wants","patient requirements","requirements","procedure","treatment",
    "nom","âge","taille","poids","maladie","infection","chirurgie","opération","médicament","allergie","fume","alcool",
    "nume","vârstă","varsta","înălțime","inaltime","greutate","boală","boala","infecție","infectie","operație","operatie","medicamente","alergie","fumez",
    "nombre","edad","altura","peso","enfermedad","infección","infeccion","cirugía","cirugia","medicamento","alergia","fumar",
    "nome","età","eta","altezza","malattia","infezione","chirurgia","intervento","farmaco","allergia","fumo","alcol",
    "name","alter","größe","grosse","gewicht","krankheit","infektion","operation","medikament","rauchen","alkohol",
    "isim","ad","yaş","yas","boy","kilo","hastalık","hastalik","enfeksiyon","ameliyat","ilaç","ilac","alerji","sigara","alkol",
    "naam","leeftijd","lengte","ziekte","infectie","operatie","medicijn","roken",
]

NONE_PHRASES = {
    "English":["no","none","nothing","nope","nil","negative","not any","no any","no disease","no diseases",
               "no infection","no infections","no allergy","no allergies","no medication","no medications",
               "i don't have","i dont have","i don't take","i dont take","i do not have","i do not take","i have no","i have none"],
    "Dutch":["nee","geen","niets","niks","niet van toepassing","ik heb geen","ik gebruik geen","ik neem geen"],
    "French":["non","aucun","aucune","rien","néant","je n'ai pas","je nai pas","je ne prends pas"],
    "Romanian":["nu","niciuna","niciun","nimic","nu am","nu iau","fără","fara"],
    "Spanish":["no","ninguno","ninguna","nada","no tengo","no tomo","sin"],
    "Italian":["no","nessuno","nessuna","niente","non ho","non prendo","senza"],
    "German":["nein","keine","keiner","nichts","ich habe keine","ich nehme keine"],
    "Turkish":["hayır","hayir","yok","hiç yok","hic yok","yoktur","kullanmıyorum","kullanmiyorum",
               "almıyorum","almiyorum","alerji yok","herhangi bir","bulunmamaktadır"],
}

YES_SURGERY_PHRASES = {
    "English":["yes","i had","had","before","surgery","operation","operated"],
    "Dutch":["ja","ik had","gehad","eerder","operatie","geopereerd"],
    "French":["oui","j'ai eu","jai eu","chirurgie","opération","operation","opéré","avant"],
    "Romanian":["da","am avut","operație","operatie","chirurgie","operat","înainte","inainte"],
    "Spanish":["sí","si","tuve","cirugía","cirugia","operación","operacion","operado","antes"],
    "Italian":["sì","si","ho avuto","chirurgia","intervento","operazione","operato","prima"],
    "German":["ja","hatte","operation","operiert","chirurgie","vorher"],
    "Turkish":["evet","oldum","ameliyat","operasyon","daha önce","daha once","geçirdim","gecirdim"],
}

SMOKE_WORDS = {
    "English":["smok","cigarette","cigaret"],"Dutch":["rook","roken","sigaret","tabak"],
    "French":["fume","fumer","cigarette","tabac"],"Romanian":["fumez","fumat","țigări","tigari"],
    "Spanish":["fum","cigarrillo","tabaco"],"Italian":["fum","sigarett","tabacco"],
    "German":["rauche","rauchen","zigarette"],"Turkish":["sigara"],
}
ALCOHOL_WORDS = {
    "English":["alcohol","drink","wine","beer","spirits"],"Dutch":["alcohol","drinken","wijn","bier"],
    "French":["alcool","bois","boire","vin","bière"],"Romanian":["alcool","beau","băut","baut","vin","bere"],
    "Spanish":["alcohol","bebo","beber","vino","cerveza"],"Italian":["alcol","alcool","bevo","bere","vino","birra"],
    "German":["alkohol","trinke","trinken","wein","bier"],"Turkish":["alkol","içki","şarap","sarap","bira"],
}
OCCASIONAL_WORDS = {
    "English":["sometimes","occasionally","social","socially","rarely","once in a while","moderate"],
    "Dutch":["soms","af en toe","zelden","occasioneel","sociaal"],
    "French":["parfois","occasionnellement","socialement","rarement","de temps en temps"],
    "Romanian":["uneori","ocazional","social","rar"],
    "Spanish":["a veces","ocasionalmente","socialmente","rara vez"],
    "Italian":["a volte","occasionalmente","socialmente","raramente"],
    "German":["manchmal","gelegentlich","sozial","selten"],
    "Turkish":["bazen","ara sıra","ara sira","nadiren","sosyal olarak","arada sırada"],
}

FIELD_LABEL_PATTERNS = {
    "name":[r"(?:full\s+)?name",r"naam",r"nom(?:\s+complet)?",r"(?:ad\s+)?soyad",r"nome(?:\s+completo)?",r"nombre(?:\s+completo)?",r"isim",r"ad"],
    "age":[r"age",r"âge",r"leeftijd",r"vârst[aă]",r"edad",r"et[àa]",r"alter",r"ya[şs]"],
    "height":[r"height",r"tall",r"lengte",r"taille",r"în[aă]l[tț]ime",r"inaltime",r"altura",r"altezza",r"gr[öo][sß]e",r"boy"],
    "weight":[r"weight",r"gewicht",r"poids",r"greutate",r"peso",r"kilo(?:gram)?"],
    "chronic":[r"chronic",r"chronische?",r"chronique",r"cronice?",r"cronica",r"crónica?",r"kronik"],
    "infection":[r"infect",r"infectious",r"infecti(?:e|ous|on)",r"bula[şs]ıcı"],
    "surgery":[r"surger(?:y|ies)",r"operat(?:ion|ed|ie|ies)",r"chirurgi[ae]?",r"ameliyat",r"operatie",r"opération"],
    "medication":[r"medicat(?:ion|ions)",r"medicijnen?",r"médicaments?",r"medicamente",r"medicamento",r"farmac[oi]",r"medikamente?",r"ila[çc]",r"drugs?"],
    "allergy":[r"allerg(?:y|ies|ie|ies|en|ia)",r"allergieën",r"allergi(?:e|es|en)",r"alergi(?:i|a)?",r"alerg(?:ie|ii)?"],
    "smoke_alcohol":[r"smok(?:e|ing)",r"alcohol",r"sigara",r"alkol",r"rauchen",r"fume(?:r|z)?",r"tabac",r"roken",r"drink(?:ing)?",r"içki"],
}

_NAME_SKIP_WORDS = {
    "yes","no","none","sometimes","occasionally","cm","kg","lb","lbs","years","old","yo",
    "oui","non","aucun","aucune","parfois","da","nu","sí","si","sì","ja","nein","hayır","hayir",
    "yok","evet","nee","geen","chronic","disease","infection","surgery","medication","allergy","smoke","alcohol",
}

def get_answer_lines(text: str) -> list:
    text = normalize_text(text)
    lines = []
    for line in [clean_line(l) for l in text.split("\n")]:
        if not line: continue
        lower = line.lower().strip()
        if lower.strip("*: -–—") in QUESTION_HEADERS: continue
        if re.match(r"^\d+\s*[\.)\-]\s*",lower):
            after = re.sub(r"^\d+\s*[\.)\-]\s*","",lower).strip()
            if any(kw in after for kw in QUESTION_KEYWORDS) and (after.endswith(":") or not after): continue
        if lower.startswith("(") and lower.endswith(")"): continue
        if ":" in line:
            before,after = line.split(":",1)
            if any(kw in before.lower().strip() for kw in QUESTION_KEYWORDS):
                line = clean_line(after)
                if not line: continue
        lines.append(line)
    return lines

def try_label_field_extract(text: str) -> dict:
    found = {}
    text = normalize_text(text)
    for field,patterns in FIELD_LABEL_PATTERNS.items():
        for pattern in patterns:
            m = re.search(r"(?:^|\n)\s*(?:\d+\s*[\.)\-]\s*)?"+pattern+r"\s*[:\-–—]\s*(.+?)(?=\n|$)",text,flags=re.IGNORECASE|re.MULTILINE)
            if m:
                value = strip_leading_number(clean_line(m.group(1)))
                if value: found[field]=value; break
    return found

def extract_name(lines: list) -> str:
    for line in lines:
        candidate = clean_line(strip_leading_number(line))
        if not candidate: continue
        lower = candidate.lower()
        if not re.search(r"[^\W\d]",candidate,re.UNICODE): continue
        if re.match(r"^\d[\d\s\.,ckmgftin\'\"]*$",lower): continue
        if any(word_in_text(skip,lower) for skip in _NAME_SKIP_WORDS): continue
        if any(t in lower for t in ["disease","infection","surgery","medication","allergy","smoke","alcohol","chronic","kg"," cm","bmi"]): continue
        tokens = candidate.split()
        if 1<=len(tokens)<=5 and all(re.match(r"^[^\W\d]",t,re.UNICODE) for t in tokens):
            return candidate
    return lines[0] if lines else ""

def extract_age_with_words(text: str) -> str:
    lower = text.lower()
    for p in [r"(?:age|âge|vârst[aă]|varsta|edad|et[àa]|alter|ya[şs]|leeftijd)\s*[:\-]?\s*(\d{1,3})",
              r"(\d{1,3})\s*(?:years?\s*old|yo\b|y/o|ans\b|ani\b|años\b|anos\b|anni\b|jahre\b|yaşında|yasinda|jaar\b)"]:
        m = re.search(p,lower)
        if m:
            age = int(m.group(1))
            if 1<=age<=120: return str(age)
    return ""

def extract_age_height_weight_by_order(lines: list) -> tuple:
    full_text = "\n".join(lines)
    height_cm = extract_height_with_units(full_text)
    weight_kg = extract_weight_with_units(full_text)
    age = extract_age_with_words(full_text)
    name = extract_name(lines)
    name_index = next((i for i,l in enumerate(lines) if l==name),None)
    start = 1 if name_index is None else name_index+1
    numeric_lines = []
    for idx in range(start,len(lines)):
        candidate = strip_leading_number(lines[idx])
        numbers = re.findall(r"\d+(?:[.,]\d+)?",candidate)
        if numbers: numeric_lines.append((idx,float(numbers[0].replace(",",".")),candidate))
        if len(numeric_lines)>=4: break
    if not age and numeric_lines:
        p = numeric_lines[0][1]
        if 1<=p<=120: age = str(int(p))
    if height_cm is None and len(numeric_lines)>=2:
        p = numeric_lines[1][1]
        if 120<=p<=230: height_cm=int(p)
        elif 1.2<=p<=2.3: height_cm=round(p*100)
    if weight_kg is None and len(numeric_lines)>=3:
        p = numeric_lines[2][1]
        if 25<=p<=300: weight_kg=int(p)
    return age,height_cm,weight_kg

def words_for(language,dictionary):
    combined = list(dictionary.get(language,[]))
    if language!="English": combined+=dictionary.get("English",[])
    return combined

def _is_none_answer(answer,patient_language):
    text = answer.lower().strip()
    boundary = {"no","none","nee","nu","nein","non","yok","geen","nada","nil","nope","ja","si","da"}
    for phrase in words_for(patient_language,NONE_PHRASES):
        if phrase in boundary:
            if word_in_text(phrase,text): return True
        else:
            if substr_in_text(phrase,text): return True
    return False

def _has_exception_clause(answer):
    return any(word_in_text(w,answer.lower()) for w in ["but","except","only","however","although","mais","sauf","pero","ma","ama","maar","behalve","ancak","fakat","sadece"])

def translate_basic_answer(token,doctor_language):
    labels=LABELS[doctor_language]
    return {"__NONE__":labels["none"],"__YES_STAR__":labels["yes_star"],"__OCCASIONALLY__":labels["occasionally"],
            "__OCC_SMOKE__":labels["occasionally_smokes"],"__OCC_DRINK__":labels["occasionally_drinks"],
            "__OCC_BOTH__":labels["occasionally_smokes_drinks"]}.get(token,token)

def normalize_answer(answer,patient_language,doctor_language):
    answer=clean_line(answer)
    if not answer: return ""
    if _is_none_answer(answer,patient_language) and not _has_exception_clause(answer):
        return translate_basic_answer("__NONE__",doctor_language)
    return strip_leading_number(online_translate_text(answer,patient_language,doctor_language))

def normalize_surgery(answer,patient_language,doctor_language):
    answer=clean_line(answer)
    if not answer: return ""
    if _is_none_answer(answer,patient_language) and not _has_exception_clause(answer):
        return translate_basic_answer("__NONE__",doctor_language)
    lower=answer.lower()
    yes_indicators=words_for(patient_language,YES_SURGERY_PHRASES)
    if any(word_in_text(w,lower) if len(w)<=4 else substr_in_text(w,lower) for w in yes_indicators):
        if lower.strip() in {"yes","oui","da","sí","si","sì","ja","evet"}:
            return translate_basic_answer("__YES_STAR__",doctor_language)
        translated=strip_leading_number(online_translate_text(answer,patient_language,doctor_language))
        return translated+" *" if "*" not in translated else translated
    return strip_leading_number(online_translate_text(answer,patient_language,doctor_language))

def normalize_smoke_alcohol(answer,patient_language,doctor_language):
    answer=clean_line(answer)
    if not answer: return ""
    if _is_none_answer(answer,patient_language) and not _has_exception_clause(answer):
        return translate_basic_answer("__NONE__",doctor_language)
    lower=answer.lower()
    has_smoke=any(substr_in_text(w,lower) for w in words_for(patient_language,SMOKE_WORDS))
    has_alcohol=any(substr_in_text(w,lower) for w in words_for(patient_language,ALCOHOL_WORDS))
    occasional=any(substr_in_text(w,lower) for w in words_for(patient_language,OCCASIONAL_WORDS))
    if occasional and not has_smoke and not has_alcohol: return translate_basic_answer("__OCCASIONALLY__",doctor_language)
    if occasional and has_smoke and has_alcohol: return translate_basic_answer("__OCC_BOTH__",doctor_language)
    if occasional and has_smoke: return translate_basic_answer("__OCC_SMOKE__",doctor_language)
    if occasional and has_alcohol: return translate_basic_answer("__OCC_DRINK__",doctor_language)
    return strip_leading_number(online_translate_text(answer,patient_language,doctor_language))

def get_order_based_answers(lines,label_extracted):
    answers={k:label_extracted.get(k,"") for k in ["name","chronic","infection","surgery","medication","allergy","smoke_alcohol"]}
    if sum(1 for v in answers.values() if v)>=4: return answers
    name=extract_name(lines) if not answers["name"] else answers["name"]
    answers["name"]=name
    remaining=[l for l in lines if l!=name]
    personal_numbers,rest=[],[]
    for line in remaining:
        candidate=strip_leading_number(line)
        if len(personal_numbers)<3 and re.search(r"\d",candidate): personal_numbers.append(candidate)
        else: rest.append(candidate)
    if len(personal_numbers)<3:
        personal_numbers=[strip_leading_number(l) for l in remaining[:3]]
        rest=[strip_leading_number(l) for l in remaining[3:]]
    for i,field in enumerate(["chronic","infection","surgery","medication","allergy","smoke_alcohol"]):
        if not answers[field]: answers[field]=rest[i] if i<len(rest) else ""
    return answers

def extract_patient_requirement_from_text(lines):
    patterns=[r"patient\s+wants?\s+(.+)",r"wants?\s+(.+)",r"interested\s+in\s+(.+)",r"looking\s+for\s+(.+)",
              r"procedure\s*[:\-]?\s*(.+)",r"treatment\s*[:\-]?\s*(.+)",r"requirement\s*[:\-]?\s*(.+)",
              r"souhaite\s+(.+)",r"veut\s+(.+)",r"dorește\s+(.+)",r"doreste\s+(.+)",r"quiere\s+(.+)",
              r"desidera\s+(.+)",r"möchte\s+(.+)",r"mochte\s+(.+)",r"istiyor\s+(.+)",r"wil\s+(.+)",r"wenst\s+(.+)"]
    for line in lines:
        for pattern in patterns:
            m=re.search(pattern,line.lower(),flags=re.IGNORECASE)
            if m:
                req=re.sub(r"^[\(\[]|[\)\]]$","",clean_line(m.group(1))).strip()
                if req: return req
    return ""

def format_patient_message_regex(patient_text,requirement_text,patient_language,doctor_language):
    if doctor_language not in LABELS: doctor_language="English"
    labels=LABELS[doctor_language]
    lines=get_answer_lines(patient_text)
    if not lines: return None
    label_extracted=try_label_field_extract(patient_text)
    detected_req=extract_patient_requirement_from_text(lines)
    lines=[l for l in lines if not any(t in l.lower() for t in ["patient wants","interested in","looking for","procedure:","treatment:","requirement:","souhaite","dorește","doreste","quiere","desidera","möchte","mochte","istiyor","wil","wenst"])]
    requirement=clean_line(requirement_text) or detected_req
    if requirement: requirement=strip_leading_number(online_translate_text(requirement,patient_language,doctor_language))
    answers=get_order_based_answers(lines,label_extracted)
    age,height_cm,weight_kg=extract_age_height_weight_by_order(lines)
    if label_extracted.get("age"): age=extract_age_with_words(label_extracted["age"]) or age
    if label_extracted.get("height"):
        h=extract_height_with_units(label_extracted["height"])
        if h: height_cm=h
    if label_extracted.get("weight"):
        w=extract_weight_with_units(label_extracted["weight"])
        if w: weight_kg=w
    bmi=calculate_bmi(height_cm,weight_kg)
    return {
        "requirements":labels["requirements"],"patient_wants":labels["patient_wants"],
        "requirement":requirement or "—","personal":labels["personal"],
        "full_name":labels["full_name"],"full_name_value":answers["name"] or "—",
        "age":labels["age"],"age_value":f"{age} {labels['yo']}" if age else "—",
        "height":labels["height"],"height_value":f"{height_cm} cm" if height_cm else "—",
        "weight":labels["weight"],"weight_value":f"{weight_kg} kg" if weight_kg else "—",
        "bmi":labels["bmi"],"bmi_value":bmi or "—",
        "medical":labels["medical"],"chronic":labels["chronic"],
        "chronic_value":normalize_answer(answers["chronic"],patient_language,doctor_language) or "—",
        "infectious":labels["infectious"],
        "infection_value":normalize_answer(answers["infection"],patient_language,doctor_language) or "—",
        "surgery":labels["surgery"],
        "surgery_value":normalize_surgery(answers["surgery"],patient_language,doctor_language) or "—",
        "med_allergy":labels["med_allergy"],"medication":labels["medication"],
        "medication_value":normalize_answer(answers["medication"],patient_language,doctor_language) or "—",
        "allergy":labels["allergy"],
        "allergy_value":normalize_answer(answers["allergy"],patient_language,doctor_language) or "—",
        "smoke_alcohol":labels["smoke_alcohol"],
        "smoke_value":normalize_smoke_alcohol(answers["smoke_alcohol"],patient_language,doctor_language) or "—",
    }

# ─────────────────────────────────────────────
# UNIFIED ENTRY POINT
# ─────────────────────────────────────────────

def format_patient_message(patient_text,requirement_text="",patient_language="English",doctor_language="English"):
    if doctor_language not in LABELS: doctor_language="English"
    api_key=_get_api_key()
    if _anthropic_available and api_key:
        ai_raw=ai_extract_fields(patient_text,patient_language)
        if ai_raw:
            result=ai_fields_to_formatted(ai_raw,requirement_text,patient_language,doctor_language)
            if result:
                result["_source"]="ai"
                return result
    result=format_patient_message_regex(patient_text,requirement_text,patient_language,doctor_language)
    if result: result["_source"]="regex"
    return result

def data_to_plain_text(data: dict) -> str:
    if data is None: return ""
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
# CSS
# ─────────────────────────────────────────────

st.markdown("""
<style>
:root {
    --navy-950:#061433;--navy-900:#0a1a3f;--navy-800:#122657;--navy-700:#1f3265;
    --red:#e30613;--white:#ffffff;--border:rgba(255,255,255,.13);
    --card:rgba(6,20,51,.72);--field:rgba(255,255,255,.08);
    --green:#22c55e;--orange:#fb923c;--violet:#a78bfa;
}
.stApp {
    background:
        radial-gradient(circle at 10% 12%,rgba(227,6,19,0.18),transparent 28%),
        radial-gradient(circle at 88% 0%,rgba(96,165,250,0.18),transparent 24%),
        linear-gradient(135deg,var(--navy-950),var(--navy-900) 42%,#07112b 100%);
    color:var(--white);
}
.block-container{padding-top:.7rem;padding-bottom:.7rem;max-width:1420px;}
[data-testid="stHeader"]{background:transparent;}
[data-testid="stToolbar"]{display:none;}
.app-title-card{
    position:relative;overflow:hidden;width:100%;box-sizing:border-box;
    border:1px solid var(--border);border-radius:24px;background:rgba(6,20,51,.78);
    box-shadow:0 16px 44px rgba(0,0,0,.20);padding:12px 16px;margin-bottom:10px;
    backdrop-filter:blur(18px);display:flex;align-items:center;justify-content:space-between;gap:16px;
}
.app-title-card::before{
    content:"";position:absolute;inset:0;
    background:linear-gradient(90deg,transparent,rgba(255,255,255,.13),transparent);
    transform:translateX(-100%);animation:headerFadeScan 5.8s infinite;pointer-events:none;
}
@keyframes headerFadeScan{
    0%{transform:translateX(-100%);opacity:0;}15%{opacity:1;}
    55%{transform:translateX(100%);opacity:1;}70%{opacity:0;}
    100%{transform:translateX(100%);opacity:0;}
}
.app-title-card>*{position:relative;z-index:1;}
.app-title-card h1{margin:0;color:#fff;font-size:clamp(1.15rem,2vw,1.8rem);line-height:1.05;letter-spacing:-0.025em;text-transform:uppercase;}
.app-title-card p{margin:4px 0 0 0;max-width:900px;color:#c8d4ec;font-size:.84rem;line-height:1.35;}
.app-title-text{min-width:0;display:flex;align-items:center;gap:16px;}
.header-logo{width:56px;height:56px;border-radius:15px;background:#fff;border:1px solid rgba(255,255,255,.18);display:flex;align-items:center;justify-content:center;overflow:hidden;flex:0 0 auto;box-shadow:0 10px 26px rgba(0,0,0,.16);}
.header-logo img{width:100%;height:100%;object-fit:contain;padding:8px;box-sizing:border-box;}
.header-copy{min-width:0;}
.hero-kicker{display:inline-flex;align-items:center;width:fit-content;gap:8px;padding:6px 10px;border-radius:999px;border:1px solid rgba(255,255,255,.22);background:rgba(255,255,255,.10);color:#dbeafe;font-weight:800;font-size:.70rem;letter-spacing:.08em;text-transform:uppercase;backdrop-filter:blur(12px);}
.hero-kicker span{width:9px;height:9px;border-radius:999px;background:var(--red);box-shadow:0 0 0 0 rgba(227,6,19,.65);animation:pulse 1.8s infinite;}
@keyframes pulse{70%{box-shadow:0 0 0 9px rgba(227,6,19,0);}100%{box-shadow:0 0 0 0 rgba(227,6,19,0);}}
.ai-badge{display:inline-flex;align-items:center;gap:7px;padding:5px 12px;border-radius:999px;border:1px solid rgba(139,92,246,.4);background:rgba(139,92,246,.15);color:#c4b5fd;font-size:.70rem;font-weight:800;letter-spacing:.07em;text-transform:uppercase;margin-bottom:8px;}
.ai-badge-dot{width:7px;height:7px;border-radius:50%;background:#a78bfa;animation:pulse 1.8s infinite;}
.regex-badge{display:inline-flex;align-items:center;gap:7px;padding:5px 12px;border-radius:999px;border:1px solid rgba(251,146,60,.4);background:rgba(251,146,60,.12);color:#fdba74;font-size:.70rem;font-weight:800;letter-spacing:.07em;text-transform:uppercase;margin-bottom:8px;}
.auto-badge{display:inline-flex;align-items:center;gap:6px;padding:4px 10px;border-radius:999px;border:1px solid rgba(52,211,153,.35);background:rgba(52,211,153,.12);color:#6ee7b7;font-size:.70rem;font-weight:800;letter-spacing:.07em;text-transform:uppercase;margin-bottom:8px;}
.auto-badge-dot{width:7px;height:7px;border-radius:50%;background:#34d399;animation:pulse 1.8s infinite;}
.panel-title{display:flex;align-items:center;gap:10px;color:#eef5ff;font-weight:900;letter-spacing:.08em;font-size:.78rem;text-transform:uppercase;margin-bottom:6px;}
.panel-dot{width:9px;height:9px;border-radius:50%;background:var(--red);box-shadow:0 0 14px rgba(227,6,19,.7);}
.stTextArea textarea,.stTextInput input{background:var(--field)!important;color:#f8fbff!important;border:1px solid rgba(255,255,255,0.16)!important;border-radius:18px!important;box-shadow:inset 0 0 0 1px rgba(255,255,255,.02)!important;}
.stTextInput input::placeholder,.stTextArea textarea::placeholder{color:rgba(233,240,255,.48)!important;}
.stSelectbox div[data-baseweb="select"]>div{background:var(--field)!important;border-color:rgba(255,255,255,0.16)!important;border-radius:16px!important;color:#f8fbff!important;}
.stButton>button{width:100%;border:1px solid rgba(255,255,255,.14);border-radius:18px;padding:.75rem 1rem;color:#fff;font-weight:900;background:linear-gradient(90deg,var(--red),#ff4050);box-shadow:0 12px 30px rgba(227,6,19,.20);transition:transform .15s ease,box-shadow .15s ease,filter .15s ease;}
.stButton>button:hover{transform:translateY(-1px);filter:brightness(1.05);box-shadow:0 18px 44px rgba(227,6,19,.26);color:#fff;}
.info-note{color:#b9c6df;font-size:.86rem;padding:10px 12px;border:1px solid rgba(255,255,255,.10);border-radius:16px;background:rgba(255,255,255,.06);}
.result-card{border:1px solid rgba(255,255,255,0.13);border-radius:22px;padding:0;background:transparent;min-height:0;}
hr{border-color:rgba(255,255,255,0.10);}
@media(max-width:900px){.app-title-card{flex-direction:column;align-items:flex-start;}.app-title-text{align-items:flex-start;}}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# UI HELPERS
# ─────────────────────────────────────────────

def image_to_data_uri(path):
    fp=Path(path)
    if not fp.exists(): return ""
    suffix=fp.suffix.lower()
    mime="image/jpeg" if suffix in [".jpg",".jpeg"] else "image/webp" if suffix==".webp" else "image/png"
    return f"data:{mime};base64,{base64.b64encode(fp.read_bytes()).decode()}"

def find_logo_data_uri():
    for p in ["logo.png","logo.jpg","logo.jpeg","app/static/logo.png","static/logo.png"]:
        d=image_to_data_uri(p)
        if d: return d
    return ""

def render_hero():
    api_key=_get_api_key()
    if _anthropic_available and api_key:
        status_html='<div class="hero-kicker"><span></span>Claude AI extraction active</div>'
    elif _anthropic_available and not api_key:
        status_html='<div class="hero-kicker" style="border-color:rgba(251,146,60,.4);background:rgba(251,146,60,.12);color:#fdba74;"><span style="background:#fb923c;box-shadow:none;animation:none;"></span>Add ANTHROPIC_API_KEY to .env</div>'
    else:
        status_html='<div class="hero-kicker"><span></span>Regex mode</div>'
    logo_uri=find_logo_data_uri()
    logo_html=f'<div class="header-logo"><img src="{logo_uri}" alt="logo"></div>' if logo_uri else '<div class="header-logo"></div>'
    st.markdown(f"""
<div class="app-title-card">
  <div class="app-title-text">
    {logo_html}
    <div class="header-copy">
      <h1>Clinical Intake Formatter</h1>
      <p>Paste patient answers in any language or format — Claude AI extracts everything instantly. Outputs clean doctor messages in <strong>English</strong> or <strong>Turkish</strong>.</p>
    </div>
  </div>
  {status_html}
</div>
""", unsafe_allow_html=True)

def render_result(data):
    if not data:
        st.markdown('<div class="result-card"><div class="info-note">Your doctor message will appear here automatically when you paste patient data.</div></div>', unsafe_allow_html=True)
        return
    source=data.get("_source","regex")
    if source=="ai":
        st.markdown('<div class="ai-badge"><span class="ai-badge-dot"></span>Extracted by Claude AI</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="regex-badge">⚙️ Extracted by pattern matching</div>', unsafe_allow_html=True)
    plain_text=data_to_plain_text(data)
    message_key=hashlib.md5(plain_text.encode()).hexdigest()[:12]
    st.text_area("Doctor message",value=plain_text,height=320,label_visibility="collapsed",key=f"doctor_message_text_area_{message_key}")

def copy_button_component(text):
    safe=escape(text).replace("\n","\\n").replace("'","&#39;")
    components.html(f"""
<style>
.copy-btn{{width:100%;border:1px solid rgba(52,211,153,.34);border-radius:18px;padding:13px 18px;color:#03130a;font-weight:900;font-family:Inter,ui-sans-serif,system-ui,sans-serif;background:linear-gradient(90deg,#34d399,#22c55e);box-shadow:0 12px 30px rgba(52,211,153,.16);cursor:pointer;}}
.copy-btn:hover{{filter:brightness(1.05);}}
.msg{{margin-top:8px;color:#94a3b8;font-family:Inter,sans-serif;font-size:13px;}}
</style>
<button class="copy-btn" onclick="copyText()">Copy doctor message</button>
<div id="msg" class="msg"></div>
<script>
function copyText(){{
  navigator.clipboard.writeText(`{safe}`).then(
    ()=>document.getElementById('msg').innerHTML='Copied. Ready to paste.',
    ()=>document.getElementById('msg').innerHTML='Copy failed — select text manually.'
  );
}}
</script>
""", height=82)

# ─────────────────────────────────────────────
# AUTO-FORMAT CALLBACK
# ─────────────────────────────────────────────

def run_format():
    text=st.session_state.get("patient_text_input","")
    req=st.session_state.get("requirement_input","")
    pat_lang=st.session_state.get("patient_language_select","English")
    doc_lang=st.session_state.get("doctor_language_select","English")
    if text.strip():
        data=format_patient_message(text,req,pat_lang,doc_lang)
        st.session_state.generated_data=data
        st.session_state.plain_message=data_to_plain_text(data) if data else ""
    else:
        st.session_state.generated_data=None
        st.session_state.plain_message=""

# ─────────────────────────────────────────────
# APP LAYOUT
# ─────────────────────────────────────────────

render_hero()

if "generated_data" not in st.session_state: st.session_state.generated_data=None
if "plain_message" not in st.session_state: st.session_state.plain_message=""

top_a,top_b,top_c=st.columns([2.2,1,1])
with top_a:
    st.text_input("Patient wants",placeholder="breast lift, rhinoplasty, lipoabdominoplasty…",key="requirement_input",on_change=run_format)
with top_b:
    st.selectbox("Patient language",PATIENT_LANGUAGES,index=0,key="patient_language_select",on_change=run_format)
with top_c:
    st.selectbox("Doctor message",DOCTOR_MESSAGE_LANGUAGES,index=0,key="doctor_language_select",on_change=run_format)

left,right=st.columns([1,1],gap="large")

with left:
    api_key=_get_api_key()
    if _anthropic_available and api_key:
        badge='<div class="auto-badge"><span class="auto-badge-dot"></span>Auto-formats on paste · AI-powered</div>'
    else:
        badge='<div class="auto-badge"><span class="auto-badge-dot"></span>Auto-formats on paste</div>'
    st.markdown(f'<div class="panel-title"><span class="panel-dot"></span>Patient answers</div>{badge}', unsafe_allow_html=True)
    st.text_area("Paste raw patient answer",value="",placeholder="Paste the patient's answers here in any language or format…",
                 height=320,label_visibility="collapsed",key="patient_text_input",on_change=run_format)
    b1,b2=st.columns([1.35,1])
    with b1:
        if st.button("Generate message",type="primary",use_container_width=True):
            run_format(); st.rerun()
    with b2:
        if st.button("Clear",use_container_width=True):
            st.session_state.generated_data=None
            st.session_state.plain_message=""
            st.rerun()
    if _anthropic_available and api_key:
        note="<strong>Claude AI</strong> understands any format, language, or phrasing. Measurements auto-convert to cm/kg. Falls back to pattern matching if AI is unavailable."
    else:
        note="<strong>Pattern matching mode.</strong> Add <code>ANTHROPIC_API_KEY=sk-ant-...</code> to a <code>.env</code> file next to app.py to enable full AI extraction."
    st.markdown(f'<div class="info-note">{note}</div>', unsafe_allow_html=True)

with right:
    st.markdown('<div class="panel-title"><span class="panel-dot" style="background:#34d399;box-shadow:0 0 14px rgba(52,211,153,.8)"></span>Doctor-ready output</div>', unsafe_allow_html=True)
    render_result(st.session_state.generated_data)
    if st.session_state.plain_message:
        copy_button_component(st.session_state.plain_message)

st.markdown('<div style="color:#64748b;font-size:12px;text-align:center;padding:8px 0 4px 0;">No patient data is stored by this app. AI extraction sends text to the Anthropic API. Translation sends text to Google Translate.</div>', unsafe_allow_html=True)

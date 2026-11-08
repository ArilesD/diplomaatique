import re
from typing import Dict, List

from cleaner import clean_ocr_text


# Ce module extrait des libelles de services/structures administratives.
# Il vise surtout les lignes "entete" des arretes (Direction..., Service..., Cabinet...).

_SERVICE_TOKEN_RE = re.compile(
    r"(?i)\b("
    r"SERVICE|DIRECTION|CABINET|BUREAU|PREFECTURE|SOUS[-\s]?PREFECTURE|"
    r"SECRETARIAT\s+GENERAL|DELEGATION|MISSION|AGENCE|DDETS|DDTM|DREAL|ARS|DDPP|DDSP"
    r")\b"
)

# Fallback quand plusieurs libelles sont colles dans la meme ligne OCR.
_INLINE_SERVICE_RE = re.compile(
    r"(?i)\b("
    r"(?:CABINET|BUREAU|DIRECTION|SERVICE)\s+[^.;:\n]{3,}"
    r")"
)

_SERVICE_START_RE = re.compile(
    r"(?i)^\s*(?:"
    r"CABINET|BUREAU|DIRECTION|SERVICE|SECRETARIAT\s+GENERAL|DELEGATION|MISSION|"
    r"AGENCE|DDETS|DDTM|DREAL|ARS|DDPP|DDSP"
    r")\b"
)

_INSTITUTION_CONTEXT_RE = re.compile(r"(?i)/\s*(?:SERVICE|DIRECTION)\b")

# Debut de sections juridiques: on ne veut pas les prendre comme services.
_STOP_LINE_RE = re.compile(
    r"(?i)^\s*(?:VU\b|CONSID\S*RANT\b|ARTICLE\b|ARRETE\b|DECIDE\b|ORDONNE\b|FAIT\b)"
)

# Fragments qui indiquent souvent une phrase metier/juridique et non un libelle d'entete.
_NOISE_FRAGMENT_RE = re.compile(
    r"(?i)\b("
    r"en\s+fin\s+de\s+service|prise\s+de\s+service|mise\s+en\s+service|"
    r"aires?\s+de\s+service|service\s+de\s+garde|service\s+d['e]interet\s+general|"
    r"tribunal|telerecours|www\.|http|@\w+|courriel|cs\s+\d{2,}|"
    r"sur\s+proposition|sont\s+charges?|est\s+charge|pour\s+la\s+prefet"
    r")\b"
)

_PERSON_ROLE_RE = re.compile(
    r"(?i)^\s*(?:M(?:ME)?\.?|MONSIEUR|MADAME|LE|LA)\s+"
    r"(?:PREFET(?:E)?|SOUS[-\s]?PREFET(?:E)?|DIRECTEUR(?:TRICE)?)\b"
)

_ACTION_WORD_RE = re.compile(
    r"(?i)\b("
    r"proceder|procede|institue|institues|charg[eé]s?|application|"
    r"afin\s+de|sur\s+proposition|au\s+sein|pour\s+"
    r")\b"
)


def _normalize(value: str) -> str:
    # Normalisation legere pour faciliter la deduplication.
    value = re.sub(r"\s+", " ", value).strip(" ,;:.-\t")
    value = re.sub(r"(?i)\bde\s+la\s+prefete?\b", "", value).strip(" ,;:.-\t")
    return value


def _prepare_lines(text: str) -> List[str]:
    if not isinstance(text, str):
        return []
    cleaned = clean_ocr_text(text)
    return [line.strip() for line in cleaned.splitlines() if line.strip()]


def _prepare_raw_lines(text: str) -> List[str]:
    if not isinstance(text, str):
        return []
    return [line.strip() for line in text.splitlines() if line.strip()]


def _is_probable_service_line(line: str) -> bool:
    if _STOP_LINE_RE.match(line):
        return False
    if not _SERVICE_TOKEN_RE.search(line):
        return False
    if _PERSON_ROLE_RE.search(line):
        return False
    if _NOISE_FRAGMENT_RE.search(line):
        return False
    if len(line) < 6 or len(line) > 130:
        return False
    # Heuristique par score: on favorise les vrais entetes institutionnels.
    score = 0
    if _SERVICE_START_RE.search(line):
        score += 3
    if _INSTITUTION_CONTEXT_RE.search(line):
        score += 2
    if "," not in line and ";" not in line and "." not in line:
        score += 1
    # Les verbes d'action indiquent plutot une phrase qu'un nom de structure.
    if _ACTION_WORD_RE.search(line):
        score -= 3
    if line.count(" ") > 16 and "," in line:
        score -= 2
    return score >= 2


def _collect_line_candidates(lines: List[str]) -> List[str]:
    # On favorise les entetes (debut de document), mais on garde un fallback global.
    head = lines[:350]
    candidates: List[str] = []

    for line in head:
        if _is_probable_service_line(line):
            candidates.append(_normalize(line))

    # Si on trouve deja des candidats dans les entetes, on s'arrete la.
    if candidates:
        return candidates

    # Fallback OCR: parfois plusieurs libelles sont colles sur une seule ligne.
    whole_text = "\n".join(lines)
    inline_candidates: List[str] = []
    for match in _INLINE_SERVICE_RE.finditer(whole_text):
        candidate = _normalize(match.group(1))
        if _is_probable_service_line(candidate):
            inline_candidates.append(candidate)
    return inline_candidates


def _collect_unique_candidates(text: str) -> List[str]:
    # Retourne les candidats detectes, sans doublons, dans l'ordre d'apparition.
    cleaned_lines = _prepare_lines(text)
    raw_lines = _prepare_raw_lines(text)
    if not cleaned_lines and not raw_lines:
        return []

    # On combine texte nettoye + texte brut, car le cleaning peut parfois perdre des entetes.
    raw_candidates = _collect_line_candidates(cleaned_lines)
    raw_candidates.extend(_collect_line_candidates(raw_lines))

    unique: List[str] = []
    seen: set[str] = set()
    for item in raw_candidates:
        cleaned = _normalize(item)
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(cleaned)

    return unique


def extract_service(text: str) -> str:
    # Extrait le premier libelle "service" pertinent.
    candidates = _collect_unique_candidates(text)

    # Priorite a un vrai libelle qui commence par "Service ...".
    for item in candidates:
        if re.search(r"(?i)^\s*SERVICE\b", item):
            return item

    # Sinon, on accepte un contexte de type "... / Service ...".
    for item in candidates:
        if re.search(r"(?i)/\s*SERVICE\b", item):
            return item
    return ""


def extract_direction_bureau_cabinet(text: str) -> List[str]:
    # Extrait les lignes de type direction / bureau / cabinet.
    candidates = _collect_unique_candidates(text)
    selected: List[str] = []
    for item in candidates:
        if re.search(r"(?i)^\s*(?:DIRECTION|BUREAU|CABINET)\b", item):
            selected.append(item)
    return selected


def extract_services(text: str) -> Dict[str, object]:
    # Extrait les deux informations attendues:
    # - service principal
    # - direction / bureau / cabinet
    return {
        "service": extract_service(text),
        "direction_bureau_cabinet": extract_direction_bureau_cabinet(text),
    }

import re
import unicodedata
from typing import Dict, List, Optional, Tuple

from cleaner import clean_ocr_text

_DATE_LINE_RE = re.compile(
    r"(?im)\bFait\s+(?:a|à|Ã\S*)\s+([A-Za-zÀ-ÖØ-öø-ÿ' -]+),?\s+le\s+(\d{1,2}\s+[A-Za-zÀ-ÖØ-öø-ÿ]+\s+\d{4})\b"
)
_DATE_ONLY_RE = re.compile(r"(?im)\ble\s+(\d{1,2}\s+[A-Za-zÀ-ÖØ-öø-ÿ]+\s+\d{4})\b")

_NAME_WITH_CIVILITE_RE = re.compile(
    r"(?i)\b(?:M\.?|MME\.?|MONSIEUR|MADAME)\s+([A-Z][A-Za-zÀ-ÖØ-öø-ÿ' -]{1,})\b"
)
_NAME_UPPER_RE = re.compile(r"[A-ZÀ-ÖØ-Þ][A-ZÀ-ÖØ-Þ' -]{2,}")

_DATE_LINE_NORM_RE = re.compile(r"\bfait\s+a\s+.+,\s+le\s+\d{1,2}\s+[a-z]+\s+\d{4}\b")
_FUNCTION_HINT_RE = re.compile(
    r"\b(?:prefet|prefete|sous[- ]?prefet|secretaire|directeur|directrice|"
    r"president|presidente|maire|cabinet|pour le prefet|par delegation|p/?o)\b"
)
_NOISE_RE = re.compile(
    r"\b(?:article|vu|considerant|recours|tribunal|telerecours|www\.|notification|"
    r"execution|publie|arrete)\b"
)


def _prepare_lines(text: str) -> List[str]:
    if not isinstance(text, str):
        return []
    cleaned = clean_ocr_text(text)
    return [re.sub(r"\s+", " ", line).strip() for line in cleaned.splitlines()]


def _normalize_for_match(value: str) -> str:
    if not value:
        return ""

    # Repare les formes mojibake les plus frequentes avant normalisation.
    repaired = value
    repairs = {
        "Ã©": "e",
        "Ã¨": "e",
        "Ãª": "e",
        "Ã«": "e",
        "Ã ": "a",
        "Ã ": "a",
        "Ã¢": "a",
        "Ã®": "i",
        "Ã¯": "i",
        "Ã´": "o",
        "Ã¹": "u",
        "Ã»": "u",
        "Ã§": "c",
        "Â": " ",
    }
    for broken, fixed in repairs.items():
        repaired = repaired.replace(broken, fixed)

    normalized = unicodedata.normalize("NFKD", repaired)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.lower()
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _signature_zone_lines(lines: List[str], size: int = 80) -> List[str]:
    if not lines:
        return []

    start = max(0, len(lines) - size)
    normalized = [_normalize_for_match(line) for line in lines]
    for idx in range(len(lines) - 1, start - 1, -1):
        if _DATE_LINE_NORM_RE.search(normalized[idx]):
            start = idx
            break
    return [line for line in lines[start:] if line]


def _has_signature_marker(line: str) -> bool:
    normalized = _normalize_for_match(line)
    if re.search(r"\bsign", normalized):
        return True
    if re.search(r"(?i)\bsign\S{0,8}", line):
        return True
    return False


def _clean_name_candidate(candidate: str) -> str:
    cleaned = re.sub(r"\s+", " ", candidate).strip(" ,;:-")
    cleaned = re.sub(r"(?i)^(?:M\.?|MME\.?|MONSIEUR|MADAME)\s+", "", cleaned).strip(" ,;:-")
    return cleaned


def _looks_like_function_line(line: str) -> bool:
    normalized = _normalize_for_match(line)
    if not normalized:
        return False
    if _has_signature_marker(line):
        return False
    if _NOISE_RE.search(normalized):
        return False
    return bool(_FUNCTION_HINT_RE.search(normalized))


def _is_probable_person_name(candidate: str) -> bool:
    cleaned = _clean_name_candidate(candidate)
    if len(cleaned) < 4:
        return False

    normalized = _normalize_for_match(cleaned)
    if _NOISE_RE.search(normalized):
        return False
    if _looks_like_function_line(cleaned):
        return False

    tokens = [token for token in re.split(r"[ \-']", cleaned) if token]
    if len(tokens) < 2:
        return False

    uppercase_count = sum(1 for token in tokens if len(token) >= 2 and token.isupper())
    starts_upper_count = sum(1 for token in tokens if token[:1].isalpha() and token[:1].isupper())
    return uppercase_count >= 1 or starts_upper_count >= 2


def _extract_inline_name_after_signed_marker(line: str) -> str:
    if not _has_signature_marker(line):
        return ""

    # Couvre "Signé : NOM", "Signe - NOM", mais aussi "SignÃ© : NOM".
    match = re.search(r"(?i)\bsign\S*\s*[:\-]\s*(.+)$", line)
    if match:
        return _clean_name_candidate(match.group(1))

    match = re.search(r"(?i)\bsign\S*\s+(.+)$", line)
    if match:
        return _clean_name_candidate(match.group(1))

    return ""


def _extract_name_near_signature(lines: List[str]) -> Tuple[str, Optional[int], Optional[int], str]:
    if not lines:
        return "", None, None, ""

    for idx in range(len(lines) - 1, -1, -1):
        if not _has_signature_marker(lines[idx]):
            continue

        inline_name = _extract_inline_name_after_signed_marker(lines[idx])
        if inline_name and _is_probable_person_name(inline_name):
            return inline_name, idx, idx, lines[idx]

        for j in range(idx + 1, min(idx + 5, len(lines))):
            candidate = _clean_name_candidate(lines[j])
            if _is_probable_person_name(candidate):
                return candidate, j, idx, lines[j]

    for idx in range(len(lines) - 1, -1, -1):
        line = lines[idx]
        civilite_match = _NAME_WITH_CIVILITE_RE.search(line)
        if civilite_match:
            candidate = _clean_name_candidate(civilite_match.group(1))
            if _is_probable_person_name(candidate):
                return candidate, idx, None, line

        compact = _clean_name_candidate(line)
        if _NAME_UPPER_RE.fullmatch(compact) and _is_probable_person_name(compact):
            return compact, idx, None, line

    return "", None, None, ""


def _extract_fonction_from_context(lines: List[str], pivot_idx: Optional[int]) -> str:
    if not lines:
        return ""

    end = pivot_idx if isinstance(pivot_idx, int) and pivot_idx >= 0 else len(lines)
    start = max(0, end - 8)
    candidates: List[str] = []

    for idx in range(start, end):
        line = lines[idx].strip(" ,;:-")
        if not line:
            continue
        if _DATE_LINE_NORM_RE.search(_normalize_for_match(line)):
            continue
        if _looks_like_function_line(line):
            candidates.append(re.sub(r"\s+", " ", line).strip())

    if candidates:
        return candidates[-1]
    return ""


def _extract_signature_context(text: str) -> Dict[str, str]:
    zone = _signature_zone_lines(_prepare_lines(text), size=80)
    if not zone:
        return {"nom": "", "fonction": "", "ligne": ""}

    nom, name_idx, marker_idx, source_line = _extract_name_near_signature(zone)
    pivot_idx = marker_idx if marker_idx is not None else name_idx
    fonction = _extract_fonction_from_context(zone, pivot_idx)

    if not source_line:
        if isinstance(name_idx, int) and 0 <= name_idx < len(zone):
            source_line = zone[name_idx]
        elif fonction:
            source_line = fonction

    return {
        "nom": nom,
        "fonction": fonction,
        "ligne": source_line,
    }


def extract_date_signature(text: str) -> str:
    cleaned = clean_ocr_text(text)
    match = _DATE_LINE_RE.search(cleaned)
    if match:
        return re.sub(r"\s+", " ", match.group(2)).strip()

    tail = "\n".join(_signature_zone_lines(_prepare_lines(text), size=80))
    fallback = _DATE_ONLY_RE.search(tail)
    if not fallback:
        return ""
    return re.sub(r"\s+", " ", fallback.group(1)).strip()


def extract_lieu_signature(text: str) -> str:
    match = _DATE_LINE_RE.search(clean_ocr_text(text))
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group(1)).strip(" ,:-")


def extract_fonction_signataire(text: str) -> str:
    return _extract_signature_context(text).get("fonction", "")


def extract_nom_signataire(text: str) -> str:
    return _extract_signature_context(text).get("nom", "")


def extract_signataire(text: str) -> Dict[str, str]:
    context = _extract_signature_context(text)
    nom = context.get("nom", "")
    fonction = context.get("fonction", "")
    date_signature = extract_date_signature(text)
    lieu_signature = extract_lieu_signature(text)
    source_line = context.get("ligne", "")

    return {
        "nom": nom,
        "fonction": fonction,
        "date_signature": date_signature,
        "lieu_signature": lieu_signature,
        "ligne": source_line,
    }

"""
Extraction de l'autorité émettrice.
Identifie le service, la direction ou l'administration à l'origine de l'acte.
"""

import re
from typing import Dict, List

from cleaner import clean_ocr_text

# Mots-clés désignant un service administratif
_EMITTER_HINTS_RE = re.compile(r"(?i)\b(?:PREFECTURE|DIRECTION|CABINET|SERVICE|MAIRIE|MINISTERE|AGENCE)\b")

# Regex pour capturer la fonction exacte en en-tête
_ROLE_HEADER_RE = re.compile(
    r"(?i)^\s*(?:LE|LA)\s+(PREFET(?:E)?|SOUS[-\s]?PREFET(?:E)?|DIRECTEUR(?:TRICE)?|MAIRE|PRESIDENT(?:E)?)\b"
)

_FUNCTION_PATTERNS = [
    re.compile(r"(?i)\b(?:LE|LA)\s+PREFET(?:E)?\b"),
    re.compile(r"(?i)\b(?:LE|LA)\s+SOUS[-\s]?PREFET(?:E)?\b"),
    re.compile(r"(?i)\b(?:LE|LA)\s+DIRECTEUR(?:TRICE)?\b"),
    re.compile(r"(?i)\b(?:LE|LA)\s+MAIRE\b"),
    re.compile(r"(?i)\b(?:LE|LA)\s+PRESIDENT(?:E)?\b"),
]

_DECISION_MARKERS_RE = re.compile(r"(?i)\b(?:ARRETE|DECIDE|ORDONNE|AUTORISE)\b")
_ARRETE_NUMBER_RE = re.compile(r"\b(?:\d{1,3}|2A|2B|R\d{2})-\d{4}-\d{2}-\d{2}-\d{5}\b", re.IGNORECASE)


def _normalize_line(value: str) -> str:
    """Nettoie la ligne des espaces multiples et de la ponctuation résiduelle."""
    return re.sub(r"\s+", " ", value).strip(" ,:-\t")


def _prepare_lines(text: str) -> List[str]:
    """Nettoie le texte via le module cleaner et le découpe en liste de lignes."""
    if not isinstance(text, str):
        return []
    cleaned = clean_ocr_text(text)
    return [_normalize_line(line) for line in cleaned.splitlines() if _normalize_line(line)]


def _prepare_raw_lines(text: str) -> List[str]:
    """Découpe le texte brut d'origine sans passer par le cleaner OCR."""
    if not isinstance(text, str):
        return []
    return [_normalize_line(line) for line in text.splitlines() if _normalize_line(line)]


def _extract_function(line: str) -> str:
    """Identifie le rôle figurant sur la ligne."""
    if re.search(r"(?i)\b(?:LE|LA)\s+PREFET(?:E)?\b", line):
        return "Préfet"
    if re.search(r"(?i)\b(?:LE|LA)\s+SOUS[-\s]?PREFET(?:E)?\b", line):
        return "Sous-préfet"
    if re.search(r"(?i)\b(?:LE|LA)\s+DIRECTEUR(?:TRICE)?\b", line):
        return "Directeur"
    if re.search(r"(?i)\b(?:LE|LA)\s+MAIRE\b", line):
        return "Maire"
    if re.search(r"(?i)\b(?:LE|LA)\s+PRESIDENT(?:E)?\b", line):
        return "Président"
    for pattern in _FUNCTION_PATTERNS:
        match = pattern.search(line)
        if match:
            return _normalize_line(match.group(0))
    return ""


def _smart_title(value: str) -> str:
    """Formate un texte en 'Title Case' en gérant les apostrophes."""
    words: List[str] = []
    for token in value.lower().split():
        if "'" in token:
            parts = token.split("'")
            parts = [part[:1].upper() + part[1:] if part else part for part in parts]
            words.append("'".join(parts))
        else:
            words.append(token[:1].upper() + token[1:] if token else token)
    text = " ".join(words)
    text = re.sub(r"(?i)\b(Du|De|Des|D')\b", lambda m: m.group(1).lower(), text)
    text = re.sub(r"(?i)\bL'", "l'", text)
    return text


def _extract_nom(line: str) -> str:
    """Récupère le nom de la personne, ou reformate la fonction + lieu."""
    role_place_match = re.search(
        r"(?i)^\s*(?:LE|LA)\s+(PREFET(?:E)?|SOUS[-\s]?PREFET(?:E)?|DIRECTEUR(?:TRICE)?|MAIRE|PRESIDENT(?:E)?)\s+(DE|DU|DES|D')\s+(.+)$",
        line.strip(" ,;:-"),
    )
    if role_place_match:
        role = _extract_function(line)
        preposition = role_place_match.group(2).lower()
        place = _smart_title(_normalize_line(role_place_match.group(3)))
        return f"{role} {preposition} {place}".strip()

    match = re.search(
        r"(?i)\b(?:M\.?|MME\.?|MONSIEUR|MADAME)\s+([A-Z][A-Za-zÀ-ÖØ-öø-ÿ' -]{1,})\b",
        line,
    )
    if not match:
        return ""
    return _normalize_line(match.group(1))


def _extract_service(line: str) -> str:
    """Retourne la ligne si elle contient un mot-clé de service."""
    if _EMITTER_HINTS_RE.search(line):
        return line
    return ""


def _extract_administration(line: str) -> str:
    """Isole le nom précis de l'administration sur la ligne."""
    direction_match = re.search(r"(?i)(DIRECTION\s+[^-]{8,})", line)
    if direction_match:
        value = _normalize_line(direction_match.group(1))
        # Suppression des numéros d'arrêtés inutiles
        value = re.sub(
            r"(?i)\s*-\s*(?:\d{1,3}|2A|2B|R\d{2})-\d{4}-\d{2}-\d{2}-\d{5}.*$",
            "",
            value,
        ).strip(" ,:-")
        value = re.sub(r"(?i)\b(?:ARRETE|DECIDE|ORDONNE|AUTORISE)\b.*$", "", value).strip(" ,:-")
        return value

    match = re.search(r"(?i)\b(?:DE|DU|DES|D')\s+(.+)$", line)
    if not match:
        return ""
    value = _normalize_line(match.group(1))
    value = re.sub(r"(?i)\b(?:ARRETE|DECIDE|ORDONNE|AUTORISE)\b.*$", "", value).strip(" ,:-")
    return value


def _extract_administration_from_lines(lines: List[str]) -> str:
    """Gère le recollement d'une administration scannée sur plusieurs lignes (OCR)."""
    limit = min(len(lines), 80)
    for idx in range(limit):
        value = _extract_administration(lines[idx])
        if not (value and re.search(r"(?i)\bDIRECTION\b", value)):
            continue

        # L'OCR coupe parfois l'administration sur la ligne suivante.
        # On vérifie si la ligne d'après commence par une préposition pour la recoller.
        j = idx + 1
        while j < limit:
            next_line = _normalize_line(lines[j])
            if not next_line:
                break
            if re.match(r"(?i)^(?:du|de|des|d'|et)\b", next_line):
                value = _normalize_line(f"{value} {next_line}")
                j += 1
                continue
            break
        return value
    return ""


def _build_candidates(lines: List[str]) -> List[Dict[str, object]]:
    """Évalue chaque ligne et attribue un score pour trouver l'autorité émettrice."""
    candidates: List[Dict[str, object]] = []
    total = len(lines)

    for idx, line in enumerate(lines):
        if "_" in line or re.match(r"^\d{2,}", line) or len(line) < 5:
            continue
        if _ARRETE_NUMBER_RE.search(line):
            continue

        fonction = _extract_function(line)
        has_service_hint = bool(_extract_service(line))
        has_decision_marker = bool(_DECISION_MARKERS_RE.search(line))

        if not fonction and not has_service_hint:
            continue

        score = 0
        if idx < 40:
            score += 3
        elif idx < 100:
            score += 1

        if has_service_hint:
            score += 3
        if fonction:
            score += 2
        if _ROLE_HEADER_RE.search(line):
            score += 6
        if has_decision_marker:
            score += 2

        near_lines = lines[max(0, idx - 2): min(total, idx + 3)]
        if any(_DECISION_MARKERS_RE.search(candidate) for candidate in near_lines):
            score += 2

        candidates.append({
            "index": idx,
            "score": score,
            "line": line,
        })

    return candidates


def extract_autorite_emettrice(text: str) -> Dict[str, str]:
    """Fonction principale d'extraction de l'autorité émettrice."""
    lines = _prepare_lines(text)
    raw_lines = _prepare_raw_lines(text)
    if not lines:
        return {"nom": "", "fonction": "", "service": "", "administration": "", "ligne": ""}

    candidates = _build_candidates(lines)
    if not candidates:
        return {"nom": "", "fonction": "", "service": "", "administration": "", "ligne": ""}

    # Sélection du meilleur candidat
    best = sorted(candidates, key=lambda item: (item["score"], -item["index"]), reverse=True)[0]
    line = str(best["line"])
    
    administration = _extract_administration_from_lines(lines)
    administration_raw = _extract_administration_from_lines(raw_lines)
    
    # On garde la version la plus longue
    if len(administration_raw) > len(administration):
        administration = administration_raw
    if not administration:
        administration = _extract_administration(line)

    return {
        "nom": _extract_nom(line),
        "fonction": _extract_function(line),
        "service": _extract_service(line),
        "administration": administration,
        "ligne": line,
    }
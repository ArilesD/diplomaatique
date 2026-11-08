"""
Extraction de l'autorité décisionnaire.
Identifie la personne ou l'entité qui prend la décision dans l'arrêté 
ainsi que son nom et l'institution associée.
"""

import re
from typing import Dict, List
from cleaner import clean_ocr_text

# Mots-clés indiquant l'action de décision
_DECISION_MARKERS = ("ARRETE", "DECIDE", "ORDONNE", "AUTORISE")

# Regex pour détecter les différentes fonctions administratives
_ROLE_PATTERNS = [
    ("prefet", re.compile(r"(?i)\b(?:LE|LA)\s+PREFET(?:E)?\b")),
    ("sous_prefet", re.compile(r"(?i)\b(?:LE|LA)\s+SOUS[-\s]?PREFET(?:E)?\b")),
    ("directeur", re.compile(r"(?i)\b(?:LE|LA)\s+DIRECTEUR(?:TRICE)?\b")),
    ("maire", re.compile(r"(?i)\b(?:LE|LA)\s+MAIRE\b")),
    ("president", re.compile(r"(?i)\b(?:LE|LA)\s+PRESIDENT(?:E)?\b")),
]

def _normalize_line(line: str) -> str:
    """Nettoie la ligne en supprimant les espaces en double et la ponctuation inutile."""
    return re.sub(r"\s+", " ", line).strip(" ,-:\t")

def _extract_name_from_line(line: str) -> str:
    """Recherche un nom propre précédé de civilités (M., Mme, Monsieur, Madame)."""
    match = re.search(
        r"(?i)\b(?:M\.?|MME\.?|MONSIEUR|MADAME)\s+([A-Z][A-ZÀ-ÖØ-Þ' -]{1,})\b",
        line,
    )
    if not match:
        return ""
    return _normalize_line(match.group(1))

def _extract_institution_from_line(line: str) -> str:
    """Isole l'institution en récupérant ce qui suit 'de', 'du', 'des', 'd' '."""
    match = re.search(r"(?i)\b(?:DE|DU|DES|D')\s+(.+)$", line)
    if not match:
        return ""
    value = _normalize_line(match.group(1))
    # Retire les verbes d'action s'ils se trouvent à la fin de la phrase
    value = re.sub(r"(?i)\b(?:ARRETE|DECIDE|ORDONNE)\b.*$", "", value).strip(" ,-:")
    return value

def _contains_decision_marker(line: str) -> bool:
    """Vérifie si la ligne contient l'un des verbes de décision."""
    upper = line.upper()
    return any(marker in upper for marker in _DECISION_MARKERS)

def _build_candidates(lines: List[str]) -> List[Dict[str, object]]:
    """
    Évalue chaque ligne du texte et lui attribue un score pour déterminer 
    laquelle a le plus de probabilité de contenir l'autorité décisionnaire.
    """
    candidates: List[Dict[str, object]] = []
    total = len(lines)

    for idx, raw in enumerate(lines):
        line = _normalize_line(raw)
        if not line:
            continue

        # Vérifie si un rôle connu est présent sur la ligne
        role = ""
        for role_name, pattern in _ROLE_PATTERNS:
            if pattern.search(line):
                role = role_name
                break

        if not role:
            continue

        score = 0
        # Gros bonus pour le tout début du document
        if idx < 20:
            score += 5
        elif idx < 40:
            score += 2
            
        # Gros malus si on est dans les articles finaux ou si on dépasse la moitié du document
        if re.match(r"(?i)^ARTICLE\s*\d+", line) or idx > total / 2:
            score -= 10

        # Bonus si on trouve un mot comme ARRETE sur la ligne
        if _contains_decision_marker(line):
            score += 4

        # Bonus si on trouve un marqueur de décision sur les lignes adjacentes
        nearby = lines[max(0, idx - 2) : min(total, idx + 4)]
        if any(_contains_decision_marker(window_line) for window_line in nearby):
            score += 3

        candidates.append({
            "index": idx,
            "score": score,
            "role": role,
            "line": line,
        })

    return candidates

def extract_autorite_decisionnaire(text: str) -> Dict[str, str]:
    """Retourne un dictionnaire contenant les infos extraites."""
    if not isinstance(text, str):
        return {"fonction": "", "nom": "", "institution": "", "ligne": ""}

    cleaned = clean_ocr_text(text)
    lines = cleaned.splitlines()
    candidates = _build_candidates(lines)

    if not candidates:
        return {"fonction": "", "nom": "", "institution": "", "ligne": ""}

    # Sélection de la ligne avec le meilleur score
    best = sorted(candidates, key=lambda item: (item["score"], -item["index"]), reverse=True)[0]
    line = str(best["line"])

    role_label_map = {
        "prefet": "prefet/prefete",
        "sous_prefet": "sous-prefet/sous-prefete",
        "directeur": "directeur/directrice",
        "maire": "maire",
        "president": "president/presidente",
    }
    fonction = role_label_map.get(str(best["role"]), "")

    return {
        "fonction": fonction,
        "nom": _extract_name_from_line(line),
        "institution": _extract_institution_from_line(line),
        "ligne": line,
    }
# je decris le module
"""Extraction robuste des voies et delais de recours."""

# je charge un module utile
from __future__ import annotations

# je charge un module utile
import re
# je charge un module utile
import unicodedata
# je charge un module utile
from typing import Dict, List, Optional, Tuple


# je prepare un motif de recherche
_SPACE_RE = re.compile(r"[ \t]+")
# je prepare un motif de recherche
_LINE_BREAK_RE = re.compile(r"\n{3,}")
# je prepare une variable
_MOJIBAKE_MARKERS = ("Ã", "Â", "â€™", "â€“", "â€œ", "â€", "�")

# je prepare un motif de recherche
_ARTICLE_START_RE = re.compile(
    # je garde cette ligne pour la logique
    r"(?i)^\s*article\s+(?:\d+|1er|premier|unique|[ivxlcdm]+)\b"
# je ferme ce bloc
)

# je prepare un motif de recherche
_SECTION_TITLE_RE = re.compile(
    # je garde cette ligne pour la logique
    r"(?i)\b(?:"
    # je garde cette ligne pour la logique
    r"voies?\s+et\s+delais?\s+de\s+recours|"
    # je garde cette ligne pour la logique
    r"delais?\s+et\s+voies?\s+de\s+recours|"
    # je garde cette ligne pour la logique
    r"voies?\s+de\s+recours|"
    # je garde cette ligne pour la logique
    r"delais?\s+de\s+recours"
    # je garde cette ligne pour la logique
    r")\b"
# je ferme ce bloc
)

# je prepare une variable
_STRONG_START_PATTERNS = [
    # je definis un motif de recherche
    re.compile(r"(?i)\bpeut\s+faire\s+l[' ]objet\s+d[' ]un\s+recours\b"),
    # je definis un motif de recherche
    re.compile(r"(?i)\ble\s+present\s+arrete.{0,140}?\brecours\b"),
    # je definis un motif de recherche
    re.compile(r"(?i)\brecours\s+devant\s+le\s+tribunal\s+administratif\b"),
    # je definis un motif de recherche
    re.compile(r"(?i)\btribunal\s+administratif\s+de\b"),
    # je garde cette ligne pour la logique
    _SECTION_TITLE_RE,
# je ferme ce bloc
]

# je prepare un motif de recherche
_SIGNAL_LINE_RE = re.compile(
    # je garde cette ligne pour la logique
    r"(?i)\b(?:"
    # je garde cette ligne pour la logique
    r"recours|"
    # je garde cette ligne pour la logique
    r"tribunal\s+administratif|"
    # je garde cette ligne pour la logique
    r"cour\s+administrative\s+d[' ]appel|"
    # je garde cette ligne pour la logique
    r"telerecours|"
    # je garde cette ligne pour la logique
    r"r\.?\s*421-?\s*1"
    # je garde cette ligne pour la logique
    r")\b"
# je ferme ce bloc
)

# je prepare un motif de recherche
_END_LINE_RE = re.compile(
    # je garde cette ligne pour la logique
    r"(?i)^\s*(?:"
    # je garde cette ligne pour la logique
    r"article\s+(?:\d+|1er|premier|unique|[ivxlcdm]+)\b|"
    # je garde cette ligne pour la logique
    r"fait\s+a\b|"
    # je garde cette ligne pour la logique
    r"execution\b|"
    # je garde cette ligne pour la logique
    r"publication\b"
    # je garde cette ligne pour la logique
    r")"
# je ferme ce bloc
)

# je prepare un motif de recherche
_FOOTER_LINE_RE = re.compile(
    # je garde cette ligne pour la logique
    r"(?i)^\s*(?:"
    # je garde cette ligne pour la logique
    r"\d+\s*/\s*\d+|"
    # je garde cette ligne pour la logique
    r"\d{2}_[a-z]|"
    # je garde cette ligne pour la logique
    r".*site\s+internet.*|"
    # je garde cette ligne pour la logique
    r".*twitter.*|"
    # je garde cette ligne pour la logique
    r".*telephone.*|"
    # je garde cette ligne pour la logique
    r".*cedex.*"
    # je garde cette ligne pour la logique
    r")"
# je ferme ce bloc
)

# je prepare une variable
_VOIE_PATTERNS = {
    # je garde cette ligne pour la logique
    "gracieux": re.compile(r"(?i)\brecours\s+gracieux\b"),
    # je garde cette ligne pour la logique
    "hierarchique": re.compile(r"(?i)\brecours\s+hierarchique\b"),
    # je garde cette ligne pour la logique
    "contentieux": re.compile(r"(?i)\brecours\s+contentieux\b"),
# je ferme ce bloc
}

# je prepare une variable
_NUMBER_WORD = (
    # je garde cette ligne pour la logique
    r"(?:[0-9]+|un|une|deux|trois|quatre|cinq|six|sept|huit|neuf|dix|onze|douze|"
    # je garde cette ligne pour la logique
    r"treize|quatorze|quinze|seize|dix-sept|dix-huit|dix-neuf|vingt|trente|"
    # je garde cette ligne pour la logique
    r"quarante|cinquante|soixante)"
# je ferme ce bloc
)
# je prepare une variable
_UNIT = r"(?:jour|jours|mois|an|ans|heure|heures)"
# je prepare une variable
_DURATION = (
    # je garde cette ligne pour la logique
    rf"(?:{_NUMBER_WORD})(?:\s*(?:a|au|-)\s*(?:{_NUMBER_WORD}))?\s+{_UNIT}"
    # je garde cette ligne pour la logique
    r"(?:\s+francs?)?"
# je ferme ce bloc
)

# je prepare un motif de recherche
_DELAI_CONTEXT_RE = re.compile(
    # je garde cette ligne pour la logique
    r"(?i)\b(?:"
    # je garde cette ligne pour la logique
    r"recours|"
    # je garde cette ligne pour la logique
    r"tribunal|"
    # je garde cette ligne pour la logique
    r"juridiction|"
    # je garde cette ligne pour la logique
    r"saisi|"
    # je garde cette ligne pour la logique
    r"notification|"
    # je garde cette ligne pour la logique
    r"publication|"
    # je garde cette ligne pour la logique
    r"decision\s+implicite|"
    # je garde cette ligne pour la logique
    r"rejet\s+implicite|"
    # je garde cette ligne pour la logique
    r"telerecours|"
    # je garde cette ligne pour la logique
    r"r\.?\s*421-?\s*1"
    # je garde cette ligne pour la logique
    r")\b"
# je ferme ce bloc
)

# je prepare un motif de recherche
_BAD_DELAI_CONTEXT_RE = re.compile(
    # je garde cette ligne pour la logique
    r"(?i)\b(?:"
    # je garde cette ligne pour la logique
    r"paiement|"
    # je garde cette ligne pour la logique
    r"recouvrement|"
    # je garde cette ligne pour la logique
    r"fiscal|"
    # je garde cette ligne pour la logique
    r"gracieuses?|"
    # je garde cette ligne pour la logique
    r"penalites?|"
    # je garde cette ligne pour la logique
    r"somme|"
    # je garde cette ligne pour la logique
    r"montant|"
    # je garde cette ligne pour la logique
    r"euro|"
    # je garde cette ligne pour la logique
    r"euros|"
    # je garde cette ligne pour la logique
    r"impot|"
    # je garde cette ligne pour la logique
    r"taxe|"
    # je garde cette ligne pour la logique
    r"credit|"
    # je garde cette ligne pour la logique
    r"comptable"
    # je garde cette ligne pour la logique
    r")\b"
# je ferme ce bloc
)

# je prepare une variable
_DELAI_PATTERNS = [
    # je definis un motif de recherche
    re.compile(
        # je garde cette ligne pour la logique
        rf"(?i)\bdans\s+(?:un|le|les?)\s+delai\s+de\s+{_DURATION}\b"
        # je garde cette ligne pour la logique
        r"(?:[^.;:\n]{0,240})?"
    # je ferme ce bloc
    ),
    # je definis un motif de recherche
    re.compile(
        # je garde cette ligne pour la logique
        rf"(?i)\ble\s+delai\s+de\s+recours(?:\s+\w+)?\s+"
        # je garde cette ligne pour la logique
        rf"(?:est|sera|demeure|court)?\s*(?:de|d[' ]une?)?\s*{_DURATION}\b"
        # je garde cette ligne pour la logique
        r"(?:[^.;:\n]{0,220})?"
    # je ferme ce bloc
    ),
    # je definis un motif de recherche
    re.compile(
        # je garde cette ligne pour la logique
        rf"(?i)\bdans\s+les?\s+{_DURATION}\b"
        # je garde cette ligne pour la logique
        r"(?:[^.;:\n]{0,220}(?:a\s+compter|suivant|apres))?"
        # je garde cette ligne pour la logique
        r"(?:[^.;:\n]{0,120})?"
    # je ferme ce bloc
    ),
    # je definis un motif de recherche
    re.compile(
        # je garde cette ligne pour la logique
        rf"(?i)\b{_DURATION}\s+(?:a|au)\s+compter\s+de\s+[^.;:\n]{0,220}"
    # je ferme ce bloc
    ),
    # je definis un motif de recherche
    re.compile(
        # je garde cette ligne pour la logique
        rf"(?i)\b{_DURATION}\s+(?:suivant|suivants|apres)\s+[^.;:\n]{0,160}"
    # je ferme ce bloc
    ),
    # je definis un motif de recherche
    re.compile(
        # je garde cette ligne pour la logique
        rf"(?i)\bsous\s+{_DURATION}\b(?:[^.;:\n]{0,120})?"
    # je ferme ce bloc
    ),
    # je definis un motif de recherche
    re.compile(
        # je garde cette ligne pour la logique
        rf"(?i)\bsilence\s+garde[^.;:\n]{{0,140}}\bpendant\s+{_DURATION}\b"
        # je garde cette ligne pour la logique
        r"[^.;:\n]{0,180}\b(?:decision\s+implicite|rejet|acceptation)\b"
    # je ferme ce bloc
    ),
    # je definis un motif de recherche
    re.compile(
        # je garde cette ligne pour la logique
        rf"(?i)\brejet\s+implicite[^.;:\n]{{0,160}}\bau\s+terme\s+d[' ]un\s+"
        # je garde cette ligne pour la logique
        rf"delai\s+de\s+{_DURATION}\b(?:[^.;:\n]{{0,120}})?"
    # je ferme ce bloc
    ),
# je ferme ce bloc
]
# je prepare un motif de recherche
_DURATION_RE = re.compile(rf"(?i)\b{_DURATION}\b")

# je garde cette ligne pour la logique
_JURIDICTION_START_PATTERNS: List[Tuple[str, re.Pattern[str]]] = [
    # je garde cette ligne pour la logique
    ("tribunal administratif de", re.compile(r"(?i)\btribunal\s+administratif\s+de\s+")),
    # je garde cette ligne pour la logique
    (
        # je garde cette ligne pour la logique
        "cour administrative d'appel de",
        # je definis un motif de recherche
        re.compile(r"(?i)\bcour\s+administrative\s+d['’]appel\s+de\s+"),
    # je ferme ce bloc
    ),
# je ferme ce bloc
]

# je prepare une variable
_JURIDICTION_FALLBACKS = [
    # je definis un motif de recherche
    re.compile(r"(?i)\btribunal\s+administratif\b"),
    # je definis un motif de recherche
    re.compile(r"(?i)\bcour\s+administrative\s+d['’]appel\b"),
# je ferme ce bloc
]

# je prepare un motif de recherche
_TELERECOURS_PATTERN = re.compile(
    # je garde cette ligne pour la logique
    r"(?i)\b(?:telerecours(?:\s+citoyens?)?|www\.telerecours\.fr|citoyens\.telerecours\.fr)\b"
# je ferme ce bloc
)

# je prepare une variable
_BAD_JURI_TOKENS = {
    # je garde cette ligne pour la logique
    "prefecture",
    # je garde cette ligne pour la logique
    "notification",
    # je garde cette ligne pour la logique
    "publication",
    # je garde cette ligne pour la logique
    "code",
    # je garde cette ligne pour la logique
    "justice",
    # je garde cette ligne pour la logique
    "arrete",
    # je garde cette ligne pour la logique
    "present",
    # je garde cette ligne pour la logique
    "mois",
# je ferme ce bloc
}

# je prepare une variable
_JURI_BREAK_TOKENS = {
    # je garde cette ligne pour la logique
    "dans",
    # je garde cette ligne pour la logique
    "du",
    # je garde cette ligne pour la logique
    "de",
    # je garde cette ligne pour la logique
    "des",
    # je garde cette ligne pour la logique
    "a",
    # je garde cette ligne pour la logique
    "au",
    # je garde cette ligne pour la logique
    "aux",
    # je garde cette ligne pour la logique
    "ou",
    # je garde cette ligne pour la logique
    "et",
    # je garde cette ligne pour la logique
    "suivant",
    # je garde cette ligne pour la logique
    "compter",
    # je garde cette ligne pour la logique
    "conformement",
    # je garde cette ligne pour la logique
    "article",
    # je garde cette ligne pour la logique
    "code",
    # je garde cette ligne pour la logique
    "justice",
    # je garde cette ligne pour la logique
    "administrative",
    # je garde cette ligne pour la logique
    "site",
    # je garde cette ligne pour la logique
    "internet",
    # je garde cette ligne pour la logique
    "www",
    # je garde cette ligne pour la logique
    "telerecours",
# je ferme ce bloc
}


# je cree la fonction _strip_accents
def _strip_accents(text: str) -> str:
    # je renvoie le resultat
    return "".join(
        # je garde cette ligne pour la logique
        ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch)
    # je ferme ce bloc
    )


# je cree la fonction _normalize_for_match
def _normalize_for_match(text: str) -> str:
    # je prepare une variable
    normalized = text.replace("\u00a0", " ")
    # je prepare une variable
    normalized = normalized.replace("’", "'").replace("‘", "'").replace("`", "'")
    # je prepare une variable
    normalized = normalized.replace("–", "-").replace("—", "-").replace("−", "-")
    # je renvoie le resultat
    return _strip_accents(normalized).lower()


# je cree la fonction _repair_mojibake
def _repair_mojibake(text: str) -> str:
    # je verifie une condition
    if not any(marker in text for marker in _MOJIBAKE_MARKERS):
        # je renvoie le resultat
        return text
    # je tente une operation
    try:
        # je prepare une variable
        repaired = text.encode("latin-1").decode("utf-8")
    # je gere une erreur possible
    except (UnicodeEncodeError, UnicodeDecodeError):
        # je renvoie le resultat
        return text
    # je verifie une condition
    if repaired.count("�") > text.count("�"):
        # je renvoie le resultat
        return text
    # je renvoie le resultat
    return repaired


# je cree la fonction _clean_text
def _clean_text(text: str) -> str:
    # je prepare une variable
    cleaned = _repair_mojibake(text or "")
    # je prepare une variable
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    # je prepare une variable
    cleaned = cleaned.replace("\u00a0", " ")
    # je prepare une variable
    cleaned = _SPACE_RE.sub(" ", cleaned)
    # je prepare une variable
    cleaned = _LINE_BREAK_RE.sub("\n\n", cleaned)
    # je renvoie le resultat
    return cleaned.strip()


# je cree la fonction _strip_footer_noise
def _strip_footer_noise(section: str) -> str:
    # je garde cette ligne pour la logique
    kept: List[str] = []
    # je parcours des elements
    for raw in section.splitlines():
        # je prepare une variable
        line = raw.strip()
        # je verifie une condition
        if not line:
            # je garde cette ligne pour la logique
            continue
        # je verifie une condition
        if _FOOTER_LINE_RE.match(_normalize_for_match(line)):
            # je garde cette ligne pour la logique
            break
        # je garde cette ligne pour la logique
        kept.append(line)
    # je renvoie le resultat
    return "\n".join(kept).strip()


# je cree la fonction _make_window_candidate
def _make_window_candidate(lines: List[str], start_idx: int, max_lines: int = 16) -> str:
    # je garde cette ligne pour la logique
    selected: List[str] = []
    # je parcours des elements
    for idx in range(start_idx, min(len(lines), start_idx + max_lines)):
        # je prepare une variable
        raw = lines[idx].strip()
        # je prepare une variable
        norm = _normalize_for_match(raw)
        # je verifie une condition
        if idx > start_idx and _END_LINE_RE.match(norm) and "recours" not in norm:
            # je garde cette ligne pour la logique
            break
        # je verifie une condition
        if idx > start_idx and _FOOTER_LINE_RE.match(norm):
            # je garde cette ligne pour la logique
            break
        # je verifie une condition
        if raw:
            # je garde cette ligne pour la logique
            selected.append(raw)
    # je renvoie le resultat
    return _strip_footer_noise("\n".join(selected).strip())


# je cree la fonction _collect_article_ranges
def _collect_article_ranges(lines: List[str]) -> List[Tuple[int, int]]:
    # je garde cette ligne pour la logique
    starts: List[int] = []
    # je parcours des elements
    for idx, line in enumerate(lines):
        # je verifie une condition
        if _ARTICLE_START_RE.match(_normalize_for_match(line)):
            # je garde cette ligne pour la logique
            starts.append(idx)
    # je verifie une condition
    if not starts:
        # je renvoie le resultat
        return []
    # je garde cette ligne pour la logique
    ranges: List[Tuple[int, int]] = []
    # je parcours des elements
    for i, start in enumerate(starts):
        # je prepare une variable
        end = starts[i + 1] if i + 1 < len(starts) else len(lines)
        # je garde cette ligne pour la logique
        ranges.append((start, end))
    # je renvoie le resultat
    return ranges


# je cree la fonction _extract_features
def _extract_features(section: str) -> Dict[str, bool]:
    # je prepare une variable
    norm = _normalize_for_match(section)
    # je renvoie le resultat
    return {
        # je garde cette ligne pour la logique
        "has_recours": "recours" in norm,
        # je garde cette ligne pour la logique
        "has_title": bool(_SECTION_TITLE_RE.search(norm)),
        # je garde cette ligne pour la logique
        "has_objet_recours": bool(
            # je garde cette ligne pour la logique
            re.search(r"\bpeut\s+faire\s+l[' ]objet\s+d[' ]un\s+recours\b", norm)
        # je ferme ce bloc
        ),
        # je garde cette ligne pour la logique
        "has_present_arrete": "present arrete" in norm,
        # je garde cette ligne pour la logique
        "has_tribunal": "tribunal administratif" in norm
        # je garde cette ligne pour la logique
        or "cour administrative d'appel" in norm,
        # je garde cette ligne pour la logique
        "has_delai": "delai" in norm
        # je garde cette ligne pour la logique
        or bool(re.search(rf"\b(?:{_NUMBER_WORD})\s+{_UNIT}\b", norm)),
        # je garde cette ligne pour la logique
        "has_notification_pub": "notification" in norm or "publication" in norm,
        # je garde cette ligne pour la logique
        "has_telerecours": "telerecours" in norm,
        # je garde cette ligne pour la logique
        "has_r421": bool(re.search(r"\br\.?\s*421-?\s*1\b", norm)),
        # je garde cette ligne pour la logique
        "has_gracieux": "recours gracieux" in norm,
        # je garde cette ligne pour la logique
        "has_hierarchique": "recours hierarchique" in norm,
        # je garde cette ligne pour la logique
        "has_contentieux": "recours contentieux" in norm,
        # je garde cette ligne pour la logique
        "looks_table_noise": bool(
            # je garde cette ligne pour la logique
            re.search(r"\b[a-z]\.\s*\d{2,3}-\d+\b.*\bx\b", norm)
            # je garde cette ligne pour la logique
            or re.search(r"\bx\s+x\b", norm)
        # je ferme ce bloc
        ),
    # je ferme ce bloc
    }


# je cree la fonction _score_candidate
def _score_candidate(section: str) -> int:
    # je prepare une variable
    norm = _normalize_for_match(section)
    # je prepare une variable
    f = _extract_features(section)
    # je prepare une variable
    score = 0
    # je verifie une condition
    if f["has_title"]:
        # je garde cette ligne pour la logique
        score += 20
    # je verifie une condition
    if f["has_objet_recours"]:
        # je garde cette ligne pour la logique
        score += 18
    # je verifie une condition
    if f["has_present_arrete"] and f["has_recours"]:
        # je garde cette ligne pour la logique
        score += 12
    # je verifie une condition
    if f["has_tribunal"]:
        # je garde cette ligne pour la logique
        score += 14
    # je verifie une condition
    if f["has_delai"]:
        # je garde cette ligne pour la logique
        score += 8
    # je verifie une condition
    if f["has_notification_pub"]:
        # je garde cette ligne pour la logique
        score += 4
    # je verifie une condition
    if f["has_telerecours"]:
        # je garde cette ligne pour la logique
        score += 4
    # je verifie une condition
    if f["has_r421"]:
        # je garde cette ligne pour la logique
        score += 3
    # je garde cette ligne pour la logique
    score += min(norm.count("recours"), 4) * 2

    # je verifie une condition
    if f["has_gracieux"] and not f["has_tribunal"] and not f["has_delai"] and not f["has_objet_recours"]:
        # je garde cette ligne pour la logique
        score -= 14
    # je verifie une condition
    if f["looks_table_noise"]:
        # je garde cette ligne pour la logique
        score -= 8
    # je verifie une condition
    if len(norm) < 40:
        # je garde cette ligne pour la logique
        score -= 10
    # je renvoie le resultat
    return score


# je cree la fonction _is_valid_candidate
def _is_valid_candidate(section: str, score: int) -> bool:
    # je prepare une variable
    f = _extract_features(section)
    # je prepare une variable
    strong = (
        # je garde cette ligne pour la logique
        f["has_title"]
        # je garde cette ligne pour la logique
        or f["has_objet_recours"]
        # je garde cette ligne pour la logique
        or (f["has_tribunal"] and (f["has_delai"] or f["has_telerecours"] or f["has_notification_pub"]))
        # je garde cette ligne pour la logique
        or (f["has_present_arrete"] and f["has_recours"] and f["has_delai"])
    # je ferme ce bloc
    )
    # je verifie une condition
    if not strong:
        # je renvoie le resultat
        return False
    # je renvoie le resultat
    return score >= 12


# je cree la fonction _extract_section
def _extract_section(text: str) -> Optional[str]:
    # je prepare une variable
    lines = text.splitlines()
    # je verifie une condition
    if not lines:
        # je renvoie le resultat
        return None

    # je garde cette ligne pour la logique
    candidates: List[str] = []

    # 1) Candidats forts: lignes qui ressemblent explicitement a la clause de recours.
    # je parcours des elements
    for idx, line in enumerate(lines):
        # je prepare une variable
        norm = _normalize_for_match(line)
        # je prepare une variable
        next_norm = _normalize_for_match(lines[idx + 1]) if idx + 1 < len(lines) else ""
        # je prepare une variable
        window = f"{norm} {next_norm}".strip()
        # je verifie une condition
        if any(pattern.search(window) for pattern in _STRONG_START_PATTERNS):
            # je garde cette ligne pour la logique
            candidates.append(_make_window_candidate(lines, max(0, idx - 1), max_lines=18))

    # 2) Candidats article-entier: utile si la clause est englobee dans ARTICLE X.
    # je parcours des elements
    for start, end in _collect_article_ranges(lines):
        # je prepare une variable
        article_text = "\n".join(line.strip() for line in lines[start:end] if line.strip())
        # je prepare une variable
        norm = _normalize_for_match(article_text)
        # je verifie une condition
        if _SIGNAL_LINE_RE.search(norm):
            # je garde cette ligne pour la logique
            candidates.append(_strip_footer_noise(article_text))

    # 3) Fallback fenetres autour des lignes signales.
    # je verifie une condition
    if not candidates:
        # je parcours des elements
        for idx, line in enumerate(lines):
            # je verifie une condition
            if _SIGNAL_LINE_RE.search(_normalize_for_match(line)):
                # je garde cette ligne pour la logique
                candidates.append(_make_window_candidate(lines, max(0, idx - 2), max_lines=14))

    # je verifie une condition
    if not candidates:
        # je renvoie le resultat
        return None

    # Dedoublonnage simple tout en gardant l'ordre.
    # je garde cette ligne pour la logique
    deduped: List[str] = []
    # je prepare une variable
    seen = set()
    # je parcours des elements
    for section in candidates:
        # je prepare une variable
        key = _normalize_for_match(section)
        # je verifie une condition
        if not key or key in seen:
            # je garde cette ligne pour la logique
            continue
        # je garde cette ligne pour la logique
        seen.add(key)
        # je garde cette ligne pour la logique
        deduped.append(section)

    # je garde cette ligne pour la logique
    best_section: Optional[str] = None
    # je prepare une variable
    best_score = -10_000
    # je parcours des elements
    for section in deduped:
        # je prepare une variable
        score = _score_candidate(section)
        # je verifie une condition
        if score > best_score:
            # je prepare une variable
            best_score = score
            # je prepare une variable
            best_section = section

    # je verifie une condition
    if not best_section:
        # je renvoie le resultat
        return None
    # je verifie une condition
    if not _is_valid_candidate(best_section, best_score):
        # je renvoie le resultat
        return None
    # je renvoie le resultat
    return best_section


# je cree la fonction _extract_voies
def _extract_voies(section: str) -> List[str]:
    # je garde cette ligne pour la logique
    voies: List[str] = []
    # je prepare une variable
    norm = _normalize_for_match(section)
    # je parcours des elements
    for voie, pattern in _VOIE_PATTERNS.items():
        # je verifie une condition
        if pattern.search(norm):
            # je garde cette ligne pour la logique
            voies.append(voie)
    # je verifie une condition
    if not voies and re.search(r"\brecours\b", norm):
        # je garde cette ligne pour la logique
        voies.append("contentieux")
    # je renvoie le resultat
    return voies


# je cree la fonction _cleanup_phrase
def _cleanup_phrase(text: str) -> str:
    # je prepare une variable
    phrase = text.strip(" .;:\n")
    # je prepare une variable
    phrase = re.sub(r"\s+", " ", phrase).strip()
    # je prepare une variable
    phrase = re.split(
        # je garde cette ligne pour la logique
        r"(?i)\b(?:conformement|article\s+r|code\s+de\s+justice|"
        # je garde cette ligne pour la logique
        r"le\s+tribunal|www\.|telerecours|citoyens\.telerecours)\b",
        # je garde cette ligne pour la logique
        phrase,
        # je prepare une variable
        maxsplit=1,
    # je garde cette ligne pour la logique
    )[0].strip(" ,;:")
    # je prepare une variable
    phrase = re.sub(r"(?i)\b(de|du|des|la|le|les|a|au|aux)$", "", phrase).strip(" ,;:")
    # je renvoie le resultat
    return phrase


# je cree la fonction _delay_window_has_context
def _delay_window_has_context(window: str) -> bool:
    # je verifie une condition
    if not window:
        # je renvoie le resultat
        return False
    # je prepare une variable
    has_context = bool(_DELAI_CONTEXT_RE.search(window))
    # je verifie une condition
    if not has_context:
        # je renvoie le resultat
        return False
    # je prepare une variable
    has_bad_context = bool(_BAD_DELAI_CONTEXT_RE.search(window))
    # je verifie une condition
    if not has_bad_context:
        # je renvoie le resultat
        return True
    # Si on voit des mots "metier" (paiement/fiscal), on exige des marqueurs recours forts.
    # je renvoie le resultat
    return bool(
        # je garde cette ligne pour la logique
        re.search(
            # je garde cette ligne pour la logique
            r"(?i)\b(?:recours|tribunal|juridiction|notification|publication|"
            # je garde cette ligne pour la logique
            r"decision\s+implicite|rejet\s+implicite|telerecours|r\.?\s*421-?\s*1)\b",
            # je garde cette ligne pour la logique
            window,
        # je ferme ce bloc
        )
    # je ferme ce bloc
    )


# je cree la fonction _extract_delais
def _extract_delais(section: str) -> List[str]:
    # je prepare une variable
    norm = _normalize_for_match(section)
    # je garde cette ligne pour la logique
    raw_results: List[str] = []
    # je prepare une variable
    seen = set()
    # je parcours des elements
    for pattern in _DELAI_PATTERNS:
        # je parcours des elements
        for match in pattern.finditer(norm):
            # je prepare une variable
            candidate = _cleanup_phrase(match.group(0))
            # je verifie une condition
            if not candidate:
                # je garde cette ligne pour la logique
                continue
            # je verifie une condition
            if not _DURATION_RE.search(candidate):
                # je garde cette ligne pour la logique
                continue

            # Controle contextuel dans un voisinage pour limiter les faux positifs.
            # je prepare une variable
            window_start = max(0, match.start() - 120)
            # je prepare une variable
            window_end = min(len(norm), match.end() + 120)
            # je prepare une variable
            window = norm[window_start:window_end]
            # je verifie une condition
            if not _delay_window_has_context(window):
                # je garde cette ligne pour la logique
                continue

            # je prepare une variable
            candidate = re.sub(r"\s+", " ", candidate).strip(" ,;:")
            # je verifie une condition
            if len(candidate) < 10:
                # je garde cette ligne pour la logique
                continue
            # je prepare une variable
            key = candidate.lower()
            # je verifie une condition
            if key in seen:
                # je garde cette ligne pour la logique
                continue
            # je garde cette ligne pour la logique
            seen.add(key)
            # je garde cette ligne pour la logique
            raw_results.append(candidate)

    # je garde cette ligne pour la logique
    results: List[str] = []
    # je parcours des elements
    for candidate in sorted(raw_results, key=len, reverse=True):
        # je verifie une condition
        if any(candidate in kept for kept in results):
            # je garde cette ligne pour la logique
            continue
        # je garde cette ligne pour la logique
        results.append(candidate)
    # je renvoie le resultat
    return results


# je cree la fonction _is_bad_jurisdiction_place
def _is_bad_jurisdiction_place(place: str) -> bool:
    # je prepare une variable
    tokens = set(_normalize_for_match(place).split())
    # je renvoie le resultat
    return bool(tokens & _BAD_JURI_TOKENS)


# je cree la fonction _extract_place_from_tail
def _extract_place_from_tail(tail: str) -> str:
    # je prepare une variable
    cleaned_tail = tail.replace("\n", " ")
    # je prepare une variable
    cleaned_tail = re.sub(r"\s+", " ", cleaned_tail).strip()
    # je prepare une variable
    cleaned_tail = re.sub(r"(?i)^(?:la|le|les|l')\s+", "", cleaned_tail)

    # je garde cette ligne pour la logique
    place_tokens: List[str] = []
    # je parcours des elements
    for raw_token in cleaned_tail.split(" "):
        # je prepare une variable
        token = raw_token.strip(" ,.;:()[]{}\"'")
        # je verifie une condition
        if not token:
            # je garde cette ligne pour la logique
            continue
        # je prepare une variable
        token_norm = _normalize_for_match(token)
        # je verifie une condition
        if token_norm in _JURI_BREAK_TOKENS and place_tokens:
            # je garde cette ligne pour la logique
            break
        # je verifie une condition
        if token_norm in _BAD_JURI_TOKENS:
            # je garde cette ligne pour la logique
            break
        # je verifie une condition
        if any(char.isdigit() for char in token):
            # je garde cette ligne pour la logique
            break
        # je verifie une condition
        if place_tokens and token[:1].islower():
            # je garde cette ligne pour la logique
            break
        # je garde cette ligne pour la logique
        place_tokens.append(token)
        # je verifie une condition
        if len(place_tokens) >= 4:
            # je garde cette ligne pour la logique
            break
    # je renvoie le resultat
    return " ".join(place_tokens).strip()


# je cree la fonction _extract_juridiction
def _extract_juridiction(section: str) -> Optional[str]:
    # je parcours des elements
    for prefix, pattern in _JURIDICTION_START_PATTERNS:
        # je parcours des elements
        for match in pattern.finditer(section):
            # je prepare une variable
            tail = section[match.end() : match.end() + 120]
            # je prepare une variable
            city = _extract_place_from_tail(tail)
            # je verifie une condition
            if not city or _is_bad_jurisdiction_place(city):
                # je garde cette ligne pour la logique
                continue
            # je renvoie le resultat
            return f"{prefix} {city}"

    # je parcours des elements
    for pattern in _JURIDICTION_FALLBACKS:
        # je prepare une variable
        fallback = pattern.search(section)
        # je verifie une condition
        if fallback:
            # je renvoie le resultat
            return fallback.group(0).strip()
    # je renvoie le resultat
    return None


# je cree la fonction _extract_mentions
def _extract_mentions(section: str) -> Dict[str, bool]:
    # je renvoie le resultat
    return {"telerecours": bool(_TELERECOURS_PATTERN.search(_normalize_for_match(section)))}


# je cree la fonction extract_voies_recours
def extract_voies_recours(text: str) -> Dict[str, object]:
    # je decris le module
    """Extrait les informations de recours depuis le texte d'un arrete."""
    # je prepare une variable
    cleaned = _clean_text(text or "")
    # je prepare une variable
    section = _extract_section(cleaned)
    # je verifie une condition
    if not section:
        # je renvoie le resultat
        return {
            # je garde cette ligne pour la logique
            "voiesRecours": [],
            # je garde cette ligne pour la logique
            "delaiRecours": [],
            # je garde cette ligne pour la logique
            "juridictionCompetente": None,
            # je garde cette ligne pour la logique
            "texteExplicatifRecours": None,
            # je garde cette ligne pour la logique
            "mentions": {"telerecours": False},
            # je garde cette ligne pour la logique
            "found": False,
        # je ferme ce bloc
        }

    # je renvoie le resultat
    return {
        # je garde cette ligne pour la logique
        "voiesRecours": _extract_voies(section),
        # je garde cette ligne pour la logique
        "delaiRecours": _extract_delais(section),
        # je garde cette ligne pour la logique
        "juridictionCompetente": _extract_juridiction(section),
        # je garde cette ligne pour la logique
        "texteExplicatifRecours": section,
        # je garde cette ligne pour la logique
        "mentions": _extract_mentions(section),
        # je garde cette ligne pour la logique
        "found": True,
    # je ferme ce bloc
    }


# je cree la fonction extract
def extract(text: str) -> Dict[str, object]:
    # je decris le module
    """Alias generique pour compatibilite pipeline."""
    # je renvoie le resultat
    return extract_voies_recours(text)

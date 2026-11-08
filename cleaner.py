import json
import os
import re
from typing import Dict, List


# Dans ce module, je nettoie le texte OCR d'un recueil RAA.
# Mon objectif est simple: je reduis le bruit sans casser la structure juridique
# utile aux extracteurs (Vu, Considerant, Article, Fait a, Signe, Annexe).

_MOJIBAKE_REPLACEMENTS = {
    "NÂ°": "N°",
    "nÂ°": "n°",
    "nÂº": "n°",
    "PUBLIÃ‰": "PUBLIE",
    "publiÃ©": "publie",
    "ARRÃŠTÃ‰": "ARRETE",
    "PRÃ‰FECTORAL": "PREFECTORAL",
    "PRÃ‰FET": "PREFET",
    "PRÃ‰FÃˆTE": "PREFETE",
    "CONSIDÃ‰RANT": "CONSIDERANT",
    "Fait Ã ": "Fait a ",
    "â€“": "-",
    "â€”": "-",
}

# Indices frequents des en-tetes/pieds de page repetes.
_HEADER_FOOTER_HINT_RE = re.compile(
    r"(?i)\b(?:page\s+\d+|prefecture|recueil\s+des\s+actes|www\.|@|courrier|cedex)\b"
)
# Forme classique d'un numero d'arrete.
_ARRETE_NUMBER_RE = re.compile(
    r"\b(?:\d{1,3}|2A|2B|R\d{2})-\d{4}-\d{2}-\d{2}-\d{5}\b",
    re.IGNORECASE,
)
_STRONG_HEADER_FOOTER_RE = re.compile(
    r"(?i)(?:^\d{2}_pref_|libert[eé]\s*egalit[eé]\s*fraternit[eé]|"
    r"\b(?:t[ée]l\.?|site internet|facebook|@prefet|www\.)\b|"
    r"\bquartier\b.*\bcs\s*\d+\b)"
)
_LEGAL_CONTENT_RE = re.compile(
    r"(?i)\b(?:vu|considerant|considérant|article|arr[eê]t[eé]|"
    r"decide|d[ée]cide|fait\s+a|signe|annexe)\b"
)
_PAGE_MARKER_RE = re.compile(r"(?i)\bpage\s+\d+\b")
_TRAILING_PAGE_NUMBER_RE = re.compile(r".+\s\d{1,3}\s*$")


def _line_repeat_key(line: str) -> str:
    # Cree une cle de comparaison stable pour detecter les repetitions inter-pages.
    key = line.strip().lower()
    key = re.sub(r"\s+", " ", key)
    key = re.sub(r"(?i)\bpage\s+\d+\b", "", key)
    key = re.sub(r"\s+\d{1,3}$", "", key)
    return key.strip(" -:|")


def _fix_mojibake(text: str) -> str:
    # Ici, je corrige les caracteres "casses" les plus frequents (problemes d'encodage OCR).
    fixed = text
    for broken, repaired in _MOJIBAKE_REPLACEMENTS.items():
        fixed = fixed.replace(broken, repaired)

    # Ensuite, je tente une reparation generique s'il reste du mojibake.
    if any(marker in fixed for marker in ("Ã", "Â", "â")):
        try:
            repaired = fixed.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            repaired = fixed
        else:
            if repaired.count("�") <= fixed.count("�"):
                fixed = repaired
    return fixed


def _normalize_legal_markers(text: str) -> str:
    # Met les mots juridiques cles dans une forme stable pour les detecter plus facilement.
    normalized = text
    replacements = {
        r"(?i)\bART[Il1]CLE\b": "ARTICLE",
        r"(?i)\bCONSID[EÉ]?RANT\b": "CONSIDERANT",
        r"(?i)\bARR[EÉ]T[EÉ]\b": "ARRETE",
        r"(?i)\bD[ÉE]CIDE\b": "DECIDE",
    }
    for pattern, replacement in replacements.items():
        normalized = re.sub(pattern, replacement, normalized)
    return normalized


def _drop_repetitive_noise(lines: List[str]) -> List[str]:
    # Retire les en-tetes/pieds et les lignes qui se repetent entre plusieurs pages.
    counts: Dict[str, int] = {}
    for line in lines:
        stripped = line.strip()
        if stripped:
            key = _line_repeat_key(stripped)
            if key:
                counts[key] = counts.get(key, 0) + 1

    filtered: List[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            filtered.append(line)
            continue

        key = _line_repeat_key(stripped)
        repeated = counts.get(key, 0) >= 2 if key else False
        very_repeated = counts.get(key, 0) >= 3 if key else False

        strong_header_footer = bool(_STRONG_HEADER_FOOTER_RE.search(stripped))
        looks_like_header_footer = bool(
            _HEADER_FOOTER_HINT_RE.search(stripped)
            or _ARRETE_NUMBER_RE.search(stripped)
        )
        has_page_marker = bool(
            _PAGE_MARKER_RE.search(stripped)
            or _TRAILING_PAGE_NUMBER_RE.match(stripped)
        )
        looks_legal = bool(_LEGAL_CONTENT_RE.search(stripped))

        if strong_header_footer:
            continue
        if repeated and not looks_legal and (looks_like_header_footer or has_page_marker):
            continue
        if very_repeated and not looks_legal and len(key) >= 8:
            continue

        filtered.append(line)
    return filtered


def _merge_hyphenated_lines(lines: List[str]) -> List[str]:
    # Recoller les mots coupes en fin de ligne par OCR: "auto-" + "risation".
    merged: List[str] = []
    i = 0
    while i < len(lines):
        current = lines[i]
        if i + 1 < len(lines):
            nxt = lines[i + 1]
            if current.rstrip().endswith("-") and re.match(r"^[a-zà-öø-ÿ]", nxt.strip()):
                merged.append(current.rstrip()[:-1] + nxt.lstrip())
                i += 2
                continue
        merged.append(current)
        i += 1
    return merged


def clean_ocr_text(text: str) -> str:
    # C'est mon pipeline principal de nettoyage utilise partout dans le projet.
    if not isinstance(text, str):
        return ""

    # 1) Je repare l'encodage puis j'uniformise les mots juridiques.
    cleaned = _fix_mojibake(text)
    cleaned = _normalize_legal_markers(cleaned)

    # 2) Je fais un nettoyage technique: BOM, retours ligne, espaces speciaux, tabulations.
    cleaned = cleaned.replace("\ufeff", "")
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = cleaned.replace("\u00a0", " ").replace("\t", " ")

    # 3) Je remplace les variantes de tirets par un tiret simple.
    for dash in ("\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2212"):
        cleaned = cleaned.replace(dash, "-")

    # 4) Je filtre le bruit et je recolle les mots coupes.
    lines = cleaned.split("\n")
    lines = _drop_repetitive_noise(lines)
    lines = _merge_hyphenated_lines(lines)

    normalized_lines: List[str] = []
    previous_blank = False
    for raw_line in lines:
        # Normalise les espaces sans casser la structure du texte.
        line = re.sub(r"[ \t]+", " ", raw_line).strip()
        if not line:
            # Garde au maximum une ligne vide consecutive.
            if not previous_blank:
                normalized_lines.append("")
            previous_blank = True
            continue

        # Supprime les numeros de page seuls (ex: "12").
        if re.fullmatch(r"\d{1,3}", line):
            continue

        normalized_lines.append(line)
        previous_blank = False

    return "\n".join(normalized_lines).strip()


# Fonctions historiques conservees pour compatibilite.
def extract_numero_raa(text: str) -> str:
    # Version legacy: lit le numero de recueil si present.
    cleaned = clean_ocr_text(text)
    match = re.search(
        r"N(?:\s*[\u00b0\u00bao])?\s*((?:\d{1,3}|2A|2B|R\d{2})-\d{4}-\d{3})",
        cleaned,
        re.IGNORECASE,
    )
    return match.group(1) if match else "Inconnu"


def extract_publication_date(text: str) -> str:
    # Version legacy: essaie plusieurs motifs pour trouver la date de publication.
    cleaned = clean_ocr_text(text)
    motifs = [
        r"publi[eé] le\s+(\d{1,2} [A-ZÉÈÊËÎÂÔÛÙÜÇ]{3,20} \d{4})",
        r"(\d{1,2} [A-ZÉÈÊËÎÂÔÛÙÜÇ]{3,20} \d{4})\s*[-]\s*n(?:\s*[\u00b0\u00ba])?\s*\d{1,3}-\d{4}-\d{3}",
        r"recueil.{0,20}(\d{1,2} [A-ZÉÈÊËÎÂÔÛÙÜÇ]{3,20} \d{4})",
    ]
    for pattern in motifs:
        match = re.search(pattern, cleaned, re.IGNORECASE)
        if match:
            return match.group(1).strip().upper()
    return "Inconnue"


def detect_sommaire(text: str) -> bool:
    # Test simple: le mot "sommaire" existe-t-il dans le texte nettoye ?
    return "sommaire" in clean_ocr_text(text).lower()


def _extract_titles_for_legacy(text: str) -> List[Dict[str, str]]:
    # Heuristique legacy: construit des titres courts a partir des blocs ARRETE.
    lines = clean_ocr_text(text).splitlines()
    arretes: List[Dict[str, str]] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if re.match(r"^(ARRETE|ARRETE PREFECTORAL)", line.upper()):
            block = [line]
            j = i + 1
            while j < min(i + 10, len(lines)):
                candidate = lines[j].strip()
                if any(
                    keyword in candidate.upper()
                    for keyword in ("LA PREFETE", "LE PREFET", "SIGNE", "FAIT A", "VU", "ARTICLE")
                ):
                    break
                block.append(candidate)
                j += 1
            title = re.sub(r"\s+", " ", " ".join(block)).strip()
            if title:
                arretes.append({"titre": title, "source": "texte"})
            i = j
            continue
        i += 1
    return arretes


def process_file(filepath: str, prefecture: str):
    # Traite un fichier .txt et renvoie un resume JSON-friendly.
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    cleaned_text = clean_ocr_text(text)
    legacy_titles = _extract_titles_for_legacy(cleaned_text)
    return {
        "fichier": os.path.basename(filepath),
        "prefecture": prefecture,
        "numero_raa": extract_numero_raa(cleaned_text),
        "date_publication": extract_publication_date(cleaned_text),
        "sommaire_present": detect_sommaire(cleaned_text),
        "nombre_arretes": len(legacy_titles),
        "arretes": legacy_titles,
    }


def process_prefecture_folder(pref: str) -> None:
    # Traite tous les fichiers d'une prefecture.
    folder = os.path.join("data", pref, "raa")
    if not os.path.isdir(folder):
        print("Dossier introuvable :", folder)
        return

    all_files = [os.path.join(folder, name) for name in os.listdir(folder) if name.lower().endswith(".txt")]
    results = [process_file(file_path, pref) for file_path in sorted(all_files)]

    output_file = f"{pref}_arretes.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"Fichier JSON genere : {output_file}")


def main() -> None:
    # Petit point d'entree interactif.
    pref_name = input("please enter the pref you want : ").strip()
    if pref_name:
        process_prefecture_folder(pref_name)


if __name__ == "__main__":
    main()

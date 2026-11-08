import re
from typing import Dict, List

from cleaner import clean_ocr_text


# Dans ce module, je regroupe toute la logique d'extraction des articles d'un arrete.
# Je gere le reperage des entetes, le decoupage en blocs, le contenu
# de chaque article et les sous-parties (listes / puces / sous-sections).

ARTICLE_START_RE = re.compile(
    r"""
    (?im)^\s*
        (
            (?:
            ART(?:ICLE|ICL|[Il1]CLE)
            \.?
        )
        \s*
        (?:
            \d+[A-Z]?
            (?!\s*\.\s*\d)
            (?:\s+(?:BIS|TER|QUATER|QUINQUIES))?
            |
            1ER|PREMIER|UNIQUE
            |
            [IVXLCDM]+
        )
        (?:\s*[-:.])?
    )
    """,
    re.VERBOSE,
)

ARTICLE_END_MARKER_RE = re.compile(
    r"(?im)^\s*(?:"
    r"FAIT\s+\S+|"
    r"SIGN\S*|"
    r"POUR\s+LE\s+PREFET|"
    r"VOIES?\s+ET\s+D\S*LAIS?\s+DE\s+RECOURS|"
    r"ANNEXE|"
    r"LE\s+PREFET|"
    r"LA\s+PREFETE"
    r")\b"
)

SUBPART_LINE_RE = re.compile(
    r"(?im)^\s*([A-Z]\)|\d+\)|\d+°|[-*])\s+(.*)$"
)


def _prepare_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    cleaned = clean_ocr_text(text)
    cleaned = re.sub(r"(?i)\bART[Il1]CLE\b", "ARTICLE", cleaned)
    cleaned = re.sub(r"(?i)\bART\.\s*", "ARTICLE ", cleaned)
    cleaned = re.sub(r"(?i)\bARTICLE\s+IER\b", "ARTICLE 1ER", cleaned)
    return cleaned


def _normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def find_article_headers(text: str) -> List[Dict[str, int]]:
    # Ici, je releve tous les entetes d'articles detectes avec leur position.
    source = _prepare_text(text)
    headers: List[Dict[str, int]] = []
    for match in ARTICLE_START_RE.finditer(source):
        headers.append(
            {
                "start": match.start(),
                "end": match.end(),
                "header": _normalize_spaces(match.group(1)),
            }
        )
    return headers


def split_articles(text: str) -> List[Dict[str, str]]:
    # Ici, je decoupe le document en blocs d'articles (entete + corps brut).
    source = _prepare_text(text)
    headers = find_article_headers(source)
    if not headers:
        return []

    blocks: List[Dict[str, str]] = []
    for idx, current in enumerate(headers):
        next_start = headers[idx + 1]["start"] if idx + 1 < len(headers) else len(source)
        chunk = source[current["start"]:next_start].strip()
        if not chunk:
            continue

        first_line, _, remainder = chunk.partition("\n")
        first_line_tail = first_line[current["end"] - current["start"]:].strip()
        if remainder:
            # Je coupe les marqueurs de fin seulement dans le "remainder"
            # pour eviter de supprimer un titre d'article valide sur la 1re ligne
            # (ex: "ARTICLE 8 : voies et delais de recours").
            trimmed_remainder = ARTICLE_END_MARKER_RE.split(remainder, maxsplit=1)[0].strip()
            body = f"{first_line_tail}\n{trimmed_remainder}" if first_line_tail else trimmed_remainder
        else:
            body = first_line_tail
        body = body.strip()
        body = re.sub(r"^[-:–—.]\s*", "", body)

        blocks.append(
            {
                "numero": current["header"],
                "raw_block": chunk,
                "body": body,
            }
        )

    return blocks


def split_alineas(article_body: str) -> List[str]:
    # Conserve les alineas ligne a ligne. Fallback sur decoupage phrase.
    if not article_body:
        return []

    lines = [line.strip() for line in article_body.splitlines() if line.strip()]
    if len(lines) > 1:
        return lines

    parts = [part.strip() for part in re.split(r"(?<=[.;:])\s+", article_body) if part.strip()]
    return parts if parts else [article_body.strip()]


def extract_subparts(article_body: str) -> List[Dict[str, str]]:
    # Extrait les sous-parties de type 1), a), 1°, -, *.
    subparts: List[Dict[str, str]] = []
    for line in article_body.splitlines():
        match = SUBPART_LINE_RE.match(line)
        if not match:
            continue
        label, content = match.groups()
        subparts.append(
            {
                "label": label.strip(),
                "contenu": _normalize_spaces(content),
            }
        )
    return subparts


def extract_articles(text: str) -> List[Dict[str, object]]:
    # Ici, je lance mon pipeline complet d'extraction des articles.
    blocks = split_articles(text)
    articles: List[Dict[str, object]] = []

    for block in blocks:
        body = block["body"].strip()
        numero = block["numero"].strip(" -:.")
        numero = re.sub(r"(?i)\b1E\b", "1ER", numero)
        articles.append(
            {
                "numero": numero,
                "contenu": _normalize_spaces(body),
            }
        )

    return _deduplicate_articles(articles)


def _deduplicate_articles(articles: List[Dict[str, object]]) -> List[Dict[str, object]]:
    # Ici, je fusionne les doublons de numero d'article en gardant le contenu utile.
    merged: List[Dict[str, object]] = []
    index_by_numero: Dict[str, int] = {}

    for article in articles:
        numero = str(article.get("numero", "")).strip()
        contenu = _normalize_spaces(str(article.get("contenu", "")))
        if not numero:
            continue

        if numero not in index_by_numero:
            index_by_numero[numero] = len(merged)
            merged.append({"numero": numero, "contenu": contenu})
            continue

        idx = index_by_numero[numero]
        existing = str(merged[idx].get("contenu", "")).strip()

        if not contenu:
            continue
        if not existing:
            merged[idx]["contenu"] = contenu
            continue
        if contenu == existing:
            continue
        if contenu in existing:
            continue
        if existing in contenu:
            merged[idx]["contenu"] = contenu
            continue

        # Deux contenus differents pour le meme numero: on les concatene.
        merged[idx]["contenu"] = f"{existing} {contenu}".strip()

    return merged

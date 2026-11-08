import re
from typing import Dict, List, Optional

from cleaner import clean_ocr_text

_ANNEX_START_RE = re.compile(
    r"(?im)^\s*(?:ANNEXE(?:S)?|PIECE\s+ANNEXE|DOCUMENT\s+ANNEXE)\b.*$"
)


def _prepare_lines(text: str) -> List[str]:
    if not isinstance(text, str):
        return []
    cleaned = clean_ocr_text(text)
    return cleaned.splitlines()


def find_annex_start_line(text: str) -> Optional[int]:
    # Retourne l'index de la premiere ligne d'annexe, sinon None.
    lines = _prepare_lines(text)
    for idx, line in enumerate(lines):
        if _ANNEX_START_RE.match(line.strip()):
            return idx
    return None


def has_annex(text: str) -> bool:
    # Indique rapidement si au moins une annexe existe.
    return find_annex_start_line(text) is not None


def extract_annex_text(text: str) -> str:
    # Extrait tout le texte a partir de la premiere annexe.
    lines = _prepare_lines(text)
    start = find_annex_start_line(text)
    if start is None:
        return ""
    return "\n".join(lines[start:]).strip()


def extract_annex_blocks(text: str) -> List[Dict[str, str]]:
    # Extrait chaque annexe en bloc separe.
    lines = _prepare_lines(text)
    if not lines:
        return []

    start_indexes: List[int] = []
    for idx, line in enumerate(lines):
        if _ANNEX_START_RE.match(line.strip()):
            start_indexes.append(idx)

    if not start_indexes:
        return []

    blocks: List[Dict[str, str]] = []
    for pos, start in enumerate(start_indexes):
        end = start_indexes[pos + 1] if pos + 1 < len(start_indexes) else len(lines)
        block_lines = [line for line in lines[start:end] if line.strip()]
        if not block_lines:
            continue
        title = block_lines[0].strip()
        content = "\n".join(block_lines[1:]).strip()
        blocks.append({"titre": title, "contenu": content})

    return blocks


def split_main_and_annex(text: str) -> Dict[str, str]:
    # Separe le corps principal de la premiere annexe trouvee.
    lines = _prepare_lines(text)
    start = find_annex_start_line(text)
    if start is None:
        main_text = "\n".join(lines).strip()
        return {"corps_principal": main_text, "annexe": ""}

    main_text = "\n".join(lines[:start]).strip()
    annex_text = "\n".join(lines[start:]).strip()
    return {"corps_principal": main_text, "annexe": annex_text}

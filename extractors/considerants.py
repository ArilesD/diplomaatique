import re
from typing import Dict, List, Optional
from cleaner import clean_ocr_text
_CONSIDERANT_START_RE = re.compile(r"(?im)^\s*CONSID\S*RANT(?:\s+QUE)?\b")
_CONSIDERANT_INLINE_SPLIT_RE = re.compile(r"(?i)(?=\bCONSID\S*RANT(?:\s+QUE)?\b)")
_CONSIDERANT_STOP_RE = re.compile(
    r"(?im)^\s*(?:ARTICLE\b|DECIDE\b|ARRETE\b|ORDONNE\b|FAIT\s+[A-Z])"
)

def _prepare_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    return clean_ocr_text(text)

def find_considerant_start_lines(text: str) -> List[int]:
    lines = _prepare_text(text).splitlines()
    indexes: List[int] = []
    for idx, line in enumerate(lines):
        if _CONSIDERANT_START_RE.match(line.strip()):
            indexes.append(idx)
    return indexes

def has_considerants(text: str) -> bool:
    # Indique si au moins un considerant est present.
    return len(find_considerant_start_lines(text)) > 0

def _line_has_considerant_token(line: str) -> bool:
    return bool(re.search(r"(?i)\bCONSID\S*RANT(?:\s+QUE)?\b", line))

def _collect_considerant_blocks(lines: List[str]) -> List[str]:
    blocks: List[str] = []
    current: List[str] = []
    in_considerant = False
    for raw in lines:
        line = raw.strip()
        if not line:
            if in_considerant and current:
                current.append("")
            continue
        if _CONSIDERANT_START_RE.match(line):
            if current:
                blocks.append(" ".join(part for part in current if part.strip()).strip())
            current = [line]
            in_considerant = True
            continue
        if in_considerant and _CONSIDERANT_STOP_RE.match(line):
            if current:
                blocks.append(" ".join(part for part in current if part.strip()).strip())
            current = []
            in_considerant = False
            continue
        if in_considerant:
            current.append(line)
    if current:
        blocks.append(" ".join(part for part in current if part.strip()).strip())
    return blocks

def extract_considerants(text: str) -> List[str]:
    # Extrait les considerants en liste de chaines, prêtes pour le JSON.
    prepared = _prepare_text(text)
    lines = prepared.splitlines()
    blocks = _collect_considerant_blocks(lines)
    if not blocks and re.search(r"(?i)\bCONSID\S*RANT\b", prepared):
        chunks = [chunk.strip() for chunk in _CONSIDERANT_INLINE_SPLIT_RE.split(prepared) if chunk.strip()]
        fallback: List[str] = []
        for chunk in chunks:
            if not _line_has_considerant_token(chunk):
                continue
            cleaned = _CONSIDERANT_STOP_RE.split(chunk, maxsplit=1)[0].strip()
            cleaned = re.sub(r"\s+", " ", cleaned).strip()
            if cleaned:
                fallback.append(cleaned)
        return fallback
    normalized: List[str] = []
    for block in blocks:
        cleaned = re.sub(r"\s+", " ", block).strip()
        if cleaned:
            normalized.append(cleaned)
    return normalized

def split_considerants_and_rest(text: str) -> Dict[str, str]:
    prepared = _prepare_text(text)
    lines = prepared.splitlines()
    starts = find_considerant_start_lines(prepared)
    if not starts:
        return {"avant_considerants": prepared, "considerants": "", "apres_considerants": ""}
    first_start = starts[0]
    stop_index: Optional[int] = None
    for idx in range(first_start + 1, len(lines)):
        if _CONSIDERANT_STOP_RE.match(lines[idx].strip()):
            stop_index = idx
            break
    before = "\n".join(lines[:first_start]).strip()
    if stop_index is None:
        cons_part = "\n".join(lines[first_start:]).strip()
        after = ""
    else:
        cons_part = "\n".join(lines[first_start:stop_index]).strip()
        after = "\n".join(lines[stop_index:]).strip()
    return {
        "avant_considerants": before,
        "considerants": cons_part,
        "apres_considerants": after,
    }
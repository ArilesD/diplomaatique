import re
from typing import Dict, List

from cleaner import clean_ocr_text


_VISA_START_RE = re.compile(r"(?im)^\s*VU\b")
_VISA_SPLIT_INLINE_RE = re.compile(r"(?i)(?=\bVU\b)")
_VISA_STOP_RE = re.compile(
    r"(?im)^\s*(?:CONSID\S*RANT\b|ARTICLE\b|DECIDE\b|ARRETE\b|ORDONNE\b|FAIT\s+[A-Z])"
)


def _prepare_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    return clean_ocr_text(text)


def find_visa_start_lines(text: str) -> List[int]:
    # Retourne les index des lignes qui commencent par "Vu".
    lines = _prepare_text(text).splitlines()
    indexes: List[int] = []
    for idx, line in enumerate(lines):
        if _VISA_START_RE.match(line.strip()):
            indexes.append(idx)
    return indexes


def has_visas(text: str) -> bool:
    return len(find_visa_start_lines(text)) > 0


def _collect_visa_blocks(lines: List[str]) -> List[str]:
    blocks: List[str] = []
    current: List[str] = []
    in_visa = False

    for raw in lines:
        line = raw.strip()
        if not line:
            if in_visa and current:
                current.append("")
            continue

        if _VISA_START_RE.match(line):
            if current:
                blocks.append(" ".join(part for part in current if part.strip()).strip())
            current = [line]
            in_visa = True
            continue

        if in_visa and _VISA_STOP_RE.match(line):
            if current:
                blocks.append(" ".join(part for part in current if part.strip()).strip())
            current = []
            in_visa = False
            continue

        if in_visa:
            current.append(line)

    if current:
        blocks.append(" ".join(part for part in current if part.strip()).strip())

    return blocks


def extract_visas(text: str) -> List[str]:
    prepared = _prepare_text(text)
    lines = prepared.splitlines()
    blocks = _collect_visa_blocks(lines)

    if not blocks and re.search(r"(?i)\bVU\b", prepared):
        chunks = [chunk.strip() for chunk in _VISA_SPLIT_INLINE_RE.split(prepared) if chunk.strip()]
        fallback: List[str] = []
        for chunk in chunks:
            if not re.search(r"(?i)^\s*VU\b", chunk):
                continue
            cleaned = _VISA_STOP_RE.split(chunk, maxsplit=1)[0].strip()
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


def split_visas_and_rest(text: str) -> Dict[str, str]:
    # Separe la zone des visas du reste du document.
    prepared = _prepare_text(text)
    lines = prepared.splitlines()
    starts = find_visa_start_lines(prepared)
    if not starts:
        return {"avant_visas": prepared, "visas": "", "apres_visas": ""}

    first_start = starts[0]
    stop_index = None
    for idx in range(first_start + 1, len(lines)):
        if _VISA_STOP_RE.match(lines[idx].strip()):
            stop_index = idx
            break

    before = "\n".join(lines[:first_start]).strip()
    if stop_index is None:
        visas = "\n".join(lines[first_start:]).strip()
        after = ""
    else:
        visas = "\n".join(lines[first_start:stop_index]).strip()
        after = "\n".join(lines[stop_index:]).strip()

    return {"avant_visas": before, "visas": visas, "apres_visas": after}


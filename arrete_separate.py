import argparse
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional

from cleaner import clean_ocr_text
from extractors.summary import extract_summary
from extractors.title_page import extract_title_pages


# Dans ce module, je decoupe un recueil RAA en arretes.
# En sortie, je veux une liste de blocs arretes avec texte, pagination
# et liens avec le sommaire / les pages de titre.

# Ici, je detecte un numero d'arrete (ex: 01-2024-05-12-00001).
_NUMBER_RE = re.compile(
    r"\b((?:\d{1,3}|2A|2B|R\d{2})-\d{4}-\d{2}-\d{2}-\d{5})\b",
    re.IGNORECASE,
)
# Ici, je verifie si une ligne commence par le numero attendu.
_START_WITH_NUMBER_RE_TEMPLATE = r"^\s*(?:ACTE\s+PUBLIABLE\s+)?{num}(?:\b|[\s\-:])"
# Ici, je recupere les numeros de page presents dans le texte.
_PAGE_RE = re.compile(r"(?i)\bPage\s+(\d+)\b")
_SUMMARY_ENTRY_RE = re.compile(r"(?i)\(\d+\s*pages?\)\s*Page\s+\d+\b")
_SERVICE_HEADER_RE = re.compile(
    r"(?i)^\s*(?:"
    r".{0,30}/\s*(?:SERVICE|DIRECTION|CABINET|BUREAU)\b|"
    r"(?:SERVICE|DIRECTION|CABINET|BUREAU|SECRETARIAT\s+GENERAL)\b"
    r")"
)
# C'est mon mot-cle de secours pour couper un document quand les numeros manquent.
_FALLBACK_START_RE = re.compile(
    r"(?i)^\s*(?:ARR(?:E|É)T(?:E|É)(?:\s+PREFECTORAL)?|DECISION|AVENANT|DELEGATION)\b"
)
_TITLE_STOP_RE = re.compile(r"(?i)^\s*(?:VU\b|CONSID\S*RANT\b|ARTICLE\b|DECIDE\b|ARRETE\b)")


def _summary_end_index(lines: List[str]) -> int:
    # Je cherche la fin du bloc "Sommaire" pour demarrer la recherche juste apres.
    for idx, line in enumerate(lines):
        if re.search(r"\bSommaire\b", line, re.IGNORECASE):
            # Dans certains fichiers, la ligne numerique de fin de sommaire
            # est supprimee au nettoyage. On prend donc la derniere ligne
            # contenant "(x pages) Page y" comme borne fiable.
            last_summary_line = None
            for j in range(idx + 1, len(lines)):
                if _SUMMARY_ENTRY_RE.search(lines[j].strip()):
                    last_summary_line = j
            if last_summary_line is not None:
                return last_summary_line + 1
            return idx + 1
    return 0


def _looks_like_summary_hit(lines: List[str], idx: int, numero: str) -> bool:
    # Ignore les lignes de sommaire qui referencent un numero d'acte.
    line = lines[idx].strip()
    if _SUMMARY_ENTRY_RE.search(line):
        return True

    # Cas tres frequent: numero et titre sur une ligne, "(x pages) Page y" sur la ligne suivante.
    if numero and re.search(rf"\b{re.escape(numero)}\b", line, re.IGNORECASE):
        for delta in (1, 2):
            nxt_idx = idx + delta
            if nxt_idx < len(lines) and _SUMMARY_ENTRY_RE.search(lines[nxt_idx].strip()):
                return True

    return False


def _summary_bounds(lines: List[str]) -> tuple[int, int]:
    # Renvoie [start, end) du bloc sommaire.
    start = 0
    found = False
    for idx, line in enumerate(lines):
        if re.search(r"\bSommaire\b", line, re.IGNORECASE):
            start = idx + 1
            found = True
            break
    if not found:
        return (0, 0)
    return (start, _summary_end_index(lines))


def _extract_summary_service_map(lines: List[str], numeros: List[str]) -> Dict[str, str]:
    # Associe chaque numero d'acte au "service courant" lu dans le sommaire.
    if not numeros:
        return {}

    start, end = _summary_bounds(lines)
    if end <= start:
        return {}

    number_set = set(numeros)
    current_service = ""
    mapping: Dict[str, str] = {}

    for idx in range(start, end):
        line = lines[idx].strip()
        if not line:
            continue

        if _SERVICE_HEADER_RE.search(line) and not _SUMMARY_ENTRY_RE.search(line):
            current_service = re.sub(r"\s+", " ", line).strip(" -:\t")
            continue

        match = _NUMBER_RE.search(line)
        if not match:
            continue
        numero = match.group(1)
        if numero in number_set and current_service:
            mapping[numero] = current_service

    return mapping


def _find_number_starts(lines: List[str], numeros: List[str]) -> Dict[str, Optional[int]]:
    # Je cherche la ligne de debut de chaque numero d'arrete.
    starts: Dict[str, Optional[int]] = {}
    search_start = _summary_end_index(lines)

    for numero in numeros:
        start_pattern = re.compile(
            _START_WITH_NUMBER_RE_TEMPLATE.format(num=re.escape(numero)),
            re.IGNORECASE,
        )
        contains_pattern = re.compile(rf"\b{re.escape(numero)}\b", re.IGNORECASE)
        found = None

        # 1) Cas ideal: la ligne commence par le numero d'acte.
        for i in range(search_start, len(lines)):
            line = lines[i].strip()
            if _looks_like_summary_hit(lines, i, numero):
                continue
            if start_pattern.match(line):
                found = i
                break

        # 2) Cas frequent: le numero apparait dans une ligne "service - numero - titre".
        if found is None:
            for i in range(search_start, len(lines)):
                line = lines[i].strip()
                if _looks_like_summary_hit(lines, i, numero):
                    continue
                if contains_pattern.search(line):
                    found = i
                    break

        # 3) Dernier recours: recherche globale.
        if found is None:
            for i, line in enumerate(lines):
                stripped = line.strip()
                if _looks_like_summary_hit(lines, i, numero):
                    continue
                if start_pattern.match(stripped):
                    found = i
                    break
            if found is None:
                for i, line in enumerate(lines):
                    stripped = line.strip()
                    if _looks_like_summary_hit(lines, i, numero):
                        continue
                    if contains_pattern.search(stripped):
                        found = i
                        break

        starts[numero] = found
    return starts


def _build_block_map(lines: List[str], numeros: List[str]) -> Dict[str, Dict[str, object]]:
    # Construit des blocs de texte entre deux numeros consecutifs.
    starts = _find_number_starts(lines, numeros)
    positioned = sorted(
        (start_idx, numero) for numero, start_idx in starts.items() if start_idx is not None
    )

    blocks: Dict[str, Dict[str, object]] = {}
    for idx, (start_line, numero) in enumerate(positioned):
        end_line = positioned[idx + 1][0] if idx + 1 < len(positioned) else len(lines)
        block_lines = lines[start_line:end_line]
        blocks[numero] = {
            "start_line": start_line,
            "end_line": end_line,
            "text": "\n".join(block_lines).strip(),
        }

    for numero in numeros:
        blocks.setdefault(numero, {"start_line": None, "end_line": None, "text": ""})
    return blocks


def _extract_title_from_block(block_text: str, numero: str, fallback_title: str) -> str:
    # Prend un titre court depuis le bloc, ou garde le titre de secours.
    if fallback_title:
        return fallback_title.strip()
    if not block_text:
        return ""

    lines = [line.strip() for line in block_text.splitlines() if line.strip()]
    if not lines:
        return ""

    title_lines: List[str] = []
    first = lines[0]
    if first.upper().startswith(numero.upper()):
        tail = first[len(numero) :].strip(" -:")
        if tail:
            title_lines.append(tail)
        lines = lines[1:]

    for line in lines:
        if _TITLE_STOP_RE.match(line):
            break
        title_lines.append(line)
        if len(title_lines) >= 3:
            break

    return re.sub(r"\s+", " ", " ".join(title_lines)).strip(" -:\n")


def _extract_pagination_from_text(text: str) -> Dict[str, Optional[int]]:
    # Extrait page debut / page fin en lisant "Page X" dans le texte.
    pages = [int(m.group(1)) for m in _PAGE_RE.finditer(text or "")]
    if not pages:
        return {"page_debut": None, "page_fin": None, "nb_pages": None}
    page_debut = min(pages)
    page_fin = max(pages)
    return {
        "page_debut": page_debut,
        "page_fin": page_fin,
        "nb_pages": (page_fin - page_debut + 1),
    }


def _pagination_from_summary_entry(entry: Optional[Dict[str, object]]) -> Dict[str, Optional[int]]:
    # Transforme les infos du sommaire en pagination complete.
    if not entry:
        return {"page_debut": None, "page_fin": None, "nb_pages": None}

    page_debut = entry.get("page_debut")
    nb_pages = entry.get("nb_pages")
    if isinstance(page_debut, int) and isinstance(nb_pages, int) and nb_pages > 0:
        return {
            "page_debut": page_debut,
            "page_fin": page_debut + nb_pages - 1,
            "nb_pages": nb_pages,
        }
    return {"page_debut": None, "page_fin": None, "nb_pages": None}


def _ordered_numbers(summary_entries: List[Dict[str, object]], title_entries: List[Dict[str, object]]) -> List[str]:
    # Fabrique une liste de numeros, sans doublons, en gardant l'ordre.
    seen = set()
    ordered: List[str] = []
    for entry in summary_entries + title_entries:
        numero = entry.get("numero")
        if isinstance(numero, str) and numero and numero not in seen:
            seen.add(numero)
            ordered.append(numero)
    return ordered


def _fallback_keyword_split(clean_text: str, raw_text: str) -> List[Dict[str, object]]:
    # Methode de secours: coupe sur des mots cle (ARRETE, DECISION, ...).
    clean_lines = clean_text.splitlines()
    raw_lines = raw_text.splitlines()

    starts = [idx for idx, line in enumerate(clean_lines) if _FALLBACK_START_RE.search(line.strip())]
    if not starts:
        return []

    blocks: List[Dict[str, object]] = []
    for pos, start in enumerate(starts):
        end = starts[pos + 1] if pos + 1 < len(starts) else len(clean_lines)
        clean_block = "\n".join(clean_lines[start:end]).strip()
        raw_block = "\n".join(raw_lines[start:end]).strip() if start < len(raw_lines) else clean_block

        number_match = _NUMBER_RE.search(clean_block)
        numero = number_match.group(1) if number_match else ""

        title = _extract_title_from_block(clean_block, numero, "")
        pages = _extract_pagination_from_text(clean_block)
        blocks.append(
            {
                "index": len(blocks) + 1,
                "numero": numero,
                "titre": title,
                "raw_text": raw_block,
                "clean_text": clean_block,
                "page_debut": pages["page_debut"],
                "page_fin": pages["page_fin"],
                "nb_pages": pages["nb_pages"],
                "sommaire": None,
                "title_candidate": None,
            }
        )
    return blocks


def split_raa_into_arretes(
    raw_text: str,
    clean_text: Optional[str] = None,
    summary_entries: Optional[List[Dict[str, object]]] = None,
    title_entries: Optional[List[Dict[str, object]]] = None,
) -> List[Dict[str, object]]:
    # C'est ma fonction principale: je decoupe un recueil RAA en arretes.
    clean_text = clean_text if isinstance(clean_text, str) else clean_ocr_text(raw_text or "")
    summary_entries = summary_entries if summary_entries is not None else extract_summary(clean_text)
    title_entries = title_entries if title_entries is not None else extract_title_pages(clean_text)

    summary_map = {entry.get("numero"): entry for entry in summary_entries if entry.get("numero")}
    title_map = {entry.get("numero"): entry for entry in title_entries if entry.get("numero")}
    numeros = _ordered_numbers(summary_entries, title_entries)

    if not numeros:
        # Aucun numero trouve: on tente la methode de secours.
        fallback = _fallback_keyword_split(clean_text, raw_text or clean_text)
        if fallback:
            return fallback
        return [
            {
                "index": 1,
                "numero": "",
                "titre": "",
                "raw_text": (raw_text or "").strip(),
                "clean_text": clean_text.strip(),
                "page_debut": None,
                "page_fin": None,
                "nb_pages": None,
                "sommaire": None,
                "title_candidate": None,
            }
        ]

    clean_lines = clean_text.splitlines()
    raw_lines = (raw_text or "").splitlines()
    clean_blocks = _build_block_map(clean_lines, numeros)
    raw_blocks = _build_block_map(raw_lines, numeros) if raw_lines else {}
    summary_service_map = _extract_summary_service_map(clean_lines, numeros)

    results: List[Dict[str, object]] = []
    for idx, numero in enumerate(numeros, start=1):
        # Construit la sortie finale pour chaque arrete.
        clean_block = str(clean_blocks.get(numero, {}).get("text", "")).strip()
        raw_block = str(raw_blocks.get(numero, {}).get("text", "")).strip() if raw_blocks else ""
        if not raw_block:
            raw_block = clean_block

        summary_entry = summary_map.get(numero)
        title_entry = title_map.get(numero)
        summary_title = summary_entry.get("titre", "") if isinstance(summary_entry, dict) else ""
        title_page_title = title_entry.get("titre", "") if isinstance(title_entry, dict) else ""
        titre = _extract_title_from_block(clean_block, numero, summary_title or title_page_title)

        pages = _pagination_from_summary_entry(summary_entry if isinstance(summary_entry, dict) else None)
        if pages["page_debut"] is None:
            pages = _extract_pagination_from_text(clean_block)

        results.append(
            {
                "index": idx,
                "numero": numero,
                "titre": titre,
                "raw_text": raw_block,
                "clean_text": clean_block,
                "page_debut": pages["page_debut"],
                "page_fin": pages["page_fin"],
                "nb_pages": pages["nb_pages"],
                "sommaire": summary_entry if isinstance(summary_entry, dict) else None,
                "service_hint": summary_service_map.get(numero, ""),
                "title_candidate": title_entry if isinstance(title_entry, dict) else None,
            }
        )

    return results


# Wrappers historiques conserves pour compatibilite.
def method1_extract(text: str) -> List[Dict[str, object]]:
    # Ancienne sortie simple: titre + texte + flag annexe.
    blocks = split_raa_into_arretes(raw_text=text, clean_text=clean_ocr_text(text))
    return [
        {
            "titre": block.get("titre", ""),
            "texte": block.get("clean_text", ""),
            "annexe": bool(re.search(r"(?im)^\s*annexe\b", block.get("clean_text", ""))),
        }
        for block in blocks
    ]


def method2_extract(text: str):
    # Ancien acces direct a l'extraction du sommaire.
    return extract_summary(clean_ocr_text(text))


def method3_extract(text: str):
    # Ancien acces direct a l'extraction des pages de titre.
    return extract_title_pages(clean_ocr_text(text))


def process_file(filepath: str, base_output: str) -> None:
    # Lit un fichier texte et ecrit un JSON par arrete.
    with open(filepath, "r", encoding="utf-8") as f:
        raw_text = f.read()

    blocks = split_raa_into_arretes(raw_text=raw_text)
    out_dir = Path(base_output)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(filepath).stem

    for block in blocks:
        index = int(block.get("index", 1))
        data = {
            "id": f"{stem}-{index:02d}",
            "numero": block.get("numero", ""),
            "titre": block.get("titre", ""),
            "page_debut": block.get("page_debut"),
            "page_fin": block.get("page_fin"),
            "nb_pages": block.get("nb_pages"),
            "texte": block.get("clean_text", ""),
        }
        dest = out_dir / f"{stem}-{index:02d}.json"
        with dest.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"-> {dest}")


def process_pref_mode(pref: str, base_output: str) -> None:
    # Traite tous les .txt d'une prefecture.
    folder = os.path.join("data", pref, "raa")
    if not os.path.isdir(folder):
        print("Dossier introuvable :", folder)
        return
    for file_name in sorted(os.listdir(folder)):
        if file_name.lower().endswith(".txt"):
            process_file(os.path.join(folder, file_name), base_output)


def process_whole_mode(data_root: str, base_output: str) -> None:
    # Traite toutes les prefectures presentes dans data_root.
    if not os.path.isdir(data_root):
        print("Repertoire introuvable :", data_root)
        return
    for pref in sorted(os.listdir(data_root)):
        folder = os.path.join(data_root, pref, "raa")
        if not os.path.isdir(folder):
            continue
        for file_name in sorted(os.listdir(folder)):
            if file_name.lower().endswith(".txt"):
                process_file(os.path.join(folder, file_name), base_output)


def main_lite(args) -> None:
    # Point d'entree en ligne de commande.
    output_dir = args.output if args.output else "output"
    if args.mode == "pref":
        if not args.prefecture:
            print("Le parametre --prefecture est requis pour le mode 'pref'.")
            return
        process_pref_mode(f"pref{args.prefecture}", output_dir)
        return
    if args.mode == "whole":
        process_whole_mode(args.data_dir, output_dir)
        return
    print("Mode inconnu. Choisir entre : pref, whole.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Decoupage des arretes du recueil RAA.")
    parser.add_argument("--mode", required=True, choices=["pref", "whole"])
    parser.add_argument("--prefecture", help="Code prefecture (ex: 01) si mode='pref'.")
    parser.add_argument("--data_dir", default="data")
    parser.add_argument("--output", required=True)
    parsed_args = parser.parse_args()
    main_lite(parsed_args)

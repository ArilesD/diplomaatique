from pathlib import Path
import argparse
import json
import re
import unicodedata
from typing import Any, Dict, List, Optional

from cleaner import clean_ocr_text
from arrete_separate import split_raa_into_arretes

from extractors.metadata import extract_metadata
from extractors.summary import extract_summary
from extractors.title_page import extract_title_pages
from extractors.autorite_emettrice import extract_autorite_emettrice
from extractors.autorite_decisionnair import extract_autorite_decisionnaire
from extractors.visas import extract_visas
from extractors.considerants import extract_considerants
from extractors.articles import extract_articles
from extractors.signataire import extract_signataire
from extractors.annexes import extract_annex_blocks
from extractors.voies_recours import extract_voies_recours
from extractors.services import extract_services

# Je garde une roue de secours: si l'extracteur specialise plante, je peux revenir a l'ancien.
try:
    from extractors.visas_articles import extract_details as extract_details_legacy
except Exception:
    extract_details_legacy = None


DEFAULT_META = {
    "source_pdf": "",
    "numero_raa": "",
    "date_publication": "",
    "prefecture_id": "",
    "prefecture_name": "",
}

DEFAULT_VOIES_RECOURS = {
    "voiesRecours": [],
    "delaiRecours": [],
    "juridictionCompetente": None,
    "texteExplicatifRecours": None,
}

DEFAULT_SERVICES = {
    "service": "",
    "direction_bureau_cabinet": [],
}

_DELAI_NUMBER_MAP = {
    "un": "1",
    "une": "1",
    "deux": "2",
    "trois": "3",
    "quatre": "4",
    "cinq": "5",
    "six": "6",
    "sept": "7",
    "huit": "8",
    "neuf": "9",
    "dix": "10",
    "onze": "11",
    "douze": "12",
}
_DELAI_DURATION_RE = re.compile(
    r"\b(\d+|un|une|deux|trois|quatre|cinq|six|sept|huit|neuf|dix|onze|douze)\s+"
    r"(jour|jours|mois|an|ans|heure|heures)\b"
)


def _warn(message: str) -> None:
    # Ici, je log juste un warning pour ne pas bloquer tout le traitement.
    print(f"[WARN] {message}")


def _safe_call(name: str, fn, default, *args, **kwargs):
    # Je lance la fonction en mode securise: si ca casse, je renvoie une valeur par defaut.
    try:
        result = fn(*args, **kwargs)
        if result is None:
            return default
        return result
    except Exception as exc:
        _warn(f"{name} a echoue: {exc}")
        return default


def _is_empty(value: Any) -> bool:
    # Dit si une valeur est vide, meme quand c'est une liste ou un dict imbrique.
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, dict):
        if not value:
            return True
        return all(_is_empty(v) for v in value.values())
    if isinstance(value, (list, tuple, set)):
        return len(value) == 0
    return False


def _value_score(value: Any) -> int:
    # Calcule un score pour comparer deux resultats et garder le plus riche.
    if _is_empty(value):
        return 0
    if isinstance(value, str):
        return len(value.strip())
    if isinstance(value, list):
        return sum(_value_score(item) for item in value) + len(value)
    if isinstance(value, dict):
        return sum(_value_score(v) for v in value.values()) + len(
            [k for k, v in value.items() if not _is_empty(v)]
        )
    return 1


def _prefer_best(current: Any, candidate: Any) -> Any:
    # Entre current et candidate, on garde celle qui apporte le plus d'infos.
    if _is_empty(candidate):
        return current
    if _is_empty(current):
        return candidate
    if isinstance(current, dict) and isinstance(candidate, dict):
        merged: Dict[str, Any] = dict(current)
        for key in candidate.keys():
            merged[key] = _prefer_best(current.get(key), candidate.get(key))
        return merged
    return candidate if _value_score(candidate) > _value_score(current) else current


def _normalize_meta(meta: Dict[str, Any]) -> Dict[str, Any]:
    # Complete les metadata pour etre sure que toutes les cles existent.
    normalized = dict(DEFAULT_META)
    for key in normalized.keys():
        value = meta.get(key)
        if value is None:
            value = ""
        normalized[key] = value
    return normalized


def _extract_numero_arrete(block: Dict[str, Any]) -> str:
    # Recupere le numero d'arrete depuis le bloc; sinon on le cherche dans le texte.
    numero = block.get("numero")
    if isinstance(numero, str) and numero.strip():
        return numero.strip()
    text = str(block.get("clean_text", ""))
    match = re.search(
        r"\b((?:\d{1,3}|2A|2B|R\d{2})-\d{4}-\d{2}-\d{2}-\d{5})\b",
        text,
        re.IGNORECASE,
    )
    return match.group(1) if match else ""


def _normalize_text_key(text: str) -> str:
    # Produit une cle textuelle stable (sans accents/ponctuation) pour dedoublonnage.
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_like = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    ascii_like = ascii_like.lower()
    ascii_like = re.sub(r"[^a-z0-9\s]", " ", ascii_like)
    ascii_like = re.sub(r"\s+", " ", ascii_like).strip()
    return ascii_like


def _delay_semantic_key(text: str) -> str:
    # Cle "metier" volontairement simple: voie + duree (ex: contentieux:2_mois).
    normalized = _normalize_text_key(text)
    if not normalized:
        return ""

    voie = "contentieux"
    if "gracieux" in normalized:
        voie = "gracieux"
    elif "hierarchique" in normalized:
        voie = "hierarchique"

    match = _DELAI_DURATION_RE.search(normalized)
    if not match:
        return normalized

    number_token = match.group(1)
    number = _DELAI_NUMBER_MAP.get(number_token, number_token)
    unit = match.group(2)
    if unit.startswith("jour"):
        unit = "jour"
    elif unit.startswith("an"):
        unit = "an"
    elif unit.startswith("heure"):
        unit = "heure"
    else:
        unit = "mois"
    return f"{voie}:{number}_{unit}"


def _dedupe_delais(delais: List[str]) -> List[str]:
    # Supprime les repetitions exactes et les doublons de meme duree/voie.
    unique: List[str] = []
    seen_exact = set()
    seen_semantic = set()

    for item in delais:
        exact_key = _normalize_text_key(item)
        if not exact_key or exact_key in seen_exact:
            continue

        semantic_key = _delay_semantic_key(item)
        if semantic_key in seen_semantic:
            continue

        seen_exact.add(exact_key)
        seen_semantic.add(semantic_key)
        unique.append(item)
    return unique


def _normalize_voies_recours(value: Any) -> Dict[str, Any]:
    # Assure une structure stable pour les voies de recours dans la sortie JSON.
    if not isinstance(value, dict):
        return dict(DEFAULT_VOIES_RECOURS)
    normalized = dict(DEFAULT_VOIES_RECOURS)
    normalized.update(value)
    # On exclut volontairement les champs techniques non souhaites dans la sortie.
    normalized.pop("mentions", None)
    normalized.pop("found", None)
    if not isinstance(normalized.get("voiesRecours"), list):
        normalized["voiesRecours"] = []
    raw_delais = normalized.get("delaiRecours")
    if isinstance(raw_delais, list):
        cleaned_delais: List[str] = []
        for item in raw_delais:
            if not isinstance(item, str):
                continue
            text = re.sub(r"\s*\n+\s*", " ", item)
            text = re.sub(r"[ \t]+", " ", text).strip()
            if text:
                cleaned_delais.append(text)
        normalized["delaiRecours"] = _dedupe_delais(cleaned_delais)
    else:
        normalized["delaiRecours"] = []

    for key in ("juridictionCompetente", "texteExplicatifRecours"):
        value = normalized.get(key)
        if isinstance(value, str):
            value = re.sub(r"\s*\n+\s*", " ", value)
            value = re.sub(r"[ \t]+", " ", value).strip()
            normalized[key] = value or None
        elif value is not None:
            normalized[key] = str(value)
    return normalized


def _voies_recours_score(value: Any) -> int:
    # Score utilitaire pour choisir la meilleure extraction de recours.
    if not isinstance(value, dict):
        return 0
    score = 0
    voies = value.get("voiesRecours")
    delais = value.get("delaiRecours")
    juridiction = value.get("juridictionCompetente")
    texte = value.get("texteExplicatifRecours")
    mentions = value.get("mentions")

    if isinstance(voies, list):
        score += len([v for v in voies if isinstance(v, str) and v.strip()]) * 3
    if isinstance(delais, list):
        score += len([d for d in delais if isinstance(d, str) and d.strip()]) * 6
    if isinstance(juridiction, str) and juridiction.strip():
        score += 4
    if isinstance(texte, str) and texte.strip():
        score += min(len(texte.strip()), 400) // 80
    if isinstance(mentions, dict) and mentions.get("telerecours"):
        score += 1
    if value.get("found") is True:
        score += 2
    return score


def _normalize_services(value: Any) -> Dict[str, Any]:
    # Assure une structure stable pour les services dans la sortie JSON.
    if not isinstance(value, dict):
        return dict(DEFAULT_SERVICES)
    normalized = dict(DEFAULT_SERVICES)
    normalized.update(value)

    service = normalized.get("service")
    normalized["service"] = service.strip() if isinstance(service, str) else ""

    raw_labels = normalized.get("direction_bureau_cabinet")
    labels: List[str] = []
    if isinstance(raw_labels, list):
        labels = [item.strip() for item in raw_labels if isinstance(item, str) and item.strip()]
    normalized["direction_bureau_cabinet"] = list(dict.fromkeys(labels))
    return normalized


def _section_text_score(text: str) -> int:
    # Mesure rapide de "richesse" juridique du texte pour les extracteurs de sections.
    if not isinstance(text, str) or not text.strip():
        return 0
    score = 0
    if re.search(r"(?im)^\s*VU\b", text):
        score += 1
    if re.search(r"(?im)^\s*CONSID\S*RANT\b", text):
        score += 1
    if re.search(r"(?im)^\s*ARTICLE\b", text):
        score += 2
    if len([line for line in text.splitlines() if line.strip()]) >= 20:
        score += 1
    return score


def _pick_section_source(clean_text: str, raw_text: str) -> str:
    # Si clean_text est trop court/incomplet, on bascule sur raw_text.
    clean_has_article = bool(re.search(r"(?im)^\s*ART(?:ICLE|ICL)?\s*(?:\d|1ER|UNIQUE|PREMIER|[IVXLCDM])", clean_text or ""))
    raw_has_article = bool(re.search(r"(?im)^\s*ART(?:ICLE|ICL)?\s*(?:\d|1ER|UNIQUE|PREMIER|[IVXLCDM])", raw_text or ""))

    # Regle simple et robuste: si raw a des entetes ARTICLE et pas clean, on prend raw.
    if raw_has_article and not clean_has_article:
        return raw_text

    clean_score = _section_text_score(clean_text)
    raw_score = _section_text_score(raw_text)
    if raw_score > clean_score:
        return raw_text
    return clean_text


def _extract_arrete_details(arrete_input: Dict[str, Any]) -> Dict[str, Any]:
    # Dans cette fonction, je recupere les parties importantes d'un arrete (visas, articles, signataire...).
    clean_text = str(arrete_input.get("clean_text", ""))
    raw_text = str(arrete_input.get("raw_text", ""))
    service_hint = str(arrete_input.get("service_hint", "") or "").strip()
    source_text = _pick_section_source(clean_text, raw_text) or clean_text or raw_text

    # Ici, j'appelle les extracteurs un par un.
    visas = _safe_call("extract_visas", extract_visas, [], source_text)
    considerants = _safe_call("extract_considerants", extract_considerants, [], source_text)
    # Regle simple: pour les ARTICLES, je privilegie le texte brut.
    # Je fais ca car le nettoyage OCR peut parfois casser des entetes "ARTICLE X".
    article_text = raw_text or source_text
    articles = _safe_call("extract_articles", extract_articles, [], article_text)
    # Si le texte brut est vide/inexploitable, je tente un fallback.
    if (not isinstance(articles, list) or len(articles) == 0) and source_text and source_text != article_text:
        source_articles = _safe_call("extract_articles", extract_articles, [], source_text)
        if isinstance(source_articles, list) and len(source_articles) > 0:
            articles = source_articles
    signataire = _safe_call(
        "extract_signataire",
        extract_signataire,
        {"nom": "", "fonction": "", "date_signature": "", "lieu_signature": "", "ligne": ""},
        source_text,
    )
    autorite_emettrice = _safe_call(
        "extract_autorite_emettrice",
        extract_autorite_emettrice,
        {"nom": "", "fonction": "", "service": "", "administration": "", "ligne": ""},
        source_text,
    )
    if raw_text and raw_text != source_text:
        autorite_emettrice_raw = _safe_call(
            "extract_autorite_emettrice",
            extract_autorite_emettrice,
            {"nom": "", "fonction": "", "service": "", "administration": "", "ligne": ""},
            raw_text,
        )
        autorite_emettrice = _prefer_best(autorite_emettrice, autorite_emettrice_raw)
    autorite_decisionnaire = _safe_call(
        "extract_autorite_decisionnaire",
        extract_autorite_decisionnaire,
        {"fonction": "", "nom": "", "institution": "", "ligne": ""},
        source_text,
    )
    services = _safe_call("extract_services", extract_services, dict(DEFAULT_SERVICES), source_text)
    services = _normalize_services(services)
    if service_hint:
        services["service"] = _prefer_best(services.get("service", ""), service_hint)
    if isinstance(autorite_emettrice, dict):
        autorite_emettrice["service"] = _prefer_best(
            autorite_emettrice.get("service", ""),
            services.get("service", ""),
        )
    annexes = _safe_call("extract_annex_blocks", extract_annex_blocks, [], source_text)
    voies_recours_source = _safe_call(
        "extract_voies_recours", extract_voies_recours, dict(DEFAULT_VOIES_RECOURS), source_text
    )
    voies_recours_raw: Dict[str, Any] = {}
    if raw_text and raw_text != source_text:
        voies_recours_raw = _safe_call(
            "extract_voies_recours", extract_voies_recours, dict(DEFAULT_VOIES_RECOURS), raw_text
        )
    voies_recours = _prefer_best(voies_recours_source, voies_recours_raw)
    if _voies_recours_score(voies_recours_raw) > _voies_recours_score(voies_recours_source):
        voies_recours = voies_recours_raw
    voies_recours = _normalize_voies_recours(voies_recours)

    # Si l'ancien extracteur est dispo, on fusionne pour recuperer ce qui manque.
    legacy = {}
    if callable(extract_details_legacy):
        legacy = _safe_call("extract_details_legacy", extract_details_legacy, {}, source_text)
    visas = _prefer_best(visas, legacy.get("visas", []))
    considerants = _prefer_best(considerants, legacy.get("considerants", []))
    articles = _prefer_best(articles, legacy.get("articles", []))
    annexes = _prefer_best(annexes, legacy.get("annexes", []))
    autorite_emettrice = _prefer_best(autorite_emettrice, legacy.get("autorite_emettrice", {}))
    autorite_decisionnaire = _prefer_best(
        autorite_decisionnaire, legacy.get("autorite_decisionnaire", {})
    )
    signataire = _prefer_best(signataire, legacy.get("signataire", {}))
    if isinstance(signataire, dict):
        signataire["date_signature"] = _prefer_best(
            signataire.get("date_signature", ""),
            legacy.get("date_signature", ""),
        )

    return {
        "autorite_emettrice": autorite_emettrice if isinstance(autorite_emettrice, dict) else {},
        "autorite_decisionnaire": autorite_decisionnaire
        if isinstance(autorite_decisionnaire, dict)
        else {},
        "visas": visas if isinstance(visas, list) else [],
        "considerants": considerants if isinstance(considerants, list) else [],
        "articles": articles if isinstance(articles, list) else [],
        "signataire": signataire if isinstance(signataire, dict) else {},
        "annexes": annexes if isinstance(annexes, list) else [],
        "voies_recours": voies_recours,
        "services": services,
    }


def _build_final_doc(
    base_id: str,
    index: int,
    metadata_raa: Dict[str, Any],
    block: Dict[str, Any],
    details: Dict[str, Any],
) -> Dict[str, Any]:
    # Assemble le JSON final d'un arrete.
    numero_arrete = _extract_numero_arrete(block)
    signataire = details.get("signataire", {})

    doc = {
        "id": f"{base_id}-{index:02d}",
        "metadata_raa": metadata_raa,
        "numero_arrete": numero_arrete,
        "titre": block.get("titre", "") or "",
        "page_debut": block.get("page_debut"),
        "page_fin": block.get("page_fin"),
        "nb_pages": block.get("nb_pages"),
        "autorite_emettrice": details.get("autorite_emettrice", {}),
        "autorite_decisionnaire": details.get("autorite_decisionnaire", {}),
        "services": details.get("services", dict(DEFAULT_SERVICES)),
        "visas": details.get("visas", []),
        "considerants": details.get("considerants", []),
        "articles": details.get("articles", []),
        "signataire": signataire,
        "annexes": details.get("annexes", []),
        "voies_recours": details.get("voies_recours", dict(DEFAULT_VOIES_RECOURS))
        # La ligne "debug" a complètement disparu d'ici !
    }
    return doc


def _build_arrete_input(
    block: Dict[str, Any],
    metadata_raa: Dict[str, Any],
) -> Dict[str, Any]:
    # Met les donnees au format attendu par la suite du pipeline.
    return {
        "raw_text": block.get("raw_text", "") or "",
        "clean_text": block.get("clean_text", "") or "",
        "page_debut": block.get("page_debut"),
        "page_fin": block.get("page_fin"),
        "nb_pages": block.get("nb_pages"),
        "service_hint": block.get("service_hint", "") or "",
        "metadata_raa": metadata_raa,
        "title_candidates": {
            "sommaire": block.get("sommaire"),
            "title_page": block.get("title_candidate"),
        },
    }


def _ensure_blocks(
    raw_text: str,
    clean_text: str,
    summary_entries: List[Dict[str, Any]],
    title_entries: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    # Essaie de separer le RAA en plusieurs arretes; sinon on fait un bloc unique.
    blocks = _safe_call(
        "split_raa_into_arretes",
        split_raa_into_arretes,
        [],
        raw_text,
        clean_text,
        summary_entries,
        title_entries,
    )
    if blocks:
        return blocks
    return [
        {
            "index": 1,
            "numero": "",
            "titre": "",
            "raw_text": raw_text.strip(),
            "clean_text": clean_text.strip(),
            "page_debut": None,
            "page_fin": None,
            "nb_pages": None,
            "sommaire": None,
            "title_candidate": None,
        }
    ]


def _write_arrete_doc(dest: Path, doc: Dict[str, Any]) -> None:
    # Ecrit le document JSON sur le disque.
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)


def process_raa(
    base_id: str,
    raw_text: str,
    attrap_meta: Dict[str, Any],
    output_dir: Path,
) -> List[Dict[str, Any]]:
    # Pipeline principal pour traiter un RAA complet.
    # En gros: nettoyage -> metadata -> decoupage -> extraction -> ecriture.
    clean_text = clean_ocr_text(raw_text)
    metadata_raa = _normalize_meta(
        _safe_call("extract_metadata", extract_metadata, dict(DEFAULT_META), clean_text, attrap_meta)
    )

    summary_entries = _safe_call("extract_summary", extract_summary, [], clean_text)
    title_entries = _safe_call("extract_title_pages", extract_title_pages, [], clean_text)
    blocks = _ensure_blocks(raw_text, clean_text, summary_entries, title_entries)

    docs: List[Dict[str, Any]] = []
    for index, block in enumerate(blocks, start=1):
        # Pour chaque arrete, on produit un fichier JSON.
        arrete_input = _build_arrete_input(block, metadata_raa)
        details = _extract_arrete_details(arrete_input)
        doc = _build_final_doc(base_id, index, metadata_raa, block, details)
        dest = output_dir / f"{base_id}-{index:02d}.json"
        _write_arrete_doc(dest, doc)
        docs.append(doc)
        print(f"OK : {dest.name}")
    return docs


def _iter_raa_pairs(data_dir: str, prefecture: Optional[str] = None):
    # Parcourt data/ et renvoie les paires disponibles (fichier txt + JSON ATRAP).
    root = Path(data_dir)
    if prefecture:
        pref_dirs = [root / f"pref{prefecture}"]
    else:
        pref_dirs = [path for path in sorted(root.iterdir()) if path.is_dir()]

    for pref_dir in pref_dirs:
        raa_dir = pref_dir / "raa"
        if not raa_dir.is_dir():
            continue
        for txt_path in sorted(raa_dir.glob("*.txt")):
            json_path = txt_path.with_suffix(".json")
            if json_path.exists():
                yield txt_path, json_path
            else:
                _warn(f"JSON ATRAP manquant pour {txt_path}")


def _load_attrap_json(path: Path) -> Dict[str, Any]:
    # Charge le JSON ATRAP en evitant qu'une erreur stoppe tout.
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
        _warn(f"Format ATRAP inattendu (non-dict): {path}")
        return {}
    except Exception as exc:
        _warn(f"Impossible de lire {path}: {exc}")
        return {}


def _pref_dir_name_from_meta(meta: Dict[str, Any]) -> str:
    # Devine le nom du dossier prefecture a partir des metadata.
    pref_id = str(meta.get("prefecture_id", "") or "").strip()
    if pref_id:
        return f"pref{pref_id}"
    return "pref_unknown"


def _run_batch(data_dir: str, out_dir: str, prefecture: Optional[str] = None) -> None:
    # Mode lot: traite tous les RAA d'une prefecture, ou tout le dossier data.
    out_root = Path(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    for txt_path, json_path in _iter_raa_pairs(data_dir, prefecture=prefecture):
        try:
            raw_text = txt_path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            _warn(f"Lecture texte impossible pour {txt_path}: {exc}")
            continue

        attrap_meta = _load_attrap_json(json_path)
        # Les resultats seront ranges comme: output/prefXX/nom_du_raa/
        pref_folder = txt_path.parent.parent.name
        target_dir = out_root / pref_folder / txt_path.stem
        process_raa(txt_path.stem, raw_text, attrap_meta, target_dir)


def _run_single_file(raa_txt: str, metadata_json: str, out_dir: str) -> None:
    # Mode fichier: traite seulement un couple (txt + metadata).
    txt_path = Path(raa_txt)
    meta_path = Path(metadata_json)

    raw_text = txt_path.read_text(encoding="utf-8", errors="replace")
    attrap_meta = _load_attrap_json(meta_path)

    # Meme organisation de sortie que le mode lot si la prefecture est detectee.
    clean_text = clean_ocr_text(raw_text)
    metadata_raa = _normalize_meta(
        _safe_call("extract_metadata", extract_metadata, dict(DEFAULT_META), clean_text, attrap_meta)
    )
    pref_dir = _pref_dir_name_from_meta(metadata_raa)
    target_dir = Path(out_dir) / pref_dir / txt_path.stem
    process_raa(txt_path.stem, raw_text, attrap_meta, target_dir)


def cli() -> None:
    # Entree du script en ligne de commande: on lit les options puis on lance le bon mode.
    parser = argparse.ArgumentParser()
    parser.add_argument("raa_txt", nargs="?")
    parser.add_argument("metadata", nargs="?")
    parser.add_argument("--output", nargs="?", default="output")
    parser.add_argument("--mode", choices=["auto", "file", "pref", "whole"], default="auto")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--prefecture")
    args = parser.parse_args()

    Path(args.output).mkdir(parents=True, exist_ok=True)

    # Mode auto:
    # - sans arguments positionnels -> traite tout data/
    # - avec raa_txt + metadata -> traite un seul fichier
    mode = args.mode
    if mode == "auto":
        if args.raa_txt and args.metadata:
            mode = "file"
        elif not args.raa_txt and not args.metadata:
            mode = "whole"
        else:
            parser.error("En mode auto, fournir soit 0 argument, soit raa_txt + metadata")

    if mode == "whole":
        _run_batch(args.data_dir, args.output)
        return

    if mode == "pref":
        if not args.prefecture:
            parser.error("--prefecture est requis avec --mode pref")
        _run_batch(args.data_dir, args.output, prefecture=args.prefecture)
        return

    if not args.raa_txt or not args.metadata:
        parser.error("raa_txt et metadata sont requis en mode file")
    _run_single_file(args.raa_txt, args.metadata, args.output)


if __name__ == "__main__":
    cli()

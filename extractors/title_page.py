from __future__ import annotations
import re
from typing import List, Dict


# On accepte les prefixes sur 1 a 3 chiffres, 2A/2B et les codes DOM de type R02.
_NUM_RE = re.compile(r"\b(?:\d{1,3}|2A|2B|R\d{2})-\d{4}-\d{2}-\d{2}-\d{5}\b", re.IGNORECASE)


def _clean_title(raw: str) -> str:
    cleaned = re.sub(r"\(\d+\s*pages?\)\s*Page\s*\d+", "", raw, flags=re.I)
    return re.sub(r"\s+", " ", cleaned).strip(" -—–\t\r\n")


def extract_title_pages(text: str) -> List[Dict[str, str]]:
    # On découpe le texte en lignes et on les parcours a la recherche de numeros de titre
    lines = text.splitlines()

    # Liste finale
    results: List[Dict[str, str]] = []

    # Ensemble des numeros deja trouves pour eviter les doublons.
    seen: set[str] = set()

    #on parcours les lignes a la recherche de numeros de titre
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        # Cherche un numero d'acte dans la ligne.
        match = _NUM_RE.search(line)
        if not match:
            i += 1
            continue

        # On ignore les numeros cites au milieu d'une phrase, par exemple dans un "Vu l'arrete n° ...".
        prefix = line[:match.start()]
        normalized_prefix = prefix.strip(" -:\t\r\n")
        if normalized_prefix and normalized_prefix.upper() != "ACTE PUBLIABLE":
            if re.search(r"[A-Za-z0-9]", normalized_prefix):
                i += 1
                continue
        elif re.search(r"[0-9]", normalized_prefix):
            i += 1
            continue

        # On ignore aussi le cas ou le numero est seulement la suite d'un "n°" coupe a la ligne precedente.
        if i > 0:
            previous_line = lines[i - 1].strip().replace("Â", "")
            if re.search(r"(?i)\bn(?:\s*[°º])\s*$", previous_line):
                i += 1
                continue

        # Numero retenu pour cette entree.
        numero = match.group()
        if numero in seen:
            i += 1
            continue
        seen.add(numero)
        # Morceaux de titre collectes (ligne courante + lignes suivantes).
        title_parts: list[str] = []

        # Texte apres le numero sur la meme ligne (souvent debut du titre).
        remainder = line[match.end() :].strip(" -—–:")
        if remainder:
            title_parts.append(remainder)

        # Regarde les lignes suivantes pour completer le titre (max 3 morceaux au total).
        j = i + 1
        while j < n and len(title_parts) < 3:
            nxt = lines[j].strip()
            # On stoppe si ligne vide, nouveau numero, ou ligne uniquement numerique.
            if (
                not nxt
                or _NUM_RE.search(nxt)
                or re.fullmatch(r"\d+", nxt)
            ):
                break
            title_parts.append(nxt)
            j += 1

        # Nettoyage final du titre (espaces, mentions de pagination, tirets en bord).
        titre = _clean_title(" ".join(title_parts))
        results.append({"numero": numero, "titre": titre})

        # Saute les lignes deja consommees pour ce titre.
        i = max(j, i + 1)

    return results

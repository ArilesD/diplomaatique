import re
import unicodedata
from typing import Dict, Optional
from urllib.parse import unquote


# On decrit ici les formats complets rencontres pour un numero RAA.
FULL_RAA_RE = re.compile(r"\b((?:\d{1,3}|2A|2B|R\d{2})-\d{4}-\d{3})\b", re.IGNORECASE)

# On garde aussi le format des numeros d'arretes pour recuperer un code de prefecture fiable.
ARRETE_RE = re.compile(r"\b((?:\d{1,3}|2A|2B|R\d{2})-\d{4}-\d{2}-\d{2}-\d{5})\b", re.IGNORECASE)

# On garde un format ISO simple pour la date de publication.
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# On mappe les mois en ASCII normalise pour eviter les soucis d'accents.
MONTHS = {
    "JANVIER": "01",
    "FEVRIER": "02",
    "MARS": "03",
    "AVRIL": "04",
    "MAI": "05",
    "JUIN": "06",
    "JUILLET": "07",
    "AOUT": "08",
    "SEPTEMBRE": "09",
    "OCTOBRE": "10",
    "NOVEMBRE": "11",
    "DECEMBRE": "12",
}

# On garde une table complete des prefectures pour remplir le nom final.
PREFECTURES: Dict[str, str] = {
    "01": "Ain",
    "02": "Aisne",
    "03": "Allier",
    "04": "Alpes-de-Haute-Provence",
    "05": "Hautes-Alpes",
    "06": "Alpes-Maritimes",
    "07": "Ardeche",
    "08": "Ardennes",
    "09": "Ariege",
    "10": "Aube",
    "11": "Aude",
    "12": "Aveyron",
    "13": "Bouches-du-Rhone",
    "14": "Calvados",
    "15": "Cantal",
    "16": "Charente",
    "17": "Charente-Maritime",
    "18": "Cher",
    "19": "Correze",
    "2A": "Corse-du-Sud",
    "2B": "Haute-Corse",
    "21": "Cote-d'Or",
    "22": "Cotes-d'Armor",
    "23": "Creuse",
    "24": "Dordogne",
    "25": "Doubs",
    "26": "Drome",
    "27": "Eure",
    "28": "Eure-et-Loir",
    "29": "Finistere",
    "30": "Gard",
    "31": "Haute-Garonne",
    "32": "Gers",
    "33": "Gironde",
    "34": "Herault",
    "35": "Ille-et-Vilaine",
    "36": "Indre",
    "37": "Indre-et-Loire",
    "38": "Isere",
    "39": "Jura",
    "40": "Landes",
    "41": "Loir-et-Cher",
    "42": "Loire",
    "43": "Haute-Loire",
    "44": "Loire-Atlantique",
    "45": "Loiret",
    "46": "Lot",
    "47": "Lot-et-Garonne",
    "48": "Lozere",
    "49": "Maine-et-Loire",
    "50": "Manche",
    "51": "Marne",
    "52": "Haute-Marne",
    "53": "Mayenne",
    "54": "Meurthe-et-Moselle",
    "55": "Meuse",
    "56": "Morbihan",
    "57": "Moselle",
    "58": "Nievre",
    "59": "Nord",
    "60": "Oise",
    "61": "Orne",
    "62": "Pas-de-Calais",
    "63": "Puy-de-Dome",
    "64": "Pyrenees-Atlantiques",
    "65": "Hautes-Pyrenees",
    "66": "Pyrenees-Orientales",
    "67": "Bas-Rhin",
    "68": "Haut-Rhin",
    "69": "Rhone",
    "70": "Haute-Saone",
    "71": "Saone-et-Loire",
    "72": "Sarthe",
    "73": "Savoie",
    "74": "Haute-Savoie",
    "75": "Paris",
    "76": "Seine-Maritime",
    "77": "Seine-et-Marne",
    "78": "Yvelines",
    "79": "Deux-Sevres",
    "80": "Somme",
    "81": "Tarn",
    "82": "Tarn-et-Garonne",
    "83": "Var",
    "84": "Vaucluse",
    "85": "Vendee",
    "86": "Vienne",
    "87": "Haute-Vienne",
    "88": "Vosges",
    "89": "Yonne",
    "90": "Territoire de Belfort",
    "91": "Essonne",
    "92": "Hauts-de-Seine",
    "93": "Seine-Saint-Denis",
    "94": "Val-de-Marne",
    "95": "Val-d'Oise",
    "971": "Guadeloupe",
    "972": "Martinique",
    "973": "Guyane",
    "974": "La Reunion",
    "976": "Mayotte",
}

# On mappe ici les prefixes RAA DOM en codes prefecture attendus dans le dossier data.
OVERSEAS_RAA_CODES = {
    "R01": "971",
    "R02": "972",
    "R03": "973",
    "R04": "974",
    "R06": "976",
}

def trouver_numero_raa(texte: str, url: str) -> str:
    """Cherche le numéro officiel du RAA (ex: 01-2025-034)."""
    
    # Étape 1 : On regarde dans l'URL
    match_url = re.search(r"(\d{2,3}[A-B]?-\d{4}-\d{3})", url, re.IGNORECASE)
    if match_url:
        return match_url.group(1).upper()
    
    # Étape 2 : on fouille dans les 50 premières lignes du texte si on en trouve pas dans l'url
    en_tete = "\n".join(texte.splitlines()[:50])
    match_texte = re.search(r"(\d{2,3}[A-B]?-\d{4}-\d{3})", en_tete, re.IGNORECASE)
    if match_texte:
        return match_texte.group(1).upper()
        
    return None

def trouver_date(texte: str) -> str:
    """Cherche la date de publication dans le texte."""
    
    # On prend les 50 premières lignes et on met tout en majuscules
    en_tete = "\n".join(texte.splitlines()[:50]).upper()
    
    # On cherche un motif comme "PUBLIE LE 15 JANVIER 2025" ou "DU 15 JANVIER 2025"
    match = re.search(r"(?:PUBLI[EÉ]\s+LE|DU)\s+(\d{1,2})\s+([A-Z]+)\s+(\d{4})", en_tete)
    
    if match:
        jour = match.group(1).zfill(2) # zfill(2) met un 0 devant si c'est "1" -> "01"
        mois_lettres = match.group(2)
        annee = match.group(3)
        
        # On traduit le mois en lettres vers un mois en chiffres
        mois_chiffres = MONTHS.get(mois_lettres) 
        if mois_chiffres:
            return f"{annee}-{mois_chiffres}-{jour}"
            
    return None

# 3. La fonction qui est appelée par diplomaatique.py

def extract_metadata(text: str, attrap_metadata: dict) -> dict:
    """Orchestre les recherches et renvoie le dictionnaire final."""
    
    url = attrap_metadata.get("url", "")
    
    # 1. On lance notre chercheur de numéro
    numero_raa = trouver_numero_raa(text, url)
    
    # 2. On déduit la préfecture en coupant le numéro RAA en deux
    pref_id = None
    pref_name = "Unknown"
    
    if numero_raa:
        # Si on a "01-2025-034", split("-")[0] récupère le "01"
        pref_id = numero_raa.split("-")[0]
        
        # Si le code est "1", on le transforme en "01"
        if len(pref_id) == 1:
            pref_id = "0" + pref_id
            
        pref_name = PREFECTURES.get(pref_id, "Unknown")
        
    # 3. On lance notre chercheur de date
    date_pub = trouver_date(text)
    
    # 4. On renvoie le "passeport" final exactement comme diplomaatique.py l'attend
    return {
        "source_pdf": url,
        "numero_raa": numero_raa,
        "date_publication": date_pub,
        "prefecture_id": pref_id,
        "prefecture_name": pref_name
    }
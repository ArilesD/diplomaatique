import json
import re
import sqlite3
import unicodedata
from pathlib import Path
from typing import Any

# Chemins du projet
RACINE_PROJET = Path(__file__).resolve().parent.parent
DOSSIER_BASE = RACINE_PROJET / "Base_donnees"
CHEMIN_DB = DOSSIER_BASE / "arretes.db"
DOSSIER_OUTPUT = RACINE_PROJET / "output"

NOMS_PREFECTURES = {
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
    "20": "Corse",
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
    "2A": "Corse-du-Sud",
    "2B": "Haute-Corse",
    "971": "Guadeloupe",
    "972": "Martinique",
    "973": "Guyane",
    "974": "La Reunion",
    "975": "Saint-Pierre-et-Miquelon",
    "976": "Mayotte",
    "977": "Saint-Barthelemy",
    "978": "Saint-Martin",
    "986": "Wallis-et-Futuna",
    "987": "Polynesie francaise",
    "988": "Nouvelle-Caledonie",
    "HCNC": "Nouvelle-Caledonie",
    "HCPF": "Polynesie francaise",
}


def obtenir_connexion() -> sqlite3.Connection:
    """Ouvre une connexion SQLite."""
    connexion = sqlite3.connect(CHEMIN_DB)
    connexion.row_factory = sqlite3.Row
    connexion.execute("PRAGMA foreign_keys = ON")
    connexion.create_function("normaliser_recherche", 1, _normaliser_recherche_sql)
    return connexion


def _normaliser_recherche_sql(valeur: Any) -> str:
    if valeur is None:
        return ""
    texte = str(valeur).lower().strip()
    texte = unicodedata.normalize("NFD", texte)
    texte = "".join(car for car in texte if unicodedata.category(car) != "Mn")
    return " ".join(texte.split())


def initialiser_base_si_necessaire() -> None:
    """
    Crée la base SQLite si besoin.
    Si la table principale est vide, on importe les données JSON depuis output/.
    """
    DOSSIER_BASE.mkdir(parents=True, exist_ok=True)

    with obtenir_connexion() as connexion:
        _creer_tables(connexion)
        prefectures_corrigees = _corriger_prefectures_existantes(connexion)
        nb_arretes = connexion.execute("SELECT COUNT(*) FROM arretes").fetchone()[0]
        nb_prefectures = connexion.execute(
            """
            SELECT COUNT(DISTINCT prefecture_id)
            FROM arretes
            WHERE prefecture_id IS NOT NULL AND TRIM(prefecture_id) <> ''
            """
        ).fetchone()[0]

        # Si la base est déjà bien remplie, on ne relance pas l'import.
        # Si l'import a été interrompu, on reprend automatiquement.
        import_complet = nb_arretes > 0 and nb_prefectures >= 75
        if import_complet:
            _synchroniser_index_recherche(connexion, nb_arretes, force=prefectures_corrigees)
            return

        if DOSSIER_OUTPUT.exists():
            _importer_depuis_output(connexion)
            nb_arretes = connexion.execute("SELECT COUNT(*) FROM arretes").fetchone()[0]

        _synchroniser_index_recherche(connexion, nb_arretes, force=True)


def _creer_tables(connexion: sqlite3.Connection) -> None:
    """Crée les tables avec les mêmes noms/colonnes que le dump MySQL."""
    script = """
    CREATE TABLE IF NOT EXISTS arretes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        json_id TEXT NOT NULL UNIQUE,
        numero_raa TEXT,
        date_publication TEXT,
        source_pdf TEXT,
        prefecture_id TEXT,
        prefecture_name TEXT,
        numero_arrete TEXT NOT NULL UNIQUE,
        titre TEXT NOT NULL,
        page_debut INTEGER,
        page_fin INTEGER,
        nb_pages INTEGER,
        raw_json TEXT
    );

    CREATE TABLE IF NOT EXISTS articles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        arrete_id INTEGER NOT NULL,
        numero_article TEXT NOT NULL,
        contenu TEXT NOT NULL,
        ordre_article INTEGER NOT NULL,
        UNIQUE (arrete_id, ordre_article),
        FOREIGN KEY (arrete_id) REFERENCES arretes(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS autorite_decisionnaire (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        arrete_id INTEGER NOT NULL UNIQUE,
        nom TEXT,
        fonction TEXT,
        institution TEXT,
        ligne TEXT,
        FOREIGN KEY (arrete_id) REFERENCES arretes(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS autorite_emettrice (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        arrete_id INTEGER NOT NULL UNIQUE,
        nom TEXT,
        fonction TEXT,
        service TEXT,
        administration TEXT,
        ligne TEXT,
        FOREIGN KEY (arrete_id) REFERENCES arretes(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS considerants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        arrete_id INTEGER NOT NULL,
        texte TEXT NOT NULL,
        ordre_considerant INTEGER NOT NULL,
        UNIQUE (arrete_id, ordre_considerant),
        FOREIGN KEY (arrete_id) REFERENCES arretes(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS services (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        arrete_id INTEGER NOT NULL UNIQUE,
        service TEXT,
        direction_bureau_cabinet TEXT,
        FOREIGN KEY (arrete_id) REFERENCES arretes(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS signataire (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        arrete_id INTEGER NOT NULL UNIQUE,
        nom TEXT,
        fonction TEXT,
        date_signature TEXT,
        lieu_signature TEXT,
        ligne TEXT,
        FOREIGN KEY (arrete_id) REFERENCES arretes(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS visas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        arrete_id INTEGER NOT NULL,
        texte TEXT NOT NULL,
        ordre_visa INTEGER NOT NULL,
        UNIQUE (arrete_id, ordre_visa),
        FOREIGN KEY (arrete_id) REFERENCES arretes(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS voies_recours (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        arrete_id INTEGER NOT NULL UNIQUE,
        voies_recours TEXT,
        delai_recours TEXT,
        juridiction_competente TEXT,
        texte_explicatif_recours TEXT,
        FOREIGN KEY (arrete_id) REFERENCES arretes(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS annexes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        arrete_id INTEGER NOT NULL,
        titre TEXT,
        contenu TEXT NOT NULL,
        ordre_annexe INTEGER NOT NULL,
        UNIQUE (arrete_id, ordre_annexe),
        FOREIGN KEY (arrete_id) REFERENCES arretes(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_arretes_date ON arretes(date_publication);
    CREATE INDEX IF NOT EXISTS idx_arretes_prefecture ON arretes(prefecture_name);
    CREATE INDEX IF NOT EXISTS idx_arretes_numero ON arretes(numero_arrete);
    """
    connexion.executescript(script)
    connexion.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS index_recherche USING fts5(
            arrete_id UNINDEXED,
            titre,
            numero_arrete,
            prefecture,
            texte,
            date_publication,
            tokenize = 'unicode61 remove_diacritics 2'
        )
        """
    )


def _synchroniser_index_recherche(
    connexion: sqlite3.Connection, nb_arretes: int, force: bool = False
) -> None:
    """
    Garde l'index FTS aligné avec la table des arrêtés.
    """
    nb_indexes = connexion.execute("SELECT COUNT(*) FROM index_recherche").fetchone()[0]
    if not force and nb_indexes == nb_arretes:
        return

    connexion.execute("DELETE FROM index_recherche")
    connexion.execute(
        """
        INSERT INTO index_recherche (
            arrete_id, titre, numero_arrete, prefecture, texte, date_publication
        )
        SELECT
            a.id,
            COALESCE(a.titre, ''),
            COALESCE(a.numero_arrete, ''),
            COALESCE(a.prefecture_name, ''),
            TRIM(
                COALESCE(
                    (SELECT group_concat(COALESCE(numero_article, '') || ' ' || COALESCE(contenu, ''), ' ')
                     FROM articles
                     WHERE arrete_id = a.id),
                    ''
                ) || ' ' ||
                COALESCE(
                    (SELECT group_concat(COALESCE(texte, ''), ' ')
                     FROM considerants
                     WHERE arrete_id = a.id),
                    ''
                ) || ' ' ||
                COALESCE(
                    (SELECT group_concat(COALESCE(texte, ''), ' ')
                     FROM visas
                     WHERE arrete_id = a.id),
                    ''
                ) || ' ' ||
                COALESCE(
                    (SELECT group_concat(COALESCE(titre, '') || ' ' || COALESCE(contenu, ''), ' ')
                     FROM annexes
                     WHERE arrete_id = a.id),
                    ''
                ) || ' ' ||
                COALESCE(
                    (SELECT COALESCE(nom, '') || ' ' || COALESCE(fonction, '') || ' ' ||
                            COALESCE(service, '') || ' ' || COALESCE(administration, '')
                     FROM autorite_emettrice
                     WHERE arrete_id = a.id),
                    ''
                ) || ' ' ||
                COALESCE(
                    (SELECT COALESCE(nom, '') || ' ' || COALESCE(fonction, '') || ' ' || COALESCE(institution, '')
                     FROM autorite_decisionnaire
                     WHERE arrete_id = a.id),
                    ''
                ) || ' ' ||
                COALESCE(
                    (SELECT COALESCE(service, '') || ' ' || COALESCE(direction_bureau_cabinet, '')
                     FROM services
                     WHERE arrete_id = a.id),
                    ''
                ) || ' ' ||
                COALESCE(
                    (SELECT COALESCE(nom, '') || ' ' || COALESCE(fonction, '') || ' ' || COALESCE(lieu_signature, '')
                     FROM signataire
                     WHERE arrete_id = a.id),
                    ''
                )
            ),
            COALESCE(a.date_publication, '')
        FROM arretes a
        """
    )
    connexion.commit()


def _importer_depuis_output(connexion: sqlite3.Connection) -> None:
    """
    Importe les arrêtés depuis output/ vers la base SQLite.
    On garde un code simple pour rester lisible.
    """
    curseur = connexion.cursor()
    fichiers = DOSSIER_OUTPUT.rglob("*.json")

    compteur = 0
    for index, chemin_json in enumerate(fichiers, start=1):
        donnees = _lire_json(chemin_json)
        if not _json_est_un_arrete(donnees):
            continue

        if _inserer_arrete_complet(curseur, donnees, chemin_json):
            compteur += 1

        if index % 250 == 0:
            connexion.commit()

    connexion.commit()
    print(f"[Base] {compteur} arrete(s) importe(s) dans {CHEMIN_DB}")


def _lire_json(chemin_json: Path) -> dict[str, Any]:
    try:
        with chemin_json.open("r", encoding="utf-8") as fichier:
            contenu = json.load(fichier)
            return _nettoyer_objet(contenu)
    except (OSError, json.JSONDecodeError):
        return {}


def _json_est_un_arrete(donnees: dict[str, Any]) -> bool:
    return bool(
        donnees
        and "id" in donnees
        and "numero_arrete" in donnees
        and "titre" in donnees
        and isinstance(donnees.get("metadata_raa"), dict)
    )


def _inserer_arrete_complet(
    curseur: sqlite3.Cursor, donnees: dict[str, Any], chemin_json: Path | None
) -> bool:
    metadata = donnees.get("metadata_raa", {})
    json_id = _en_texte(donnees.get("id"))
    numero_arrete = _en_texte(donnees.get("numero_arrete"))
    titre = _en_texte(donnees.get("titre"))
    prefecture_id = _trouver_code_prefecture(
        _en_texte(metadata.get("prefecture_id")),
        numero_arrete,
        chemin_json,
    )
    prefecture_name = _trouver_nom_prefecture(
        _en_texte(metadata.get("prefecture_name")),
        prefecture_id,
    )

    if not numero_arrete or not titre:
        return False

    curseur.execute(
        """
        INSERT OR IGNORE INTO arretes (
            json_id, numero_raa, date_publication, source_pdf, prefecture_id, prefecture_name,
            numero_arrete, titre, page_debut, page_fin, nb_pages, raw_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            json_id,
            _en_texte(metadata.get("numero_raa")),
            _en_texte(metadata.get("date_publication")),
            _en_texte(metadata.get("source_pdf")),
            prefecture_id,
            prefecture_name,
            numero_arrete,
            titre,
            _en_int(donnees.get("page_debut")),
            _en_int(donnees.get("page_fin")),
            _en_int(donnees.get("nb_pages")),
            json.dumps(donnees, ensure_ascii=False),
        ),
    )

    # Si déjà présent, on ne réinsère pas les détails.
    if curseur.rowcount == 0:
        return False

    arrete_id = curseur.lastrowid

    _inserer_autorite_emettrice(curseur, arrete_id, donnees.get("autorite_emettrice", {}))
    _inserer_autorite_decisionnaire(curseur, arrete_id, donnees.get("autorite_decisionnaire", {}))
    _inserer_services(curseur, arrete_id, donnees.get("services", {}))
    _inserer_signataire(curseur, arrete_id, donnees.get("signataire", {}))
    _inserer_voies_recours(curseur, arrete_id, donnees.get("voies_recours", {}))

    for ordre, texte in enumerate(donnees.get("visas", []), start=1):
        curseur.execute(
            "INSERT INTO visas (arrete_id, texte, ordre_visa) VALUES (?, ?, ?)",
            (arrete_id, _en_texte(texte), ordre),
        )

    for ordre, texte in enumerate(donnees.get("considerants", []), start=1):
        curseur.execute(
            "INSERT INTO considerants (arrete_id, texte, ordre_considerant) VALUES (?, ?, ?)",
            (arrete_id, _en_texte(texte), ordre),
        )

    for ordre, article in enumerate(donnees.get("articles", []), start=1):
        curseur.execute(
            """
            INSERT INTO articles (arrete_id, numero_article, contenu, ordre_article)
            VALUES (?, ?, ?, ?)
            """,
            (
                arrete_id,
                _en_texte(article.get("numero")),
                _en_texte(article.get("contenu")),
                ordre,
            ),
        )

    for ordre, annexe in enumerate(donnees.get("annexes", []), start=1):
        curseur.execute(
            """
            INSERT INTO annexes (arrete_id, titre, contenu, ordre_annexe)
            VALUES (?, ?, ?, ?)
            """,
            (
                arrete_id,
                _en_texte(annexe.get("titre")),
                _en_texte(annexe.get("contenu")),
                ordre,
            ),
        )

    return True


def _inserer_autorite_emettrice(
    curseur: sqlite3.Cursor, arrete_id: int, autorite: dict[str, Any]
) -> None:
    curseur.execute(
        """
        INSERT INTO autorite_emettrice (
            arrete_id, nom, fonction, service, administration, ligne
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            arrete_id,
            _en_texte(autorite.get("nom")),
            _en_texte(autorite.get("fonction")),
            _en_texte(autorite.get("service")),
            _en_texte(autorite.get("administration")),
            _en_texte(autorite.get("ligne")),
        ),
    )


def _inserer_autorite_decisionnaire(
    curseur: sqlite3.Cursor, arrete_id: int, autorite: dict[str, Any]
) -> None:
    curseur.execute(
        """
        INSERT INTO autorite_decisionnaire (
            arrete_id, nom, fonction, institution, ligne
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            arrete_id,
            _en_texte(autorite.get("nom")),
            _en_texte(autorite.get("fonction")),
            _en_texte(autorite.get("institution")),
            _en_texte(autorite.get("ligne")),
        ),
    )


def _inserer_services(curseur: sqlite3.Cursor, arrete_id: int, services: dict[str, Any]) -> None:
    direction = services.get("direction_bureau_cabinet", [])
    if not isinstance(direction, list):
        direction = []

    curseur.execute(
        """
        INSERT INTO services (arrete_id, service, direction_bureau_cabinet)
        VALUES (?, ?, ?)
        """,
        (
            arrete_id,
            _en_texte(services.get("service")),
            json.dumps(direction, ensure_ascii=False),
        ),
    )


def _inserer_signataire(curseur: sqlite3.Cursor, arrete_id: int, signataire: dict[str, Any]) -> None:
    curseur.execute(
        """
        INSERT INTO signataire (
            arrete_id, nom, fonction, date_signature, lieu_signature, ligne
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            arrete_id,
            _en_texte(signataire.get("nom")),
            _en_texte(signataire.get("fonction")),
            _en_texte(signataire.get("date_signature")),
            _en_texte(signataire.get("lieu_signature")),
            _en_texte(signataire.get("ligne")),
        ),
    )


def _inserer_voies_recours(
    curseur: sqlite3.Cursor, arrete_id: int, voies_recours: dict[str, Any]
) -> None:
    liste_voies = voies_recours.get("voiesRecours", [])
    liste_delais = voies_recours.get("delaiRecours", [])
    if not isinstance(liste_voies, list):
        liste_voies = []
    if not isinstance(liste_delais, list):
        liste_delais = []

    curseur.execute(
        """
        INSERT INTO voies_recours (
            arrete_id, voies_recours, delai_recours, juridiction_competente, texte_explicatif_recours
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            arrete_id,
            json.dumps(liste_voies, ensure_ascii=False),
            json.dumps(liste_delais, ensure_ascii=False),
            _en_texte(voies_recours.get("juridictionCompetente")),
            _en_texte(voies_recours.get("texteExplicatifRecours")),
        ),
    )


def obtenir_nom_prefecture_depuis_code(code: str) -> str:
    return NOMS_PREFECTURES.get(_normaliser_code_prefecture(code), "")


def _corriger_prefectures_existantes(connexion: sqlite3.Connection) -> bool:
    """
    Corrige les préfectures déjà importées:
    - normalisation du code (ex: 029 -> 29)
    - remplacement des noms Unknown/vides par un nom déduit du code
    - inférence du code depuis numero_arrete si nécessaire
    """
    lignes = connexion.execute(
        """
        SELECT id, prefecture_id, prefecture_name, numero_arrete
        FROM arretes
        """
    ).fetchall()

    mises_a_jour: list[tuple[str, str, int]] = []
    for ligne in lignes:
        code_initial = _en_texte(ligne["prefecture_id"])
        nom_initial = _en_texte(ligne["prefecture_name"])
        numero_arrete = _en_texte(ligne["numero_arrete"])

        code_corrige = _trouver_code_prefecture(code_initial, numero_arrete, None)
        nom_corrige = _trouver_nom_prefecture(nom_initial, code_corrige)

        if code_corrige != code_initial or nom_corrige != nom_initial:
            mises_a_jour.append((code_corrige, nom_corrige, int(ligne["id"])))

    if mises_a_jour:
        connexion.executemany(
            "UPDATE arretes SET prefecture_id = ?, prefecture_name = ? WHERE id = ?",
            mises_a_jour,
        )
        connexion.commit()
        return True
    return False


def _trouver_code_prefecture(
    code_brut: str, numero_arrete: str, chemin_json: Path | None
) -> str:
    if chemin_json:
        code_chemin = _extraire_code_depuis_chemin(chemin_json)
        if code_chemin:
            return code_chemin

    code = _normaliser_code_prefecture(code_brut)
    if code:
        return code

    code_numero = _extraire_code_depuis_numero_arrete(numero_arrete)
    if code_numero:
        return code_numero

    return ""


def _trouver_nom_prefecture(nom_brut: str, code_prefecture: str) -> str:
    nom = _en_texte(nom_brut)
    if nom and not _est_nom_inconnu(nom):
        return nom
    nom_depuis_code = obtenir_nom_prefecture_depuis_code(code_prefecture)
    if nom_depuis_code:
        return nom_depuis_code
    return "Inconnu"


def _est_nom_inconnu(nom: str) -> bool:
    nom_min = nom.strip().lower()
    return nom_min in {"unknown", "inconnu", "unk", "n/a", "na"}


def _normaliser_code_prefecture(code_brut: str) -> str:
    code = _en_texte(code_brut).upper()
    if not code:
        return ""

    if code.startswith("PREF"):
        code = code[4:]

    if code in {"HCNC", "HCPF", "2A", "2B"}:
        return code

    if code.isdigit():
        if len(code) == 3 and code.startswith("0"):
            code = str(int(code))

        if len(code) <= 2:
            return f"{int(code):02d}"
        return code

    return code


def _extraire_code_depuis_numero_arrete(numero_arrete: str) -> str:
    if not numero_arrete:
        return ""
    resultat = re.match(r"^([0-9]{2,3}|2A|2B)-", numero_arrete.strip(), re.IGNORECASE)
    if not resultat:
        return ""
    return _normaliser_code_prefecture(resultat.group(1))


def _extraire_code_depuis_chemin(chemin_json: Path) -> str:
    for element in chemin_json.parts:
        part = element.lower()
        if part.startswith("pref"):
            return _normaliser_code_prefecture(part[4:])
        if part in {"hcnc", "hcpf"}:
            return _normaliser_code_prefecture(part)
    return ""


def _nettoyer_objet(valeur: Any) -> Any:
    """Nettoie récursivement les textes pour corriger les accents mal encodés."""
    if isinstance(valeur, dict):
        return {cle: _nettoyer_objet(contenu) for cle, contenu in valeur.items()}
    if isinstance(valeur, list):
        return [_nettoyer_objet(element) for element in valeur]
    if isinstance(valeur, str):
        return _corriger_texte(valeur)
    return valeur


def _corriger_texte(texte: str) -> str:
    # On corrige seulement si on détecte un encodage "cassé".
    motifs = ("\u00C3", "\u00C2", "\u00E2", "\u20AC")
    if not any(motif in texte for motif in motifs):
        return texte
    try:
        return texte.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return texte


def _en_int(valeur: Any) -> int | None:
    try:
        if valeur is None or valeur == "":
            return None
        return int(valeur)
    except (TypeError, ValueError):
        return None


def _en_texte(valeur: Any) -> str:
    if valeur is None:
        return ""
    return str(valeur).strip()

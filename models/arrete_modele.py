import json
import re
import sqlite3
import unicodedata
from typing import Any

from models.base_donnees import (
    DOSSIER_OUTPUT,
    initialiser_base_si_necessaire,
    obtenir_connexion,
    obtenir_nom_prefecture_depuis_code,
)


class ArreteModele:
    """Modèle principal pour lire les arrêtés et leurs détails."""

    def __init__(self) -> None:
        initialiser_base_si_necessaire()

    def recuperer_prefectures(self) -> list[dict[str, str]]:
        with obtenir_connexion() as connexion:
            lignes = connexion.execute(
                """
                SELECT prefecture_id, MAX(prefecture_name) AS prefecture_name
                FROM arretes
                WHERE prefecture_id IS NOT NULL AND TRIM(prefecture_id) <> ''
                GROUP BY prefecture_id
                """
            ).fetchall()
        prefectures_par_code: dict[str, str] = {}
        for ligne in lignes:
            code = (ligne["prefecture_id"] or "").strip()
            nom = obtenir_nom_prefecture_depuis_code(code)
            if not nom:
                nom = (ligne["prefecture_name"] or "").strip()
            if not nom or nom.lower() in {"unknown", "inconnu"}:
                nom = f"Code {code}"
            prefectures_par_code[code] = nom

        # On ajoute aussi les codes présents dans output/ pour avoir toute la liste disponible.
        if DOSSIER_OUTPUT.exists():
            for dossier in DOSSIER_OUTPUT.iterdir():
                if not dossier.is_dir():
                    continue
                code = self._code_prefecture_depuis_dossier(dossier.name)
                if not code:
                    continue
                if code not in prefectures_par_code:
                    prefectures_par_code[code] = obtenir_nom_prefecture_depuis_code(code) or f"Code {code}"

        prefectures: list[dict[str, str]] = [
            {"code": code, "nom": nom} for code, nom in prefectures_par_code.items()
        ]
        prefectures.sort(key=lambda p: p["nom"])
        return prefectures

    def recuperer_dates_disponibles(self, prefecture: str = "", annee: str = "") -> list[str]:
        """
        Retourne uniquement les dates réellement disponibles dans les données.
        On garde un intervalle réaliste pour éviter les dates OCR aberrantes.
        """
        conditions = [
            "date_publication GLOB '????-??-??'",
            "substr(date_publication, 1, 4) BETWEEN '2000' AND '2100'",
        ]
        parametres: list[str] = []
        if prefecture:
            conditions.append("(prefecture_id = ? OR prefecture_name = ?)")
            parametres.extend([prefecture, prefecture])
        if annee:
            conditions.append("substr(date_publication, 1, 4) = ?")
            parametres.append(annee)

        clause_where = " AND ".join(conditions)
        requete = f"""
            SELECT DISTINCT date_publication
            FROM arretes
            WHERE {clause_where}
            ORDER BY date_publication DESC
        """

        with obtenir_connexion() as connexion:
            lignes = connexion.execute(requete, parametres).fetchall()
        return [ligne["date_publication"] for ligne in lignes if ligne["date_publication"]]

    def recuperer_annees_disponibles(self, prefecture: str = "") -> list[str]:
        """Retourne les annees disponibles selon la prefecture choisie."""
        conditions = [
            "date_publication GLOB '????-??-??'",
            "substr(date_publication, 1, 4) BETWEEN '2000' AND '2100'",
        ]
        parametres: list[str] = []
        if prefecture:
            conditions.append("(prefecture_id = ? OR prefecture_name = ?)")
            parametres.extend([prefecture, prefecture])

        clause_where = " AND ".join(conditions)
        requete = f"""
            SELECT DISTINCT substr(date_publication, 1, 4) AS annee
            FROM arretes
            WHERE {clause_where}
            ORDER BY annee DESC
        """

        with obtenir_connexion() as connexion:
            lignes = connexion.execute(requete, parametres).fetchall()
        return [ligne["annee"] for ligne in lignes if ligne["annee"]]

    def rechercher_arretes(
        self,
        mot_cle: str = "",
        prefecture: str = "",
        date_publication: str = "",
        annee: str = "",
        limite: int | None = None,
    ) -> list[dict[str, Any]]:
        conditions = []
        parametres_filtres: list[Any] = []
        if prefecture:
            conditions.append("(a.prefecture_id = ? OR a.prefecture_name = ?)")
            parametres_filtres.extend([prefecture, prefecture])
        if annee:
            conditions.append("substr(a.date_publication, 1, 4) = ?")
            parametres_filtres.append(annee)
        if date_publication:
            conditions.append("a.date_publication = ?")
            parametres_filtres.append(date_publication)

        clause_filtres = " AND ".join(conditions)
        if clause_filtres:
            clause_filtres = f"AND {clause_filtres}"

        lignes: list[sqlite3.Row]
        if mot_cle.strip():
            requete_fts_stricte = self._construire_requete_fts(mot_cle, mode="strict")
            requete_fts_souple = self._construire_requete_fts(mot_cle, mode="souple")
            if requete_fts_stricte:
                lignes = self._chercher_via_fts(
                    requete_fts=requete_fts_stricte,
                    clause_filtres=clause_filtres,
                    parametres_filtres=parametres_filtres,
                    limite=limite,
                )
                if not lignes and requete_fts_souple and requete_fts_souple != requete_fts_stricte:
                    lignes = self._chercher_via_fts(
                        requete_fts=requete_fts_souple,
                        clause_filtres=clause_filtres,
                        parametres_filtres=parametres_filtres,
                        limite=limite,
                    )
            else:
                requete = f"""
                    SELECT
                        a.id,
                        a.titre,
                        a.numero_arrete,
                        a.date_publication,
                        a.prefecture_id,
                        a.prefecture_name,
                        '' AS extrait
                    FROM arretes a
                    WHERE 1=1
                    {clause_filtres}
                    ORDER BY a.date_publication DESC, a.id DESC
                """
                parametres = list(parametres_filtres)
                if limite and limite > 0:
                    requete += "\nLIMIT ?"
                    parametres.append(limite)
                with obtenir_connexion() as connexion:
                    lignes = connexion.execute(requete, parametres).fetchall()
        else:
            requete = f"""
                SELECT
                    a.id,
                    a.titre,
                    a.numero_arrete,
                    a.date_publication,
                    a.prefecture_id,
                    a.prefecture_name,
                    '' AS extrait
                FROM arretes a
                WHERE 1=1
                {clause_filtres}
                ORDER BY a.date_publication DESC, a.id DESC
            """
            parametres = list(parametres_filtres)
            if limite and limite > 0:
                requete += "\nLIMIT ?"
                parametres.append(limite)
            with obtenir_connexion() as connexion:
                lignes = connexion.execute(requete, parametres).fetchall()

        resultat: list[dict[str, Any]] = []
        for ligne in lignes:
            arrete = dict(ligne)
            code = (arrete.get("prefecture_id") or "").strip()
            nom = obtenir_nom_prefecture_depuis_code(code)
            if not nom:
                nom = (arrete.get("prefecture_name") or "").strip()
            if not nom or nom.lower() in {"unknown", "inconnu"}:
                nom = "Inconnue"
            arrete["prefecture_affiche"] = nom
            arrete["extrait"] = (arrete.get("extrait") or "").strip()
            resultat.append(arrete)
        return resultat

    def _chercher_via_fts(
        self,
        requete_fts: str,
        clause_filtres: str,
        parametres_filtres: list[Any],
        limite: int | None,
    ) -> list[sqlite3.Row]:
        if not requete_fts:
            return []

        requete = f"""
            SELECT
                a.id,
                a.titre,
                a.numero_arrete,
                a.date_publication,
                a.prefecture_id,
                a.prefecture_name,
                snippet(index_recherche, 4, '<mark>', '</mark>', ' ... ', 22) AS extrait,
                bm25(index_recherche, 10.0, 6.0, 2.0, 1.5, 1.0, 0.7) AS score
            FROM index_recherche
            JOIN arretes a ON a.id = index_recherche.arrete_id
            WHERE index_recherche MATCH ?
            {clause_filtres}
            ORDER BY score ASC, a.date_publication DESC, a.id DESC
        """
        parametres = [requete_fts, *parametres_filtres]
        if limite and limite > 0:
            requete += "\nLIMIT ?"
            parametres.append(limite)

        with obtenir_connexion() as connexion:
            return connexion.execute(requete, parametres).fetchall()

    def _construire_requete_fts(self, mot_cle: str, mode: str = "strict") -> str:
        mots = self._extraire_mots_cles(mot_cle)
        if not mots:
            return ""

        groupes: list[str] = []
        for mot in mots:
            variantes = self._construire_variantes_mot(mot, mode)
            termes = []
            for variante in variantes:
                if variante.endswith("*"):
                    termes.append(variante)
                else:
                    termes.append(f'"{variante}"')
            groupe = " OR ".join(termes)
            if len(termes) > 1:
                groupe = f"({groupe})"
            groupes.append(groupe)

        separateur = " AND " if mode == "strict" else " OR "
        return separateur.join(groupes)

    def _extraire_mots_cles(self, texte: str) -> list[str]:
        texte_normalise = self._normaliser_texte(texte)
        mots = re.findall(r"[a-z0-9]+", texte_normalise)
        mots_vides = {
            "de",
            "des",
            "du",
            "la",
            "le",
            "les",
            "un",
            "une",
            "et",
            "ou",
            "a",
            "au",
            "aux",
            "en",
            "dans",
            "pour",
            "par",
            "sur",
            "sous",
            "avec",
            "sans",
            "d",
            "l",
            "arrete",
            "prefecture",
        }
        mots_filtres = [mot for mot in mots if len(mot) >= 2 and mot not in mots_vides]
        return mots_filtres[:8]

    def _construire_variantes_mot(self, mot: str, mode: str) -> list[str]:
        variantes: list[str] = [mot]
        if len(mot) >= 3:
            variantes.append(f"{mot}*")

        # Gestion simple singulier/pluriel.
        if mot.endswith("s") and len(mot) >= 5:
            radical = mot[:-1]
            variantes.append(radical)
            variantes.append(f"{radical}*")
        elif not mot.endswith("s") and len(mot) >= 4:
            variantes.append(f"{mot}s")
            variantes.append(f"{mot}s*")

        if mot.endswith("x") and len(mot) >= 5:
            variantes.append(mot[:-1])

        if mot.endswith("al") and len(mot) >= 5:
            variantes.append(f"{mot[:-2]}aux")

        # Tolerance faute simple: on accepte des prefixes un peu plus courts.
        if mode == "souple" and len(mot) >= 6:
            variantes.append(f"{mot[:-1]}*")
            variantes.append(f"{mot[:-2]}*")

        uniques: list[str] = []
        deja_vus: set[str] = set()
        for variante in variantes:
            if variante and variante not in deja_vus:
                deja_vus.add(variante)
                uniques.append(variante)
        return uniques

    def _normaliser_texte(self, texte: str) -> str:
        texte = (texte or "").lower().strip()
        texte = unicodedata.normalize("NFD", texte)
        texte = "".join(car for car in texte if unicodedata.category(car) != "Mn")
        return " ".join(texte.split())

    def recuperer_detail_arrete(self, arrete_id: int) -> dict[str, Any] | None:
        with obtenir_connexion() as connexion:
            arrete = connexion.execute(
                """
                SELECT id, json_id, numero_raa, date_publication, source_pdf, prefecture_id, prefecture_name,
                       numero_arrete, titre, page_debut, page_fin, nb_pages
                FROM arretes
                WHERE id = ?
                """,
                (arrete_id,),
            ).fetchone()

            if not arrete:
                return None

            autorite_emettrice = connexion.execute(
                """
                SELECT nom, fonction, service, administration, ligne
                FROM autorite_emettrice
                WHERE arrete_id = ?
                """,
                (arrete_id,),
            ).fetchone()

            autorite_decisionnaire = connexion.execute(
                """
                SELECT nom, fonction, institution, ligne
                FROM autorite_decisionnaire
                WHERE arrete_id = ?
                """,
                (arrete_id,),
            ).fetchone()

            services = connexion.execute(
                """
                SELECT service, direction_bureau_cabinet
                FROM services
                WHERE arrete_id = ?
                """,
                (arrete_id,),
            ).fetchone()

            signataire = connexion.execute(
                """
                SELECT nom, fonction, date_signature, lieu_signature, ligne
                FROM signataire
                WHERE arrete_id = ?
                """,
                (arrete_id,),
            ).fetchone()

            voies_recours = connexion.execute(
                """
                SELECT voies_recours, delai_recours, juridiction_competente, texte_explicatif_recours
                FROM voies_recours
                WHERE arrete_id = ?
                """,
                (arrete_id,),
            ).fetchone()

            articles = connexion.execute(
                """
                SELECT numero_article, contenu, ordre_article
                FROM articles
                WHERE arrete_id = ?
                ORDER BY ordre_article
                """,
                (arrete_id,),
            ).fetchall()

            visas = connexion.execute(
                """
                SELECT texte, ordre_visa
                FROM visas
                WHERE arrete_id = ?
                ORDER BY ordre_visa
                """,
                (arrete_id,),
            ).fetchall()

            considerants = connexion.execute(
                """
                SELECT texte, ordre_considerant
                FROM considerants
                WHERE arrete_id = ?
                ORDER BY ordre_considerant
                """,
                (arrete_id,),
            ).fetchall()

            annexes = connexion.execute(
                """
                SELECT titre, contenu, ordre_annexe
                FROM annexes
                WHERE arrete_id = ?
                ORDER BY ordre_annexe
                """,
                (arrete_id,),
            ).fetchall()

        arrete_dict = dict(arrete)
        code = (arrete_dict.get("prefecture_id") or "").strip()
        nom = obtenir_nom_prefecture_depuis_code(code)
        if not nom:
            nom = (arrete_dict.get("prefecture_name") or "").strip()
        if not nom or nom.lower() in {"unknown", "inconnu"}:
            nom = "Inconnue"
        arrete_dict["prefecture_affiche"] = nom

        return {
            "arrete": arrete_dict,
            "autorite_emettrice": dict(autorite_emettrice) if autorite_emettrice else {},
            "autorite_decisionnaire": dict(autorite_decisionnaire) if autorite_decisionnaire else {},
            "services": self._parser_services(services),
            "signataire": dict(signataire) if signataire else {},
            "voies_recours": self._parser_voies_recours(voies_recours),
            "articles": [dict(ligne) for ligne in articles],
            "visas": [dict(ligne) for ligne in visas],
            "considerants": [dict(ligne) for ligne in considerants],
            "annexes": [dict(ligne) for ligne in annexes],
        }

    def _parser_services(self, services: sqlite3.Row | None) -> dict[str, Any]:
        if not services:
            return {"service": "", "direction_bureau_cabinet": []}
        directions = services["direction_bureau_cabinet"]
        try:
            liste_directions = json.loads(directions) if directions else []
        except json.JSONDecodeError:
            liste_directions = []
        if not isinstance(liste_directions, list):
            liste_directions = []
        return {"service": services["service"] or "", "direction_bureau_cabinet": liste_directions}

    def _parser_voies_recours(self, voies: sqlite3.Row | None) -> dict[str, Any]:
        if not voies:
            return {
                "voies_recours": [],
                "delai_recours": [],
                "juridiction_competente": "",
                "texte_explicatif_recours": "",
            }

        try:
            liste_voies = json.loads(voies["voies_recours"]) if voies["voies_recours"] else []
        except json.JSONDecodeError:
            liste_voies = []

        try:
            liste_delais = json.loads(voies["delai_recours"]) if voies["delai_recours"] else []
        except json.JSONDecodeError:
            liste_delais = []

        if not isinstance(liste_voies, list):
            liste_voies = []
        if not isinstance(liste_delais, list):
            liste_delais = []

        return {
            "voies_recours": liste_voies,
            "delai_recours": liste_delais,
            "juridiction_competente": voies["juridiction_competente"] or "",
            "texte_explicatif_recours": voies["texte_explicatif_recours"] or "",
        }

    def _code_prefecture_depuis_dossier(self, nom_dossier: str) -> str:
        nom = (nom_dossier or "").strip().lower()
        if not nom:
            return ""
        if nom in {"hcnc", "hcpf"}:
            return nom.upper()
        if not nom.startswith("pref"):
            return ""
        code = nom[4:].upper()
        if code in {"2A", "2B"}:
            return code
        if code.isdigit():
            if len(code) <= 2:
                return f"{int(code):02d}"
            if len(code) == 3 and code.startswith("0"):
                return str(int(code))
            return code
        return code

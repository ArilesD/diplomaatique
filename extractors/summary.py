
import re
# 1. fonction de nettoyage de titre
def nettoyer_titre(texte_complet: str, numero_acte: str, index_fin: int) -> str:
    """
    Découpe le bloc de texte pour isoler uniquement le titre de l'arrêté.
    """
    # Chercher où se trouve le numéro de l'acte dans la phrase
    index_debut = texte_complet.find(numero_acte)
   
    # Si on a bien trouvé un début et une fin, on "découpe" le texte au milieu
    if index_debut != -1 and index_fin != -1:
        debut_titre = index_debut + len(numero_acte)
        titre = texte_complet[debut_titre:index_fin]
    else:
        titre = texte_complet
       
    # On enlève les espaces en trop et les tirets parasites
    titre_propre = re.sub(r"\s+", " ", titre)
    return titre_propre.strip(" -:\n")

# 2. Fonction d'extraction
def extract_summary(texte: str) -> list:
    """
    Parcourt le sommaire pour en extraire la liste des arrêtés,
    leurs titres et leurs numéros de page.
    """
    lignes = texte.splitlines()
    actes_trouves = []
   
    acte_en_cours = None
    lignes_accumulees = []
    # Trouver un numéro d'acte complet (ex: 01-2025-02-14-00001)
    regex_numero = re.compile(r"((?:\d{2,3}|2A|2B|R\d{2})-\d{4}-\d{2}-\d{2}-\d{5})", re.IGNORECASE)
   
    # Trouver la mention de la page (ex: "(3 pages) Page 12")
    regex_pages = re.compile(r"\((\d+)\s*pages?\).*?Page\s+(\d+)", re.IGNORECASE)
    for ligne in lignes:
        ligne = ligne.strip()
       
        # 1. On vérifie si la ligne contient un nouveau numéro d'acte
        match_numero = regex_numero.search(ligne)
        if match_numero:
            # Si on était déjà en train d'analyser un acte précédent, on le finalise et on le sauvegarde
            if acte_en_cours and lignes_accumulees:
                texte_bloc = " ".join(lignes_accumulees)
                match_pages = regex_pages.search(texte_bloc)
               
                # Si on trouve bien les numéros de pages dans le bloc
                if match_pages:
                    acte_en_cours["nb_pages"] = int(match_pages.group(1))
                    acte_en_cours["page_debut"] = int(match_pages.group(2))
                    # On envoie le texte complet à notre nettoyeur pour en extraire le titre
                    acte_en_cours["titre"] = nettoyer_titre(texte_bloc, acte_en_cours["numero"], match_pages.start())
                    actes_trouves.append(acte_en_cours)
            # 2. On prépare la "boîte" pour le nouvel acte qu'on vient de trouver
            acte_en_cours = {
                "numero": match_numero.group(1),
                "titre": "",
                "nb_pages": None,
                "page_debut": None
            }
            # On réinitialise notre mémoire avec la première ligne de ce nouvel acte
            lignes_accumulees = [ligne]
           
        elif acte_en_cours:
            # 3. Si ce n'est pas un nouveau numéro, c'est la suite du texte de l'acte actuel
            lignes_accumulees.append(ligne)
    # 4. Quand on arrive à la fin du document, on sauvegarde le dernier acte
    if acte_en_cours and lignes_accumulees:
        texte_bloc = " ".join(lignes_accumulees)
        match_pages = regex_pages.search(texte_bloc)
       
        if match_pages:
            acte_en_cours["nb_pages"] = int(match_pages.group(1))
            acte_en_cours["page_debut"] = int(match_pages.group(2))
            acte_en_cours["titre"] = nettoyer_titre(texte_bloc, acte_en_cours["numero"], match_pages.start())
            actes_trouves.append(acte_en_cours)
    return actes_trouves

# DiplomAAtique - Extraction d’arrêtés administratifs

Projet universitaire réalisé en équipe, avec des tâches partagées entre traitement du texte, structuration des données et application web.

DiplomAAtique sépare les arrêtés d’un recueil administratif, extrait leurs informations en JSON et permet de les rechercher dans une interface web.

**Outils :** Python, expressions régulières, SQLite et Flask.

## Aperçu du projet

![Recherche et consultation d’un arrêté dans la base universitaire de DiplomAAtique.](docs/presentation.gif)

La vidéo montre la base universitaire d’origine. Le dépôt fournit **deux arrêtés fictifs** pour reproduire l’extraction et la recherche.

[Image en grand format](docs/apercu.png) · [Voir la vidéo](docs/presentation.mp4)

## Télécharger et lancer

1. Installe [Python 3.14](https://www.python.org/downloads/) si besoin, en cochant **Add python.exe to PATH**.
2. [Télécharge le projet en ZIP](https://github.com/ArilesD/diplomaatique/archive/refs/heads/main.zip), fais **Extraire tout**, puis ouvre le dossier extrait.
3. Double-clique sur **LANCER.cmd**.

Le premier lancement nécessite Internet pour installer les bibliothèques. Garde la fenêtre de lancement ouverte pendant l’utilisation et appuie sur **Entrée** dans cette fenêtre pour arrêter le projet.

Le lancement prépare les deux exemples et la recherche SQLite. Recherche **jardin**, puis ouvre le résultat pour consulter ses articles.

## Comment fonctionne le projet

1. Le programme lit un texte déjà issu de l’OCR et les informations du recueil.
2. Il repère et sépare les arrêtés.
3. Il extrait les informations et les articles en JSON.
4. L’application importe les résultats dans SQLite pour permettre la recherche.

La qualité dépend du texte OCR et de la structure du recueil. Certains champs demandent une relecture.

## Comprendre les fichiers

| Fichier ou dossier | Rôle |
| --- | --- |
| `LANCER.cmd` et `lancer.py` | Préparent les exemples et démarrent l’application. |
| `diplomaatique.py` | Lance le traitement du recueil. |
| `cleaner.py` et `arrete_separate.py` | Nettoient le texte et séparent les arrêtés. |
| `extractors/` | Règles d’extraction des informations. |
| `app.py`, `controllers/`, `models/` et `views/` | Recherche et interface web. |
| `exemple/` et `tests/` | Recueil fictif, résultats attendus et test automatisé. |

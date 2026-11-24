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

<details>
<summary>Reproduire l’exemple depuis le code</summary>

### Reproduire l’exemple

Depuis la racine du dépôt, utilise Python 3.12 ou 3.14 pour générer les résultats et lancer le test automatisé. L’extraction et le test utilisent la bibliothèque standard Python.

```powershell
python diplomaatique.py exemple/raa-fictif.txt exemple/raa-fictif.json --output output
python -m unittest discover -s tests
```

Pour consulter le résultat dans l’interface locale, installe Flask dans ton environnement Python puis lance l’application.

```powershell
python -m pip install -r requirements.txt
python app.py
```

Ouvre [DiplomAAtique sur ton ordinateur](http://127.0.0.1:5000), cherche **jardin**, puis ouvre la fiche du résultat. L’application alimente sa base SQLite locale à partir des fichiers JSON générés dans `output/`.

[Texte du recueil fictif](exemple/raa-fictif.txt) · [Métadonnées du recueil](exemple/raa-fictif.json) · [Premier résultat attendu](exemple/resultat/raa-fictif-01.json) · [Second résultat attendu](exemple/resultat/raa-fictif-02.json)

La qualité des résultats dépend du texte OCR et de la structure du recueil. Certains champs demandent une relecture. Dans l’arrêté fictif du jardin, par exemple, la règle de détection de l’autorité émettrice reprend une phrase de l’article 2 qui mentionne un service.

</details>

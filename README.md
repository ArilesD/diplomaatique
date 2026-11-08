# DiplomAAtique - Extraction d’arrêtés administratifs

DiplomAAtique découpe le texte d’un recueil d’actes administratifs en arrêtés individuels, puis produit un fichier JSON par arrêté. Une interface Flask permet de rechercher les actes et de consulter leurs articles.

Projet universitaire réalisé en équipe. Nous avons partagé les tâches entre le traitement du texte, la structuration des données et l’application.

## Du recueil à la recherche

1. Le programme lit un fichier TXT déjà issu de l’OCR et un fichier JSON de métadonnées.
2. Il nettoie le texte et repère les débuts d’arrêtés à l’aide des numéros, du sommaire ou des pages de titre.
3. Des règles d’extraction isolent notamment les visas, considérants, articles, services et voies de recours lorsque les motifs sont présents.
4. Les fichiers JSON peuvent être importés dans SQLite. L’interface permet alors une recherche par mot-clé ou par filtre.

## Essayer avec deux arrêtés fictifs

L’[exemple de recueil](exemple/raa-fictif.txt) contient un texte sur l’accès à un jardin et un autre sur la réouverture d’une bibliothèque. Le traitement produit deux fichiers séparés, avec respectivement deux articles et un article. [Résultats JSON](exemple/resultat/)

Depuis la racine du dépôt, utilise Python 3.12 pour générer les résultats et lancer le test automatisé. L’extraction et le test utilisent la bibliothèque standard Python.

```bash
python diplomaatique.py exemple/raa-fictif.txt exemple/raa-fictif.json --output output
python -m unittest discover -s tests
```

Pour consulter le résultat dans l’interface locale, installe Flask dans ton environnement Python puis lance l’application.

```bash
python -m pip install -r requirements.txt
python app.py
```

Ouvre [DiplomAAtique sur ton ordinateur](http://127.0.0.1:5000), puis cherche **jardin**. L’application crée sa base SQLite locale à partir des fichiers JSON générés dans `output/`.

## Fichiers principaux

| Fichier ou dossier | Rôle |
| --- | --- |
| `diplomaatique.py` | Exécute le traitement et écrit les fichiers JSON. |
| `cleaner.py` et `arrete_separate.py` | Nettoient le texte OCR et découpent le recueil. |
| `extractors/` | Contient les règles d’extraction des champs. |
| `app.py`, `controllers/`, `models/` et `views/` | Relient la recherche SQLite à l’interface. |

La qualité des résultats dépend de la qualité du texte OCR et de la structure du recueil. L’exemple montre le comportement sur un format contrôlé.

# DiplomAAtique - Extraction d’arrêtés administratifs

DiplomAAtique découpe le texte d’un recueil d’actes administratifs en arrêtés individuels, puis produit un fichier JSON par arrêté. Une interface Flask permet de rechercher les actes et de consulter leurs articles.

Projet universitaire réalisé en équipe. Nous avons partagé les tâches entre le traitement du texte, la structuration des données et l’application.

## Aperçu du projet

![Enregistrement de la base universitaire : recherche « Vidourle », filtre Gard et consultation d’une fiche. Le dépôt téléchargeable fournit deux arrêtés fictifs reproductibles ; recherche « jardin ».](docs/presentation.gif)

Enregistrement de la base universitaire : recherche « Vidourle », filtre Gard et consultation d’une fiche. Le dépôt téléchargeable fournit deux arrêtés fictifs reproductibles ; recherche « jardin ».

[Voir la capture en grand format](docs/apercu.png) · [Voir la vidéo en grand format](docs/presentation.mp4) · [Mon parcours et mes autres projets](https://github.com/ArilesD)

## Télécharger et lancer

1. [Télécharge le ZIP complet](https://github.com/ArilesD/diplomaatique/archive/refs/heads/main.zip).
2. Dans l’Explorateur Windows, fais **Extraire tout**, puis ouvre le dossier extrait.
3. Installe [Python 3.14](https://www.python.org/downloads/) si besoin, en cochant **Add python.exe to PATH**. Double-clique ensuite sur **LANCER.cmd**.

Le lancement extrait les deux arrêtés du recueil fictif fourni, prépare la recherche SQLite et ouvre le site. Recherche **jardin** puis ouvre le résultat pour consulter ses articles.

Garde la fenêtre de lancement ouverte pendant l’utilisation. Appuie sur **Entrée** dans cette fenêtre pour arrêter le projet. La première préparation des applications Python installe les bibliothèques depuis Internet. Les ouvertures suivantes réutilisent l’installation du dossier.

Sous macOS ou Linux avec Python 3.12 à 3.14, ouvre un terminal dans le dossier extrait et exécute **python3 lancer.py**.


## Du recueil à la recherche

1. Le programme lit un fichier TXT déjà issu de l’OCR et un fichier JSON de métadonnées.
2. Il nettoie le texte et repère les débuts d’arrêtés à l’aide des numéros, du sommaire ou des pages de titre.
3. Des règles d’extraction isolent notamment les visas, considérants, articles, services et voies de recours lorsque les motifs sont présents.
4. Les fichiers JSON peuvent être importés dans SQLite. L’interface permet alors une recherche par mot-clé ou par filtre.

## Essayer avec deux arrêtés fictifs

Le [texte du recueil fictif](exemple/raa-fictif.txt) simule la sortie d’un OCR. Le programme le lit avec les [métadonnées du recueil](exemple/raa-fictif.json), puis sépare les deux arrêtés.

| Arrêté repéré dans le texte | Fichier généré | Articles extraits | Mot à rechercher |
| --- | --- | --- | --- |
| `93-2026-01-15-90001` - Accès au jardin des Érables | [raa-fictif-01.json](exemple/resultat/raa-fictif-01.json) | 2 | `jardin` |
| `93-2026-01-15-90002` - Réouverture de la bibliothèque des Tilleuls | [raa-fictif-02.json](exemple/resultat/raa-fictif-02.json) | 1 | `bibliothèque` |

La recherche « jardin » renvoie l’arrêté `93-2026-01-15-90001`. Sa fiche affiche les deux articles, dont celui qui suspend l’accès au jardin le 18 janvier 2026 dans ce scénario fictif.

![Recherche « jardin » dans DiplomAAtique avec un résultat sur l’exemple fictif](docs/recherche-jardin.jpg)

### Reproduire l’exemple

Depuis la racine du dépôt, utilise Python 3.12 ou 3.14 pour générer les résultats et lancer le test automatisé. L’extraction et le test utilisent la bibliothèque standard Python.

```bash
python diplomaatique.py exemple/raa-fictif.txt exemple/raa-fictif.json --output output
python -m unittest discover -s tests
```

Pour consulter le résultat dans l’interface locale, installe Flask dans ton environnement Python puis lance l’application.

```bash
python -m pip install -r requirements.txt
python app.py
```

Ouvre [DiplomAAtique sur ton ordinateur](http://127.0.0.1:5000), cherche **jardin**, puis ouvre la fiche du résultat. L’application alimente sa base SQLite locale à partir des fichiers JSON générés dans `output/`.

## Fichiers principaux

| Fichier ou dossier | Rôle |
| --- | --- |
| `diplomaatique.py` | Exécute le traitement et écrit les fichiers JSON. |
| `cleaner.py` et `arrete_separate.py` | Nettoient le texte OCR et découpent le recueil. |
| `extractors/` | Contient les règles d’extraction des champs. |
| `app.py`, `controllers/`, `models/` et `views/` | Relient la recherche SQLite à l’interface. |

La qualité des résultats dépend du texte OCR et de la structure du recueil. Certains champs demandent une relecture. Dans l’arrêté fictif du jardin, par exemple, la règle de détection de l’autorité émettrice reprend une phrase de l’article 2 qui mentionne un service.

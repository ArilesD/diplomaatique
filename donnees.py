"""Récupère les données originales du projet depuis ses téléchargements GitHub."""
from pathlib import Path
import hashlib
import json
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent

def empreinte(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()

def telecharger():
    source = json.loads((ROOT / "donnees.json").read_text(encoding="utf-8"))
    folder = ROOT / ".local" / "donnees"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / source["fichier"]
    if target.is_file() and empreinte(target) == source["sha256"]:
        return target
    temporary = target.with_suffix(target.suffix + ".part")
    print("Téléchargement des données originales du projet. Cette étape est nécessaire une seule fois.", flush=True)
    request = Request(source["url"], headers={"User-Agent": "ArilesD-project"})
    try:
        digest = hashlib.sha256()
        size = 0
        last = 0
        with urlopen(request, timeout=60) as response, temporary.open("wb") as output:
            while block := response.read(1024 * 1024):
                output.write(block)
                digest.update(block)
                size += len(block)
                if size - last >= 20 * 1024 * 1024:
                    print(f"Données : {100 * size // source['octets']} %", flush=True)
                    last = size
        if size != source["octets"] or digest.hexdigest() != source["sha256"]:
            raise RuntimeError("Le téléchargement des données est incomplet. Relance LANCER.cmd.")
        temporary.replace(target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return target


def preparer_base():
    from contextlib import closing
    import gzip
    import shutil
    import sqlite3
    import time

    source = json.loads((ROOT / "donnees.json").read_text(encoding="utf-8"))
    database = ROOT / "Base_donnees/arretes.db"
    marker = ROOT / ".local/base-originale.json"
    if database.is_file() and marker.is_file():
        if json.loads(marker.read_text(encoding="utf-8")).get("sha256") == source["base_sha256"]:
            return
    archive = telecharger()
    database.parent.mkdir(exist_ok=True)
    temporary = database.with_suffix(".db.part")
    print("Préparation de la base universitaire originale.", flush=True)
    try:
        with gzip.open(archive, "rb") as src, temporary.open("wb") as dst:
            shutil.copyfileobj(src, dst, length=1024 * 1024)
        if empreinte(temporary) != source["base_sha256"]:
            raise RuntimeError("La base décompressée ne correspond pas aux données originales.")
        with closing(sqlite3.connect(temporary)) as connection:
            count = connection.execute("SELECT COUNT(*) FROM arretes").fetchone()[0]
            if count != source["arretes"] or connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise RuntimeError("La vérification de la base d’arrêtés a échoué.")
        if database.is_file():
            database.rename(database.with_name(f"arretes-avant-restauration-{time.time_ns()}.db"))
        temporary.replace(database)
    finally:
        temporary.unlink(missing_ok=True)
    marker.write_text(json.dumps({"sha256": source["base_sha256"], "arretes": count}), encoding="utf-8")
    print(f"Base originale prête : {count} arrêtés.", flush=True)

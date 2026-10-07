# CLAUDE.md — clean-gphotos

Projet PERSO (remote `cqsdx`). Règles globales (Git, doc, secrets, style) : voir `D:\SCRIPTS\CLAUDE.md`. Langue : français.

## Description

Script CLI Python qui transforme un export Google Photos Takeout en bibliothèque propre : dédoublonnage SHA-256, classement `YYYY/MM` d'après le JSON sidecar, albums en symlinks (fallback `.shortcut` sous Windows), correction des dates EXIF des JPEG. Voir `README.md`.

## Structure

- `clean-gphotos.py` : point d'entrée CLI (détection des dossiers Takeout, orchestration)
- `lib/` : `scanner.py`, `dedup.py`, `metadata.py`, `organizer.py`, `albums.py`, `report.py`
- `tests/test_basic.py` : tests
- `_DOC/CHANGELOG.md` : seul fichier de doc

## Commandes

```bash
pip install -r requirements.txt          # piexif, tqdm (Python 3.10+)
python clean-gphotos.py -i <takeout> -o <sortie> [--dry-run] [--move] [--no-exif] [--skip-albums] [-v]
python tests/test_basic.py
```

## Conventions

- Pas de secrets ni d'OAuth dans ce projet.
- Aucune dépendance à un binaire externe (pas d'ExifTool).
- Toute modification : ligne dans `_DOC/CHANGELOG.md` (format strict avec heure), commit + push.

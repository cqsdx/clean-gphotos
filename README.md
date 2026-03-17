# clean-gphotos

Script CLI Python pour transformer un export Google Photos Takeout en bibliothèque photo propre : dédoublonnée, organisée chronologiquement, avec les albums en symlinks.

## Pourquoi ?

Google Takeout exporte chaque photo dans un dossier chronologique (`Photos de 2024/`) **et** dans chaque album où elle apparaît. Résultat : ~50% de doublons. Ce script :

1. Dédoublonne par hash SHA-256
2. Classe en `YYYY/MM/` à partir de la date du JSON sidecar (plus fiable que l'EXIF)
3. Recrée les albums sous forme de symlinks
4. Corrige les dates EXIF dans les fichiers copiés

## Prérequis

- Python 3.10+
- `pip install -r requirements.txt`

## Usage

```bash
# Mode normal (copie)
python clean-gphotos.py -i ~/takeout-export -o ~/photos/google-photos

# Aperçu sans rien toucher
python clean-gphotos.py -i ~/takeout-export -o ~/photos/google-photos --dry-run

# Déplacer au lieu de copier (économise l'espace disque)
python clean-gphotos.py -i ~/takeout-export -o ~/photos/google-photos --move

# Sans correction EXIF ni albums
python clean-gphotos.py -i ~/takeout-export -o ~/photos/google-photos --no-exif --skip-albums

# Verbose
python clean-gphotos.py -i ~/takeout-export -o ~/photos/google-photos -v
```

## Structure de sortie

```
output/
├── ALL_PHOTOS/
│   ├── 2022/
│   │   ├── 01/
│   │   └── 12/
│   ├── 2023/
│   └── 2024/
├── ALBUMS/
│   ├── Vacances 2024/    → symlinks vers ALL_PHOTOS/
│   └── Noël au chalet/   → symlinks vers ALL_PHOTOS/
├── NO_DATE/               fichiers sans date identifiable
└── report.txt             résumé du traitement
```

## Limitations

- **Symlinks Windows** : nécessite le mode développeur activé (Paramètres > Confidentialité et sécurité > Pour les développeurs) ou des droits admin. Si indisponible, crée des fichiers `.shortcut` texte en fallback.
- **EXIF** : la correction des dates EXIF ne fonctionne que pour les JPEG (via `piexif`). Les autres formats reçoivent une mise à jour de la date de modification du fichier (`os.utime`).
- **Pas d'ExifTool** : aucune dépendance à un binaire externe.

## Tests

```bash
python tests/test_basic.py
```

## Après le traitement

Le dossier de sortie est prêt à être intégré dans un backup Restic, synchronisé avec Syncthing, ou importé dans n'importe quel gestionnaire de photos (Immich, PhotoPrism, etc.).

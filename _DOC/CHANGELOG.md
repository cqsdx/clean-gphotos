# Changelog

- [2026-03-17] [12:27] [scanner/clean-gphotos] Sauvegarde mapping fichier→albums dans _album_mapping.json, recréation albums après déplacement
- [2026-03-17] [12:22] [organizer] Fix mode move : supprime la source si fichier déjà présent à destination (doublon skippé)
- [2026-03-17] [12:19] [clean-gphotos] Ajout étape nettoyage : suppression JSON orphelins et dossiers vides
- [2026-03-17] [12:15] [clean-gphotos] Fix détection espaces insécables (U+00A0) dans noms de dossiers, exclusion projets Python
- [2026-03-17] [12:08] [clean-gphotos] Auto-détection des dossiers Google Photos Takeout (Documents, D:), exclusion G:/H:, confirmation interactive

## v1.0.0 — 2026-03-17

- Initial release
- Scan Google Takeout exports (folders + zips)
- JSON sidecar metadata extraction (date, GPS, description)
- SHA-256 content deduplication
- Chronological organization (YYYY/MM)
- Album recreation via symlinks (with .shortcut fallback on Windows)
- EXIF date correction for JPEG files
- Idempotent re-runs (skip already-processed files)
- Dry-run mode
- Progress bar (tqdm)

# Changelog

- [2026-10-07] [14:20] [docs] Ajout CLAUDE.md, bloc « Initial release » converti au format CHANGELOG
- [2026-03-17] [12:27] [scanner/clean-gphotos] Sauvegarde mapping fichier→albums dans _album_mapping.json, recréation albums après déplacement
- [2026-03-17] [12:22] [organizer] Fix mode move : supprime la source si fichier déjà présent à destination (doublon skippé)
- [2026-03-17] [12:19] [clean-gphotos] Ajout étape nettoyage : suppression JSON orphelins et dossiers vides
- [2026-03-17] [12:15] [clean-gphotos] Fix détection espaces insécables (U+00A0) dans noms de dossiers, exclusion projets Python
- [2026-03-17] [12:08] [clean-gphotos] Auto-détection des dossiers Google Photos Takeout (Documents, D:), exclusion G:/H:, confirmation interactive
- [2026-03-17] [16:09] [clean-gphotos] Version initiale : scan Takeout (dossiers + zips), métadonnées JSON sidecar, dédoublonnage SHA-256, organisation YYYY/MM, albums en symlinks (fallback .shortcut), correction EXIF JPEG, relances idempotentes, dry-run, barre de progression tqdm

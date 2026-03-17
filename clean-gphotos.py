#!/usr/bin/env python3
"""Google Photos Takeout post-processor.

Deduplicates, organizes chronologically, creates album symlinks,
and fixes EXIF dates from JSON sidecar metadata.

Auto-détecte les dossiers Google Photos Takeout dans Documents et D:.
"""

import os
import sys
from pathlib import Path

from lib.scanner import scan_directory, save_album_mapping, load_album_mapping
from lib.dedup import deduplicate
from lib.organizer import organize_files
from lib.albums import create_albums
from lib.report import generate_report


# Patterns pour identifier un dossier Google Photos Takeout
GPHOTOS_PATTERNS = [
    "google photos",
    "photos google",
    "takeout",
]

# Dossiers à scanner en priorité
SCAN_PRIORITY_PATHS = [
    Path(os.path.expanduser("~/Documents")),
    Path("D:/"),
]

# Lecteurs à exclure (Google Drive)
EXCLUDED_DRIVES = ["G:", "H:"]

# Dossiers à ignorer (dev, système)
EXCLUDED_FOLDERS = [".git", "node_modules", "venv", "__pycache__"]


def find_gphotos_folders() -> list[Path]:
    """Scanne les emplacements prioritaires pour trouver des dossiers Google Photos.

    Returns:
        Liste des dossiers candidats trouvés.
    """
    candidates = []

    for base_path in SCAN_PRIORITY_PATHS:
        if not base_path.exists():
            continue

        # Vérifie qu'on n'est pas sur un lecteur exclu
        drive = str(base_path)[:2].upper()
        if drive in EXCLUDED_DRIVES:
            continue

        print(f"  Scan de {base_path}...")

        try:
            for root, dirs, files in os.walk(base_path):
                # Exclure les dossiers cachés, système et de dev
                dirs[:] = [d for d in dirs if not d.startswith(('.', '$')) and d.lower() not in EXCLUDED_FOLDERS]

                root_path = Path(root)
                # Normalise les espaces (espace insécable -> espace normal)
                folder_name = root_path.name.lower().replace('\u00a0', ' ')

                # Vérifie si le nom correspond à un pattern Google Photos
                for pattern in GPHOTOS_PATTERNS:
                    if pattern in folder_name:
                        # Exclure si c'est un projet de code (contient des .py)
                        has_py = any(f.endswith('.py') for f in files)
                        if not has_py:
                            candidates.append(root_path)
                        dirs.clear()  # Ne pas scanner les sous-dossiers
                        break

        except PermissionError:
            continue

    return candidates


def prompt_folder_selection(candidates: list[Path]) -> Path | None:
    """Affiche les dossiers trouvés et demande confirmation.

    Args:
        candidates: Liste des dossiers candidats.

    Returns:
        Le dossier sélectionné ou None si annulé.
    """
    if not candidates:
        print("\nAucun dossier Google Photos Takeout trouvé.")
        print(f"Emplacements scannés : {', '.join(str(p) for p in SCAN_PRIORITY_PATHS)}")
        return None

    print("\n" + "=" * 60)
    print("Dossiers Google Photos Takeout détectés :")
    print("=" * 60)

    for i, path in enumerate(candidates, 1):
        # Affiche la taille approximative
        try:
            size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
            size_str = _format_size(size)
        except (PermissionError, OSError):
            size_str = "?"
        print(f"\n  [{i}] {path}")
        print(f"      Taille : {size_str}")

    print("\n" + "-" * 60)

    while True:
        try:
            if len(candidates) == 1:
                choice = input("Traiter ce dossier ? (o/n) : ").strip().lower()
                if choice in ('o', 'oui', 'y', 'yes', ''):
                    return candidates[0]
                elif choice in ('n', 'non', 'no', 'q'):
                    return None
                print("Répondez 'o' pour oui ou 'n' pour non.")
            else:
                choice = input("Sélectionner un dossier (numéro) ou 'q' pour quitter : ").strip()
                if choice.lower() == 'q':
                    return None
                idx = int(choice) - 1
                if 0 <= idx < len(candidates):
                    return candidates[idx]
                print(f"Choix invalide. Entrez un nombre entre 1 et {len(candidates)}.")
        except ValueError:
            print("Entrée invalide.")
        except KeyboardInterrupt:
            print()
            return None


def _format_size(size_bytes: int) -> str:
    """Formate une taille en bytes en format lisible."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def rebuild_albums_from_mapping(album_mapping: dict, output_dir: Path) -> dict:
    """Recrée les albums à partir du mapping sauvegardé.

    Args:
        album_mapping: Dict {filename: [album1, album2, ...]}.
        output_dir: Dossier de sortie contenant ALL_PHOTOS.

    Returns:
        Stats de création.
    """
    stats = {"albums_created": 0, "links_created": 0, "skipped": 0}
    albums_dir = output_dir / "ALBUMS"
    all_photos_dir = output_dir / "ALL_PHOTOS"

    # Construire un index des fichiers dans ALL_PHOTOS
    file_index = {}
    for f in all_photos_dir.rglob("*"):
        if f.is_file():
            file_index[f.name] = f

    # Créer les albums
    albums_created = set()
    for filename, album_names in album_mapping.items():
        if filename not in file_index:
            stats["skipped"] += 1
            continue

        target_path = file_index[filename]

        for album_name in album_names:
            album_dir = albums_dir / album_name

            if album_name not in albums_created:
                album_dir.mkdir(parents=True, exist_ok=True)
                albums_created.add(album_name)
                stats["albums_created"] += 1

            link_path = album_dir / filename

            # Éviter les doublons
            if link_path.exists() or link_path.is_symlink():
                continue

            # Créer le symlink
            try:
                rel_target = os.path.relpath(target_path, link_path.parent)
                link_path.symlink_to(rel_target)
                stats["links_created"] += 1
            except OSError:
                # Fallback : créer un fichier .shortcut
                shortcut_path = link_path.with_suffix(link_path.suffix + ".shortcut")
                try:
                    with open(shortcut_path, "w", encoding="utf-8") as f:
                        f.write(f"target={rel_target}\n")
                        f.write(f"absolute={target_path}\n")
                    stats["links_created"] += 1
                except OSError:
                    stats["skipped"] += 1

    return stats


def cleanup_empty_folders(base_dir: Path) -> dict:
    """Supprime les JSON orphelins et les dossiers vides.

    Args:
        base_dir: Dossier racine à nettoyer.

    Returns:
        Stats du nettoyage.
    """
    stats = {"json_deleted": 0, "folders_deleted": 0}

    # Passe 1 : supprimer les JSON orphelins (pas de média associé)
    for json_file in base_dir.rglob("*.json"):
        # Ignore les JSON dans ALL_PHOTOS et ALBUMS (ce sont les dossiers de sortie)
        if "ALL_PHOTOS" in str(json_file) or "ALBUMS" in str(json_file):
            continue

        # Vérifie si un fichier média associé existe
        parent = json_file.parent
        stem = json_file.stem

        # Les JSON Google Photos ont souvent le pattern: photo.jpg.json ou photo.json
        # Cherche un média avec le même nom (sans .json)
        has_media = False
        for ext in ['.jpg', '.jpeg', '.png', '.gif', '.mp4', '.mov', '.avi', '.heic', '.webp']:
            # Pattern 1: photo.jpg.json -> photo.jpg
            if stem.lower().endswith(ext):
                potential_media = parent / stem
                if potential_media.exists():
                    has_media = True
                    break
            # Pattern 2: photo.json -> photo.jpg
            potential_media = parent / f"{stem}{ext}"
            if potential_media.exists():
                has_media = True
                break

        if not has_media:
            try:
                json_file.unlink()
                stats["json_deleted"] += 1
            except (PermissionError, OSError):
                pass

    # Passe 2 : supprimer les dossiers vides (du plus profond au moins profond)
    all_dirs = sorted(
        [d for d in base_dir.rglob("*") if d.is_dir()],
        key=lambda p: len(p.parts),
        reverse=True
    )

    for folder in all_dirs:
        # Ne pas supprimer ALL_PHOTOS ou ALBUMS
        if folder.name in ("ALL_PHOTOS", "ALBUMS"):
            continue

        try:
            if not any(folder.iterdir()):
                folder.rmdir()
                stats["folders_deleted"] += 1
        except (PermissionError, OSError):
            pass

    return stats


def main():
    """Point d'entrée principal."""
    print("=" * 60)
    print("  Google Photos Takeout Cleaner")
    print("=" * 60)
    print("\nRecherche de dossiers Google Photos Takeout...\n")

    # Auto-détection
    candidates = find_gphotos_folders()
    selected = prompt_folder_selection(candidates)

    if selected is None:
        print("\nOpération annulée.")
        sys.exit(0)

    input_dir = selected
    output_dir = selected  # Traitement in-place

    print(f"\n>>> Traitement de : {input_dir}\n")

    try:
        from tqdm import tqdm
        has_tqdm = True
    except ImportError:
        has_tqdm = False
        print("Note: pip install tqdm pour les barres de progression")

    # Step 1: Scan
    print("[1/7] Scan du dossier...")
    entries = scan_directory(input_dir, verbose=False)
    if not entries:
        print("Aucun fichier média trouvé.")
        sys.exit(0)
    print(f"      {len(entries)} fichiers média trouvés")

    # Step 1b: Sauvegarder le mapping albums AVANT de déplacer les fichiers
    album_count = save_album_mapping(entries, output_dir)
    if album_count > 0:
        print(f"      {album_count} fichiers avec info album sauvegardés")

    # Step 2: Deduplicate
    print("[2/7] Déduplication (SHA-256)...")
    unique, duplicates = deduplicate(entries, verbose=False)
    print(f"      {len(unique)} uniques, {len(duplicates)} doublons")

    # Step 3: Organize
    print(f"[3/7] Organisation dans {output_dir / 'ALL_PHOTOS'}...")
    if has_tqdm:
        bar = tqdm(total=len(unique), desc="      Traitement", unit="fichier")
        callback = lambda: bar.update(1)
    else:
        callback = None

    file_map, organize_stats = organize_files(
        unique,
        output_dir,
        move=True,  # Déplace les fichiers (in-place)
        fix_exif=True,
        dry_run=False,
        verbose=False,
        progress_callback=callback,
    )

    if has_tqdm:
        bar.close()

    # Step 4: Albums
    print("[4/7] Création des albums...")
    album_stats = create_albums(
        unique, file_map, output_dir,
        dry_run=False, verbose=False,
    )
    print(f"      {album_stats['albums_created']} albums, {album_stats['symlinks_created']} symlinks")

    # Step 5: Cleanup
    print("[5/7] Nettoyage (JSON orphelins, dossiers vides)...")
    cleanup_stats = cleanup_empty_folders(input_dir)
    print(f"      {cleanup_stats['json_deleted']} JSON supprimés, {cleanup_stats['folders_deleted']} dossiers vides supprimés")

    # Step 6: Recréer albums depuis le mapping sauvegardé
    print("[6/7] Recréation des albums depuis le mapping...")
    album_mapping = load_album_mapping(output_dir)
    if album_mapping:
        rebuild_stats = rebuild_albums_from_mapping(album_mapping, output_dir)
        print(f"      {rebuild_stats['albums_created']} albums, {rebuild_stats['links_created']} liens")
    else:
        rebuild_stats = {"albums_created": 0, "links_created": 0}
        print("      Aucun mapping trouvé")

    # Step 7: Report
    print("[7/7] Génération du rapport...")
    report = generate_report(
        total_scanned=len(entries),
        unique_count=len(unique),
        duplicate_count=len(duplicates),
        organize_stats=organize_stats,
        album_stats=album_stats,
        duplicates=duplicates,
        output_dir=output_dir,
        dry_run=False,
    )
    print()
    print(report)
    print("\nTerminé.")
    input("\nAppuyez sur Entrée pour fermer...")


if __name__ == "__main__":
    main()

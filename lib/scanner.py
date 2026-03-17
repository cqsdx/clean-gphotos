"""Discover media files and their JSON sidecars in a Google Takeout export."""

import json
import os
import re
import zipfile
import tempfile
from pathlib import Path

ALBUM_MAP_FILENAME = "_album_mapping.json"

MEDIA_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".heic", ".heif",
    ".mp4", ".mov", ".avi", ".mkv", ".webp", ".webm",
    ".tif", ".tiff", ".raw", ".cr2", ".nef", ".arw", ".dng",
    ".m4v", ".3gp", ".mpg", ".mpeg",
}

IGNORED_FILES = {"metadata.json", "print-subscriptions.json", "user-generated-memory-titles.json",
                 "titres-souvenirs-générés-par-utilisateur.json"}

EXCLUDED_DIRS = {"archive", "trash", "bin", "corbeille", "all_photos", "albums", "no_date"}

CHRONO_PATTERN = re.compile(r"^Photos?\s+(de|from)\s+\d{4}$", re.IGNORECASE)


def _long_path(p: str) -> str:
    """Prefix path for Windows long path support."""
    if os.name == "nt" and not p.startswith("\\\\?\\"):
        return "\\\\?\\" + os.path.abspath(p)
    return p


def extract_zips(input_dir: Path, verbose: bool = False) -> list[Path]:
    """Extract any .zip files found in input_dir to a temp directory. Returns list of extra dirs to scan."""
    extra_dirs = []
    zips = list(input_dir.glob("*.zip"))
    if not zips:
        return extra_dirs
    for zf in zips:
        if verbose:
            print(f"  Extracting {zf.name}...")
        tmp = Path(tempfile.mkdtemp(prefix="takeout_"))
        with zipfile.ZipFile(zf, "r") as z:
            z.extractall(tmp)
        extra_dirs.append(tmp)
    return extra_dirs


def is_excluded_dir(dirname: str) -> bool:
    return dirname.lower() in EXCLUDED_DIRS


def is_chrono_dir(dirname: str) -> bool:
    return bool(CHRONO_PATTERN.match(dirname))


def is_media_file(path: Path) -> bool:
    return path.suffix.lower() in MEDIA_EXTENSIONS


def find_json_sidecar(media_path: Path) -> Path | None:
    """Find the JSON sidecar for a media file.

    Google Takeout uses several naming conventions:
      - IMG_1234.jpg.json
      - IMG_1234.json
      - IMG_1234(1).jpg.json  (for duplicates)
      - IMG_1234.jpg(1).json  (variant)

    For edited files like IMG_1234-edited.jpg, also try IMG_1234.jpg.json.
    For truncated names (>47 chars), the JSON may have a shorter name.
    """
    parent = media_path.parent
    name = media_path.name
    stem = media_path.stem
    suffix = media_path.suffix

    # Try in order of likelihood
    candidates = [
        parent / f"{name}.json",           # IMG_1234.jpg.json
        parent / f"{stem}.json",           # IMG_1234.json
    ]

    # Handle (1), (2) suffixes in filename
    paren_match = re.match(r"^(.+?)(\(\d+\))(\.\w+)$", name)
    if paren_match:
        base, num, ext = paren_match.groups()
        candidates.extend([
            parent / f"{base}{ext}{num}.json",    # IMG_1234.jpg(1).json
            parent / f"{base}{num}{ext}.json",    # IMG_1234(1).jpg.json
            parent / f"{base}{ext}.json",          # IMG_1234.jpg.json (without number)
        ])

    # Handle -edited files
    if stem.endswith("-edited"):
        original_stem = stem[:-7]  # Remove "-edited"
        candidates.extend([
            parent / f"{original_stem}{suffix}.json",
            parent / f"{original_stem}.json",
        ])

    # Handle names truncated at 47 chars by Google
    if len(stem) >= 46:
        truncated = stem[:46]
        for f in parent.iterdir():
            if f.suffix == ".json" and f.stem.startswith(truncated) and f.name not in IGNORED_FILES:
                candidates.append(f)

    for candidate in candidates:
        if candidate.exists() and candidate.name not in IGNORED_FILES:
            return candidate
    return None


def scan_directory(input_dir: Path, verbose: bool = False) -> list[dict]:
    """Scan input directory and return list of media entries.

    Each entry is a dict with:
      - 'media_path': Path to the media file
      - 'json_path': Path to JSON sidecar or None
      - 'source_dir': Name of the containing folder (album name or chrono folder)
      - 'is_chrono': Whether it's from a "Photos de YYYY" folder
    """
    entries = []
    seen_paths = set()

    dirs_to_scan = [input_dir]

    # Extract zips if any
    extra_dirs = extract_zips(input_dir, verbose=verbose)
    dirs_to_scan.extend(extra_dirs)

    for scan_dir in dirs_to_scan:
        for root, dirs, files in os.walk(scan_dir):
            root_path = Path(root)

            # Get the top-level folder name relative to input
            try:
                rel = root_path.relative_to(scan_dir)
            except ValueError:
                continue
            parts = rel.parts
            if not parts:
                # Files directly in input root
                top_dir = ""
            else:
                top_dir = parts[0]

            # Skip excluded directories
            if is_excluded_dir(top_dir):
                dirs[:] = []
                continue

            for fname in files:
                fpath = root_path / fname

                if fname.lower() in IGNORED_FILES:
                    continue
                if fpath.suffix.lower() == ".json":
                    continue
                if not is_media_file(fpath):
                    continue

                real_path = str(fpath.resolve())
                if real_path in seen_paths:
                    continue
                seen_paths.add(real_path)

                json_path = find_json_sidecar(fpath)

                entries.append({
                    "media_path": fpath,
                    "json_path": json_path,
                    "source_dir": top_dir,
                    "is_chrono": is_chrono_dir(top_dir) if top_dir else True,
                })

    if verbose:
        print(f"  Found {len(entries)} media files")
    return entries


def save_album_mapping(entries: list[dict], output_dir: Path) -> int:
    """Sauvegarde le mapping fichier→albums dans un fichier JSON.

    Args:
        entries: Liste des entrées avec source_dir et is_chrono.
        output_dir: Dossier où sauvegarder le mapping.

    Returns:
        Nombre d'entrées sauvegardées.
    """
    mapping = {}

    for entry in entries:
        if entry["is_chrono"]:
            continue  # Pas d'album pour les dossiers chrono

        source_dir = entry.get("source_dir", "")
        if not source_dir or source_dir.lower() in EXCLUDED_DIRS:
            continue

        media_path = entry["media_path"]
        # Clé = nom du fichier (pour retrouver après déplacement)
        filename = media_path.name

        if filename not in mapping:
            mapping[filename] = []

        if source_dir not in mapping[filename]:
            mapping[filename].append(source_dir)

    # Sauvegarder
    map_file = output_dir / ALBUM_MAP_FILENAME
    with open(map_file, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)

    return len(mapping)


def load_album_mapping(output_dir: Path) -> dict:
    """Charge le mapping fichier→albums depuis le fichier JSON.

    Args:
        output_dir: Dossier contenant le mapping.

    Returns:
        Dict {filename: [album1, album2, ...]}.
    """
    map_file = output_dir / ALBUM_MAP_FILENAME
    if not map_file.exists():
        return {}

    with open(map_file, "r", encoding="utf-8") as f:
        return json.load(f)

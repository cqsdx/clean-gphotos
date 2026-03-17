"""Copy/move media files into YYYY/MM chronological structure."""

import os
import shutil
from pathlib import Path

from .metadata import resolve_date, read_json_metadata, timestamp_to_ymd, write_exif_date
from .dedup import hash_file


def _safe_path(p: Path) -> str:
    """Return a Windows long-path-safe string."""
    s = str(p)
    if os.name == "nt" and not s.startswith("\\\\?\\"):
        return "\\\\?\\" + os.path.abspath(s)
    return s


def _unique_dest(dest_dir: Path, filename: str, src_hash: str) -> Path:
    """Return a unique destination path, avoiding collisions with different files.

    If a file with the same name exists and has the same hash, returns None (already there).
    If different content, appends _1, _2, etc.
    """
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    candidate = dest_dir / filename

    counter = 0
    while candidate.exists():
        existing_hash = hash_file(candidate)
        if existing_hash == src_hash:
            return None  # Already exists with same content
        counter += 1
        candidate = dest_dir / f"{stem}_{counter}{suffix}"

    return candidate


def organize_files(
    entries: list[dict],
    output_dir: Path,
    move: bool = False,
    fix_exif: bool = True,
    dry_run: bool = False,
    verbose: bool = False,
    progress_callback=None,
) -> dict:
    """Organize unique media files into OUTPUT/ALL_PHOTOS/YYYY/MM/.

    Returns a mapping of {original_path_str: dest_path} for album symlink creation.
    Also returns stats dict.
    """
    all_photos_dir = output_dir / "ALL_PHOTOS"
    no_date_dir = output_dir / "NO_DATE"

    file_map = {}  # hash -> dest_path (for album symlinks)
    stats = {
        "copied": 0,
        "skipped": 0,
        "exif_fixed": 0,
        "no_date": 0,
        "errors": 0,
        "bytes_copied": 0,
    }

    for entry in entries:
        try:
            media_path = entry["media_path"]
            json_meta = read_json_metadata(entry.get("json_path"))
            timestamp, date_source = resolve_date(json_meta, media_path)

            file_hash = entry.get("hash", hash_file(media_path))
            if not file_hash:
                stats["errors"] += 1
                continue

            if date_source == "fallback":
                dest_dir = no_date_dir
                stats["no_date"] += 1
            else:
                year, month = timestamp_to_ymd(timestamp)
                dest_dir = all_photos_dir / year / month

            if dry_run:
                dest = dest_dir / media_path.name
                if verbose:
                    print(f"  [DRY-RUN] {media_path} -> {dest}")
                file_map[file_hash] = dest
                entry["dest_path"] = dest
                stats["copied"] += 1
                if progress_callback:
                    progress_callback()
                continue

            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = _unique_dest(dest_dir, media_path.name, file_hash)

            if dest is None:
                # Already exists with same content
                # Find the existing file for the map
                existing = dest_dir / media_path.name
                file_map[file_hash] = existing
                entry["dest_path"] = existing
                stats["skipped"] += 1
                # Si mode move et fichier source différent de destination, supprimer la source
                if move and media_path.resolve() != existing.resolve():
                    try:
                        media_path.unlink()
                    except (PermissionError, OSError):
                        pass
                if progress_callback:
                    progress_callback()
                continue

            if move:
                shutil.move(_safe_path(media_path), _safe_path(dest))
            else:
                shutil.copy2(_safe_path(media_path), _safe_path(dest))

            stats["copied"] += 1
            stats["bytes_copied"] += media_path.stat().st_size

            # Fix EXIF dates
            if fix_exif and date_source == "json":
                if write_exif_date(dest, timestamp):
                    stats["exif_fixed"] += 1

            file_map[file_hash] = dest
            entry["dest_path"] = dest

            if verbose:
                print(f"  {media_path.name} -> {dest} [{date_source}]")

        except Exception as e:
            stats["errors"] += 1
            if verbose:
                print(f"  ERROR: {entry.get('media_path', '?')}: {e}")

        if progress_callback:
            progress_callback()

    return file_map, stats

"""Deduplicate media files by content hash (SHA-256)."""

import hashlib
from pathlib import Path

BLOCK_SIZE = 8192


def hash_file(path: Path) -> str:
    """Compute SHA-256 hash of a file, reading in 8KB blocks."""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            while True:
                block = f.read(BLOCK_SIZE)
                if not block:
                    break
                h.update(block)
    except OSError:
        return ""
    return h.hexdigest()


def deduplicate(entries: list[dict], verbose: bool = False) -> tuple[list[dict], list[dict]]:
    """Deduplicate entries by file content hash.

    When duplicates are found, prefer keeping the one from an album folder
    (is_chrono=False) over a chronological folder (is_chrono=True).

    Returns (unique_entries, duplicate_entries).
    """
    hash_map: dict[str, list[dict]] = {}

    for entry in entries:
        file_hash = hash_file(entry["media_path"])
        if not file_hash:
            continue
        entry["hash"] = file_hash
        hash_map.setdefault(file_hash, []).append(entry)

    unique = []
    duplicates = []

    for file_hash, group in hash_map.items():
        if len(group) == 1:
            unique.append(group[0])
            continue

        # Sort: album files first (is_chrono=False), then alphabetically by path
        group.sort(key=lambda e: (e["is_chrono"], str(e["media_path"])))

        # Keep the first one (album preferred), rest are duplicates
        kept = group[0]
        unique.append(kept)

        for dup in group[1:]:
            dup["kept_as"] = str(kept["media_path"])
            duplicates.append(dup)

        # Merge album info from duplicates into the kept entry
        # So we know all albums this file belongs to
        albums = set()
        for e in group:
            if not e["is_chrono"] and e["source_dir"]:
                albums.add(e["source_dir"])
        kept["albums"] = albums

    if verbose:
        print(f"  {len(unique)} unique files, {len(duplicates)} duplicates removed")

    return unique, duplicates

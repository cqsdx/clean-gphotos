"""Create album directories with symlinks to organized photos."""

import os
from pathlib import Path


def _try_symlink(link_path: Path, target_path: Path) -> bool:
    """Try to create a relative symlink. Returns True on success."""
    try:
        rel_target = os.path.relpath(target_path, link_path.parent)
        link_path.symlink_to(rel_target)
        return True
    except OSError:
        return False


def _create_shortcut_file(link_path: Path, target_path: Path):
    """Create a .shortcut text file as fallback when symlinks aren't available."""
    shortcut_path = link_path.with_suffix(link_path.suffix + ".shortcut")
    rel_target = os.path.relpath(target_path, shortcut_path.parent)
    with open(shortcut_path, "w", encoding="utf-8") as f:
        f.write(f"target={rel_target}\n")
        f.write(f"absolute={target_path}\n")


def _test_symlinks(test_dir: Path) -> bool:
    """Test if symlinks work in the given directory."""
    test_dir.mkdir(parents=True, exist_ok=True)
    test_target = test_dir / ".symlink_test_target"
    test_link = test_dir / ".symlink_test_link"
    try:
        test_target.touch()
        test_link.symlink_to(test_target.name)
        return True
    except OSError:
        return False
    finally:
        try:
            test_link.unlink(missing_ok=True)
            test_target.unlink(missing_ok=True)
        except OSError:
            pass


def create_albums(
    entries: list[dict],
    file_map: dict,
    output_dir: Path,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict:
    """Create album directories with symlinks to files in ALL_PHOTOS.

    Returns stats dict.
    """
    albums_dir = output_dir / "ALBUMS"
    stats = {
        "albums_created": 0,
        "symlinks_created": 0,
        "shortcuts_created": 0,
        "skipped": 0,
        "symlinks_supported": True,
    }

    # Collect album -> files mapping
    album_files: dict[str, list[dict]] = {}
    for entry in entries:
        if entry["is_chrono"] or not entry.get("source_dir"):
            # Also check merged albums from dedup
            albums = entry.get("albums", set())
            for album_name in albums:
                album_files.setdefault(album_name, []).append(entry)
            continue

        album_name = entry["source_dir"]
        album_files.setdefault(album_name, []).append(entry)

    if not album_files:
        return stats

    # Test symlink support
    if not dry_run:
        symlinks_ok = _test_symlinks(albums_dir)
        stats["symlinks_supported"] = symlinks_ok
        if not symlinks_ok and verbose:
            print("  WARNING: Symlinks not supported. Using .shortcut files as fallback.")
            print("  Enable Developer Mode in Windows Settings to use symlinks.")
    else:
        symlinks_ok = True

    for album_name, files in sorted(album_files.items()):
        album_dir = albums_dir / album_name

        if dry_run:
            if verbose:
                print(f"  [DRY-RUN] Album: {album_name} ({len(files)} files)")
            stats["albums_created"] += 1
            stats["symlinks_created"] += len(files)
            continue

        album_dir.mkdir(parents=True, exist_ok=True)
        stats["albums_created"] += 1

        for entry in files:
            file_hash = entry.get("hash", "")
            dest_path = entry.get("dest_path") or file_map.get(file_hash)

            if not dest_path or not Path(dest_path).exists():
                stats["skipped"] += 1
                continue

            dest_path = Path(dest_path)
            link_path = album_dir / dest_path.name

            # Avoid collision
            if link_path.exists() or link_path.is_symlink():
                stats["skipped"] += 1
                continue

            if symlinks_ok:
                if _try_symlink(link_path, dest_path):
                    stats["symlinks_created"] += 1
                else:
                    _create_shortcut_file(link_path, dest_path)
                    stats["shortcuts_created"] += 1
            else:
                _create_shortcut_file(link_path, dest_path)
                stats["shortcuts_created"] += 1

        if verbose:
            print(f"  Album: {album_name} ({len(files)} files)")

    return stats

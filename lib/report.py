"""Generate a summary report of the processing."""

from datetime import datetime, timezone
from pathlib import Path


def _human_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / 1024 ** 2:.1f} MB"
    else:
        return f"{size_bytes / 1024 ** 3:.2f} GB"


def generate_report(
    total_scanned: int,
    unique_count: int,
    duplicate_count: int,
    organize_stats: dict,
    album_stats: dict,
    duplicates: list[dict],
    output_dir: Path,
    dry_run: bool = False,
) -> str:
    """Generate and save a human-readable report."""

    space_saved = sum(
        d["media_path"].stat().st_size for d in duplicates
        if d["media_path"].exists()
    )

    lines = [
        "=" * 60,
        "  Google Photos Takeout — Processing Report",
        "=" * 60,
        "",
        f"  Date:              {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"  Mode:              {'DRY RUN' if dry_run else 'LIVE'}",
        "",
        "  FILES",
        f"    Scanned:         {total_scanned}",
        f"    Unique:          {unique_count}",
        f"    Duplicates:      {duplicate_count}",
        f"    Space saved:     {_human_size(space_saved)}",
        "",
        "  ORGANIZATION",
        f"    Copied/moved:    {organize_stats.get('copied', 0)}",
        f"    Already present: {organize_stats.get('skipped', 0)}",
        f"    EXIF fixed:      {organize_stats.get('exif_fixed', 0)}",
        f"    No date found:   {organize_stats.get('no_date', 0)}",
        f"    Errors:          {organize_stats.get('errors', 0)}",
        "",
        "  ALBUMS",
        f"    Albums created:  {album_stats.get('albums_created', 0)}",
        f"    Symlinks:        {album_stats.get('symlinks_created', 0)}",
    ]

    if album_stats.get("shortcuts_created", 0) > 0:
        lines.append(f"    Shortcuts:       {album_stats['shortcuts_created']} (symlinks unsupported)")

    if not album_stats.get("symlinks_supported", True):
        lines.extend([
            "",
            "  WARNING: Symlinks not available on this system.",
            "  Album folders contain .shortcut text files instead.",
            "  Enable Developer Mode in Windows Settings > Privacy & Security",
            "  to allow symlink creation without admin rights.",
        ])

    lines.extend(["", "=" * 60])

    report_text = "\n".join(lines)

    if not dry_run:
        report_path = output_dir / "report.txt"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_text)

    return report_text

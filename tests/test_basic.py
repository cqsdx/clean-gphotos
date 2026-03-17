#!/usr/bin/env python3
"""Basic integration test with a simulated mini Takeout export."""

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.scanner import scan_directory, find_json_sidecar, is_chrono_dir
from lib.metadata import read_json_metadata, resolve_date, timestamp_to_ymd
from lib.dedup import deduplicate, hash_file
from lib.organizer import organize_files
from lib.albums import create_albums
from lib.report import generate_report


def create_fake_jpeg(path: Path, content: bytes = b"fake-jpeg-data"):
    """Create a minimal fake image file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def create_json_sidecar(media_path: Path, timestamp: int, title: str = ""):
    """Create a Google Takeout JSON sidecar."""
    data = {
        "title": title or media_path.name,
        "photoTakenTime": {"timestamp": str(timestamp)},
        "geoData": {"latitude": 48.8566, "longitude": 2.3522, "altitude": 0},
        "description": "",
    }
    json_path = media_path.parent / f"{media_path.name}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return json_path


def build_mini_takeout(base: Path):
    """Create a mini Takeout structure:
    - Photos de 2024/ with 3 photos
    - Vacances/ album with 2 of the same photos (duplicates)
    - 1 unique photo only in the album
    """
    chrono = base / "Photos de 2024"
    album = base / "Vacances"

    # Photo A - exists in both chrono and album (duplicate)
    create_fake_jpeg(chrono / "IMG_001.jpg", b"photo-A-content")
    create_json_sidecar(chrono / "IMG_001.jpg", 1704067200)  # 2024-01-01
    create_fake_jpeg(album / "IMG_001.jpg", b"photo-A-content")
    create_json_sidecar(album / "IMG_001.jpg", 1704067200)

    # Photo B - exists in both (duplicate)
    create_fake_jpeg(chrono / "IMG_002.jpg", b"photo-B-content")
    create_json_sidecar(chrono / "IMG_002.jpg", 1711929600)  # 2024-04-01
    create_fake_jpeg(album / "IMG_002.jpg", b"photo-B-content")
    create_json_sidecar(album / "IMG_002.jpg", 1711929600)

    # Photo C - only in chrono (unique)
    create_fake_jpeg(chrono / "IMG_003.jpg", b"photo-C-content")
    create_json_sidecar(chrono / "IMG_003.jpg", 1719792000)  # 2024-07-01

    # Photo D - only in album (unique)
    create_fake_jpeg(album / "IMG_004.jpg", b"photo-D-content")
    create_json_sidecar(album / "IMG_004.jpg", 1727740800)  # 2024-10-01


def test_chrono_dir_detection():
    assert is_chrono_dir("Photos de 2024")
    assert is_chrono_dir("Photos de 2011")
    assert is_chrono_dir("Photos from 2024")
    assert not is_chrono_dir("Vacances")
    assert not is_chrono_dir("Photos")
    assert not is_chrono_dir("")
    print("  PASS: chrono dir detection")


def test_json_sidecar_matching():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        media = tmp / "IMG_001.jpg"
        media.write_bytes(b"x")
        json_path = tmp / "IMG_001.jpg.json"
        json_path.write_text("{}")
        assert find_json_sidecar(media) == json_path

        # Test (1) variant
        media2 = tmp / "IMG_002(1).jpg"
        media2.write_bytes(b"x")
        json2 = tmp / "IMG_002.jpg.json"
        json2.write_text("{}")
        result = find_json_sidecar(media2)
        assert result == json2, f"Expected {json2}, got {result}"

    print("  PASS: JSON sidecar matching")


def test_json_metadata():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        media = tmp / "test.jpg"
        media.write_bytes(b"x")
        json_path = create_json_sidecar(media, 1704067200, "test.jpg")

        meta = read_json_metadata(json_path)
        assert meta["timestamp"] == 1704067200
        assert meta["geo"]["lat"] == 48.8566
        assert meta["title"] == "test.jpg"

    print("  PASS: JSON metadata reading")


def test_timestamp_to_ymd():
    y, m = timestamp_to_ymd(1704067200)  # 2024-01-01 UTC
    assert y == "2024"
    assert m == "01"
    print("  PASS: timestamp to YYYY/MM")


def test_full_pipeline():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        input_dir = tmp / "takeout"
        output_dir = tmp / "output"
        input_dir.mkdir()

        build_mini_takeout(input_dir)

        # Scan
        entries = scan_directory(input_dir)
        assert len(entries) == 6, f"Expected 6 entries, got {len(entries)}"

        # Dedup
        unique, dups = deduplicate(entries)
        assert len(unique) == 4, f"Expected 4 unique, got {len(unique)}"
        assert len(dups) == 2, f"Expected 2 duplicates, got {len(dups)}"

        # Organize
        file_map, stats = organize_files(unique, output_dir, fix_exif=False)
        assert stats["copied"] == 4
        assert (output_dir / "ALL_PHOTOS" / "2024" / "01").exists()
        assert (output_dir / "ALL_PHOTOS" / "2024" / "04").exists()
        assert (output_dir / "ALL_PHOTOS" / "2024" / "07").exists()
        assert (output_dir / "ALL_PHOTOS" / "2024" / "10").exists()

        # Albums
        album_stats = create_albums(unique, file_map, output_dir)
        assert album_stats["albums_created"] >= 1
        vacances_dir = output_dir / "ALBUMS" / "Vacances"
        assert vacances_dir.exists(), "Vacances album should exist"

        # Report
        report = generate_report(
            total_scanned=6,
            unique_count=4,
            duplicate_count=2,
            organize_stats=stats,
            album_stats=album_stats,
            duplicates=dups,
            output_dir=output_dir,
        )
        assert "Unique:          4" in report

    print("  PASS: full pipeline")


def test_resume_idempotent():
    """Running twice should not duplicate files."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        input_dir = tmp / "takeout"
        output_dir = tmp / "output"
        input_dir.mkdir()

        build_mini_takeout(input_dir)

        entries = scan_directory(input_dir)
        unique, _ = deduplicate(entries)
        organize_files(unique, output_dir, fix_exif=False)

        # Run again
        entries2 = scan_directory(input_dir)
        unique2, _ = deduplicate(entries2)
        _, stats2 = organize_files(unique2, output_dir, fix_exif=False)

        assert stats2["skipped"] == 4, f"Expected 4 skipped on re-run, got {stats2['skipped']}"
        assert stats2["copied"] == 0

    print("  PASS: idempotent re-run")


if __name__ == "__main__":
    print("Running tests...")
    test_chrono_dir_detection()
    test_json_sidecar_matching()
    test_json_metadata()
    test_timestamp_to_ymd()
    test_full_pipeline()
    test_resume_idempotent()
    print("\nAll tests passed!")

"""Read metadata from Google Takeout JSON sidecars and EXIF data."""

import json
import os
import struct
from datetime import datetime, timezone
from pathlib import Path


def read_json_metadata(json_path: Path | None) -> dict:
    """Read Google Takeout JSON sidecar and extract useful metadata.

    Returns dict with keys: 'timestamp', 'geo', 'description', 'title'
    """
    result = {"timestamp": None, "geo": None, "description": None, "title": None}
    if json_path is None or not json_path.exists():
        return result

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return result

    # Timestamp
    taken_time = data.get("photoTakenTime", {})
    ts = taken_time.get("timestamp")
    if ts:
        try:
            result["timestamp"] = int(ts)
        except (ValueError, TypeError):
            pass

    # Geo
    geo = data.get("geoData", {})
    lat = geo.get("latitude", 0)
    lng = geo.get("longitude", 0)
    if lat != 0 or lng != 0:
        result["geo"] = {"lat": lat, "lng": lng, "alt": geo.get("altitude", 0)}

    # Description
    desc = data.get("description", "")
    if desc:
        result["description"] = desc

    # Title (useful for truncated filenames)
    title = data.get("title", "")
    if title:
        result["title"] = title

    return result


def read_exif_date(media_path: Path) -> int | None:
    """Try to read DateTimeOriginal from EXIF data. Returns epoch timestamp or None."""
    if media_path.suffix.lower() not in (".jpg", ".jpeg", ".tif", ".tiff"):
        return None

    try:
        import piexif
        exif_dict = piexif.load(str(media_path))
        # Try DateTimeOriginal first, then DateTimeDigitized
        for tag in (piexif.ExifIFD.DateTimeOriginal, piexif.ExifIFD.DateTimeDigitized):
            val = exif_dict.get("Exif", {}).get(tag)
            if val:
                if isinstance(val, bytes):
                    val = val.decode("utf-8", errors="ignore")
                dt = datetime.strptime(val, "%Y:%m:%d %H:%M:%S")
                return int(dt.replace(tzinfo=timezone.utc).timestamp())
    except Exception:
        pass

    return None


def get_file_mtime(media_path: Path) -> int:
    """Get file modification time as epoch timestamp."""
    try:
        return int(os.path.getmtime(media_path))
    except OSError:
        return int(datetime.now(timezone.utc).timestamp())


def resolve_date(json_meta: dict, media_path: Path) -> tuple[int, str]:
    """Determine the best date for a media file.

    Priority: JSON timestamp > EXIF DateTimeOriginal > file mtime > now

    Returns (epoch_timestamp, source_string)
    """
    # 1. JSON timestamp (most reliable for Takeout)
    if json_meta.get("timestamp"):
        return json_meta["timestamp"], "json"

    # 2. EXIF date
    exif_ts = read_exif_date(media_path)
    if exif_ts and exif_ts > 0:
        return exif_ts, "exif"

    # 3. File modification time
    mtime = get_file_mtime(media_path)
    if mtime > 0:
        return mtime, "mtime"

    # 4. Fallback to now
    return int(datetime.now(timezone.utc).timestamp()), "fallback"


def timestamp_to_ymd(ts: int) -> tuple[str, str]:
    """Convert epoch timestamp to (YYYY, MM) strings."""
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return f"{dt.year:04d}", f"{dt.month:02d}"


def write_exif_date(media_path: Path, timestamp: int) -> bool:
    """Write date into EXIF DateTimeOriginal and CreateDate.

    Only works for JPEG files via piexif. For other formats, falls back to os.utime().
    Returns True if EXIF was written, False if only utime was set.
    """
    dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    date_str = dt.strftime("%Y:%m:%d %H:%M:%S")

    if media_path.suffix.lower() in (".jpg", ".jpeg"):
        try:
            import piexif

            try:
                exif_dict = piexif.load(str(media_path))
            except Exception:
                exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}}

            if "Exif" not in exif_dict:
                exif_dict["Exif"] = {}

            exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = date_str.encode("utf-8")
            exif_dict["Exif"][piexif.ExifIFD.DateTimeDigitized] = date_str.encode("utf-8")

            # Also set 0th IFD DateTime
            if "0th" not in exif_dict:
                exif_dict["0th"] = {}
            exif_dict["0th"][piexif.ImageIFD.DateTime] = date_str.encode("utf-8")

            # Remove thumbnail to avoid size issues
            exif_dict.pop("thumbnail", None)
            if "1st" in exif_dict:
                exif_dict["1st"] = {}

            exif_bytes = piexif.dump(exif_dict)
            piexif.insert(exif_bytes, str(media_path))
            return True
        except Exception:
            pass

    # Fallback: set file modification time
    try:
        os.utime(media_path, (timestamp, timestamp))
    except OSError:
        pass
    return False

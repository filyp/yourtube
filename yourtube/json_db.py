import json
from pathlib import Path
import time

VIDEOS_DIR = Path.home() / ".yourtube/videos"
PLAYLISTS_DIR = Path.home() / ".yourtube/playlists"


def read_video(video_id):
    path = VIDEOS_DIR / f"{video_id}.json"
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def all_video_ids():
    return (path.stem for path in VIDEOS_DIR.glob("*.json"))


def update_video(video_id, recommendations, is_down=False):
    data = {
        "recommendations": recommendations,
        "time_scraped": time.time(),
        "is_down": is_down,
    }
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    path = VIDEOS_DIR / f"{video_id}.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def _read_playlist(playlist_name):
    """Read and return a playlist JSON by name."""
    path = PLAYLISTS_DIR / f"{playlist_name}.json"
    with open(path) as f:
        return json.load(f)


def _extract_video_ids(playlist, range_start=0.0, range_end=1.0):
    """Extract video IDs from a playlist dict, optionally slicing by range.

    Args:
        playlist: Playlist dict with 'entries' key
        range_start: Start of range as fraction (0.0 to 1.0)
        range_end: End of range as fraction (0.0 to 1.0)
    """
    entries = [e for e in playlist.get("entries", []) if e and e.get("id")]
    n = len(entries)
    start_idx = int(n * range_start)
    end_idx = int(n * range_end)
    return {e["id"] for e in entries[start_idx:end_idx]}


def get_playlist_video_ids():
    """Read all playlist JSONs and return the set of video IDs."""
    if not PLAYLISTS_DIR.is_dir():
        return set()

    video_ids = set()
    for name in get_playlist_names():
        video_ids |= _extract_video_ids(_read_playlist(name))
    return video_ids


def get_playlist_entries():
    """Returns list of (playlist_name, video_id, entry_data) tuples from all playlist JSONs."""
    if not PLAYLISTS_DIR.is_dir():
        return []

    results = []
    for name in get_playlist_names():
        playlist = _read_playlist(name)
        for entry in playlist.get("entries", []):
            if entry and entry.get("id"):
                results.append((name, entry["id"], entry))
    return results


def get_playlist_names():
    """Returns sorted list of playlist names (alphabetically)."""
    if not PLAYLISTS_DIR.is_dir():
        return []
    return sorted(path.stem for path in PLAYLISTS_DIR.glob("*.json"))


def get_playlist_video_ids_by_name(playlist_name, range_start=0.0, range_end=1.0):
    """Returns set of video IDs from a specific playlist.

    Args:
        playlist_name: Name of the playlist
        range_start: Start of range as fraction (0.0 to 1.0)
        range_end: End of range as fraction (0.0 to 1.0)
    """
    return _extract_video_ids(_read_playlist(playlist_name), range_start, range_end)

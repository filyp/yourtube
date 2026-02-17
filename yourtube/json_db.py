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


def get_playlist_video_ids():
    """Read all playlist JSONs and return the set of video IDs."""
    if not PLAYLISTS_DIR.is_dir():
        return set()

    video_ids = set()
    for path in PLAYLISTS_DIR.glob("*.json"):
        with open(path) as f:
            playlist = json.load(f)
        for entry in playlist.get("entries", []):
            if entry and entry.get("id"):
                video_ids.add(entry["id"])
    return video_ids


def get_playlist_entries():
    """Returns list of (playlist_name, video_id, entry_data) tuples from all playlist JSONs."""
    if not PLAYLISTS_DIR.is_dir():
        return []

    results = []
    for path in PLAYLISTS_DIR.glob("*.json"):
        playlist_name = path.stem
        with open(path) as f:
            playlist = json.load(f)
        for entry in playlist.get("entries", []):
            if entry and entry.get("id"):
                results.append((playlist_name, entry["id"], entry))

    return results

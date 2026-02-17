import json
import os
from pathlib import Path

VIDEOS_DIR = os.path.expanduser("~/.yourtube/videos")
PLAYLISTS_DIR = os.path.expanduser("~/.yourtube/playlists")


def _read_video(video_id):
    path = os.path.join(VIDEOS_DIR, f"{video_id}.json")
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def update_video(video_id, recommendations, time_scraped, is_down=False):
    data = {
        "recommendations": recommendations,
        "time_scraped": time_scraped,
        "is_down": is_down,
    }
    Path(VIDEOS_DIR).mkdir(parents=True, exist_ok=True)
    path = os.path.join(VIDEOS_DIR, f"{video_id}.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def check_if_this_video_was_scraped(video_id):
    data = _read_video(video_id)
    if data is None:
        return []
    return [(data.get("time_scraped"), data.get("is_down", False))]


def get_playlist_video_ids():
    """Read all playlist JSONs and return the set of video IDs."""
    if not os.path.isdir(PLAYLISTS_DIR):
        return set()

    video_ids = set()
    for filename in os.listdir(PLAYLISTS_DIR):
        if not filename.endswith(".json"):
            continue
        with open(os.path.join(PLAYLISTS_DIR, filename)) as f:
            playlist = json.load(f)
        for entry in playlist.get("entries", []):
            if entry and entry.get("id"):
                video_ids.add(entry["id"])
    return video_ids


def get_video_recommendations():
    """Load all playlist videos and their recommendations.
    Returns list of (v1_id, v1_is_down, v2_id, v2_is_down) tuples.
    """
    video_ids = get_playlist_video_ids()

    results = []
    for v1_id in video_ids:
        v1 = _read_video(v1_id)
        if v1 is None:
            continue
        for v2_id in v1.get("recommendations", []):
            v2 = _read_video(v2_id)
            results.append((
                v1_id, v1.get("is_down"),
                v2_id, v2.get("is_down") if v2 else None,
            ))

    return results


def get_playlist_entries():
    """Returns list of (playlist_name, video_id, entry_data) tuples from all playlist JSONs."""
    if not os.path.isdir(PLAYLISTS_DIR):
        return []

    results = []
    for filename in os.listdir(PLAYLISTS_DIR):
        if not filename.endswith(".json"):
            continue
        playlist_name = filename[:-5]  # strip .json
        with open(os.path.join(PLAYLISTS_DIR, filename)) as f:
            playlist = json.load(f)
        for entry in playlist.get("entries", []):
            if entry and entry.get("id"):
                results.append((playlist_name, entry["id"], entry))

    return results


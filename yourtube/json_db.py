import json
import os

from yourtube.config import Config


VIDEOS_DIR = os.path.join(Config.json_db_path, "videos")
PLAYLISTS_DIR = os.path.join(Config.json_db_path, "playlists")


def _read_video(video_id):
    path = os.path.join(VIDEOS_DIR, f"{video_id}.json")
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def _write_video(video_id, data):
    path = os.path.join(VIDEOS_DIR, f"{video_id}.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def update_video(recs, **video_info):
    video_id = video_info["video_id"]
    data = video_info.copy()
    data["is_down"] = False
    data["recommendations"] = recs
    _write_video(video_id, data)

    # ensure stub files exist for recommended videos
    for rec_id in recs:
        rec_path = os.path.join(VIDEOS_DIR, f"{rec_id}.json")
        if not os.path.exists(rec_path):
            _write_video(rec_id, {"video_id": rec_id, "recommendations": []})


def mark_video_as_down(video_id):
    data = _read_video(video_id) or {"video_id": video_id, "recommendations": []}
    data["is_down"] = True
    _write_video(video_id, data)


def check_if_this_video_was_scraped(video_id):
    data = _read_video(video_id)
    if data is None:
        return []
    return [(data.get("time_scraped"), data.get("is_down", False))]


def ensure_playlist_exists(username, playlist_name):
    user_dir = os.path.join(PLAYLISTS_DIR, username)
    os.makedirs(user_dir, exist_ok=True)
    path = os.path.join(user_dir, f"{playlist_name}.json")
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump([], f)


def add_info_that_video_is_in_playlist(username, playlist_name, video_id, time_added):
    path = os.path.join(PLAYLISTS_DIR, username, f"{playlist_name}.json")
    try:
        with open(path) as f:
            entries = json.load(f)
    except FileNotFoundError:
        entries = []

    # avoid duplicates
    for entry in entries:
        if entry["video_id"] == video_id:
            entry["time_added"] = time_added
            break
    else:
        entries.append({"video_id": video_id, "time_added": time_added})

    with open(path, "w") as f:
        json.dump(entries, f, indent=2)


def get_limited_user_relevant_video_info(username):
    """Load all playlist videos and their recommendations.
    Returns list of 12-tuples matching the old Neo4j query format:
    (v1_id, v1_title, v1_view_count, v1_like_count, v1_time_scraped, v1_is_down,
     v2_id, v2_title, v2_view_count, v2_like_count, v2_time_scraped, v2_is_down)
    """
    user_playlists_dir = os.path.join(PLAYLISTS_DIR, username)
    if not os.path.isdir(user_playlists_dir):
        return []

    # collect all video IDs from all playlists
    playlist_video_ids = set()
    for filename in os.listdir(user_playlists_dir):
        if not filename.endswith(".json"):
            continue
        with open(os.path.join(user_playlists_dir, filename)) as f:
            entries = json.load(f)
        for entry in entries:
            playlist_video_ids.add(entry["video_id"])

    # for each playlist video, load it and its recommendations
    results = []
    for v1_id in playlist_video_ids:
        v1 = _read_video(v1_id)
        if v1 is None:
            continue
        for v2_id in v1.get("recommendations", []):
            v2 = _read_video(v2_id)
            if v2 is None:
                continue
            results.append((
                v1_id, v1.get("title"), v1.get("view_count"), v1.get("like_count"),
                v1.get("time_scraped"), v1.get("is_down"),
                v2_id, v2.get("title"), v2.get("view_count"), v2.get("like_count"),
                v2.get("time_scraped"), v2.get("is_down"),
            ))

    return results


def get_all_user_relevant_playlist_info(username):
    """Returns list of (playlist_name, video_id, time_added) tuples."""
    user_playlists_dir = os.path.join(PLAYLISTS_DIR, username)
    if not os.path.isdir(user_playlists_dir):
        return []

    results = []
    for filename in os.listdir(user_playlists_dir):
        if not filename.endswith(".json"):
            continue
        playlist_name = filename[:-5]  # strip .json
        with open(os.path.join(user_playlists_dir, filename)) as f:
            entries = json.load(f)
        for entry in entries:
            results.append((playlist_name, entry["video_id"], entry["time_added"]))

    return results


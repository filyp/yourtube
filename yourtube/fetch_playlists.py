import json
import os
from pathlib import Path

import yt_dlp

browsers = ["brave", "chrome", "chromium", "edge", "firefox", "opera", "safari", "vivaldi", "whale"]  # fmt: skip
LIKED_PLAYLIST_URL = "https://www.youtube.com/playlist?list=LL"
TO_WATCH_PLAYLIST_URL = "https://www.youtube.com/playlist?list=WL"

PLAYLISTS_DIR = os.path.expanduser("~/.yourtube/playlists")


def get_playlist_info(playlist_url):
    for browser in browsers:
        try:
            ydl_opts = {
                "cookiesfrombrowser": (browser,),
                "extract_flat": "in_playlist",
                "quiet": True,
                "no_warnings": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(playlist_url, download=False)
        except yt_dlp.DownloadError:
            pass
    raise Exception("Could not fetch playlist info with any browser")


def save_playlist_info(info):
    Path(PLAYLISTS_DIR).mkdir(parents=True, exist_ok=True)
    filename = f"{info['channel_id']}__{info['id']}.json"
    path = os.path.join(PLAYLISTS_DIR, filename)
    with open(path, "w") as f:
        json.dump(info, f, indent=2)
    print(f"Saved {path}")


def main():
    for url in [LIKED_PLAYLIST_URL, TO_WATCH_PLAYLIST_URL]:
        print(f"Fetching {url} ...")
        info = get_playlist_info(url)
        save_playlist_info(info)


if __name__ == "__main__":
    main()

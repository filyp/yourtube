import json
import re
import pickle
import csv
from time import time
import os.path
import datetime
import requests


id_to_url = "https://www.youtube.com/watch?v={}"


def get_freetube_favorites_ids():
    with open("/home/filip/.config/FreeTube/playlists.db") as db:
        lines = db.readlines()
    playlist = json.loads(lines[-1])
    videos = playlist["videos"]
    video_ids = [video["videoId"] for video in videos]
    return video_ids


def get_exported_youtube_playlist_ids(filename):
    def timestamp_to_seconds(timestamp):
        epoch = datetime.datetime.utcfromtimestamp(0)
        utc = datetime.datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S UTC")
        return (utc - epoch).total_seconds()

    with open(filename) as file:
        reader = csv.reader(file, delimiter=",")
        data_read = [row for row in reader]

    data_read = data_read[5:]  # strip metadata
    ids, timestamps = zip(*data_read)
    # strip whitespaces
    video_ids = [id_.strip() for id_ in ids]
    times_liked = [timestamp_to_seconds(timestamp) for timestamp in timestamps]
    return video_ids, times_liked


def get_content(id_):
    url = id_to_url.format(id_)
    content = requests.get(url, cookies={"CONSENT": "YES+1"})
    return content


def get_recommended_ids(content, id_):
    all_urls = re.findall(r"watch\?v=(.{11})", content.text)
    recs = list(set(all_urls))
    if id_ in recs:
        recs.remove(id_)
    return recs


def get_title(content):
    candidates = re.findall(r"title=\"(.*?)\"><link rel=", content.text)
    candidates = set(candidates)
    if "YouTube" in candidates:
        candidates.remove("YouTube")
    candidates = list(candidates)
    title = candidates[0] if candidates else None
    return title


def scrape(id_, G, skip_if_fresher_than=None):
    content = get_content(id_)
    recs = get_recommended_ids(content, id_)
    if not recs:
        return
    for rec in recs:
        G.add_edge(id_, rec)
    G.nodes[id_]["title"] = get_title(content)
    G.nodes[id_]["time_scraped"] = time()
    # TODO scrape thumbnails:    "thumbnail":{"thumbnails":[{"url":"https://i.ytimg.com


# def get_liked_time_sorted_sources(G):
#     sources = [
#         (G.nodes[node]["time_liked"], node)
#         for node in G.nodes
#         if "time_liked" in G.nodes[node]
#     ]
#     sources = sorted(sources)
#     sources = [node for timestamp, node in sources]
#     return sources

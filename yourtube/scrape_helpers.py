import os
import re
import json
import csv
import datetime
import requests
from time import time
from tqdm import tqdm

from common import id_to_url


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

    data_read = data_read[4:-1]  # strip metadata
    if data_read:
        ids, timestamps = zip(*data_read)
    else:
        ids = []
        timestamps = []
    # strip whitespaces
    video_ids = [id_.strip() for id_ in ids]
    times_added = [timestamp_to_seconds(timestamp) for timestamp in timestamps]
    return video_ids, times_added


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


def scrape_from_list(ids_to_add, G, skip_if_fresher_than=None):
    """
    Scrapes videos from the ids_to_add list and adds them to graph G

    skip_if_fresher_than is in seconds
    if set, videos scraped earlier than this time will be skipped
    """
    print(f"adding {len(ids_to_add)} nodes")

    skipped = 0
    for id_ in tqdm(ids_to_add, ncols=80):
        # check if this video was already scraped recently
        if (
            skip_if_fresher_than is not None
            and id_ in G.nodes
            and "time_scraped" in G.nodes[id_]
            and time() - G.nodes[id_]["time_scraped"] < skip_if_fresher_than
        ):
            skipped += 1
            continue

        # TODO maybe omit videos where title is None
        # they are down but are tried do to be scraped every time
        scrape(id_, G)

    print(f"skipped {skipped} videos")

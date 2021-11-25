import csv
import json
import logging
import os
import pickle
import re
from time import mktime, time

import networkx as nx
import pickledb
from dateutil import parser

from yourtube.neo4j_queries import (
    get_all_user_relevant_playlist_info,
    get_limited_user_relevant_video_info,
)

logger = logging.getLogger("yourtube")
logger.setLevel(logging.DEBUG)

id_to_url = "https://www.youtube.com/watch?v={}"

home = os.path.expanduser("~")
graph_path_template = os.path.join(home, ".yourtube", "graph_cache", "{}.pickle")
clustering_cache_template = os.path.join(home, ".yourtube", "clustering_cache", "{}.pickle")
transcripts_path = os.path.join(home, ".yourtube", "transcripts.json")
playlists_path = os.path.join(
    home, ".yourtube", "Takeout", "YouTube and YouTube Music", "playlists"
)
history_path = os.path.join(
    home, ".yourtube", "Takeout", "YouTube and YouTube Music", "history", "watch-history.html"
)


def load_graph_from_neo4j(driver, user):
    # see if it's cached
    graph_path = graph_path_template.format(user)
    if os.path.isfile(graph_path):
        time_modified = os.path.getmtime(graph_path)
        seconds_in_a_day = 60 * 60 * 24
        if time() - time_modified < seconds_in_a_day * 3:
            logger.info("using cached graph")
            with open(graph_path, "rb") as handle:
                return pickle.load(handle)

    # loading in this awkward way, loads the graph in 2s instead of 25s
    with driver.session() as s:
        info = s.read_transaction(get_limited_user_relevant_video_info, user)
    G = nx.DiGraph()
    for (
        v1_video_id,
        v1_title,
        v1_view_count,
        v1_like_count,
        v1_time_scraped,
        v1_is_down,
        v1_watched,
        v2_video_id,
        v2_title,
        v2_view_count,
        v2_like_count,
        v2_time_scraped,
        v2_is_down,
        v2_watched,
    ) in info:
        # load the parameters returned by neo4j, and delete None values
        params_dict_v1 = dict(
            title=v1_title,
            view_count=v1_view_count,
            like_count=v1_like_count,
            time_scraped=v1_time_scraped,
            is_down=v1_is_down,
            watched=v1_watched,
        )
        params_dict_v1 = {k: v for k, v in params_dict_v1.items() if v is not None}
        params_dict_v2 = dict(
            title=v2_title,
            view_count=v2_view_count,
            like_count=v2_like_count,
            time_scraped=v2_time_scraped,
            is_down=v2_is_down,
            watched=v2_watched,
        )
        params_dict_v2 = {k: v for k, v in params_dict_v2.items() if v is not None}
        G.add_node(v1_video_id, **params_dict_v1)
        G.add_node(v2_video_id, **params_dict_v2)
        G.add_edge(v1_video_id, v2_video_id)

    with driver.session() as s:
        playlist_info = s.read_transaction(get_all_user_relevant_playlist_info, user)
    for playlist_name, video_id, time_added in playlist_info:
        if video_id not in G.nodes:
            # this means the video had no recommended videos, and wasn't matched by the previous step
            # so it's probably down
            continue
        G.nodes[video_id]["from"] = playlist_name
        G.nodes[video_id]["time_added"] = time_added

    # cache graph
    with open(graph_path, "wb") as handle:
        pickle.dump(G, handle, protocol=pickle.HIGHEST_PROTOCOL)

    return G


def get_transcripts_db():
    return pickledb.load(transcripts_path, auto_dump=False)


def get_playlist_names():
    for filename in os.listdir(playlists_path):
        match = re.match(r"(.*)\.csv", filename)
        if match is not None:
            yield match[1]
        else:
            # it looks that playlists with a dot in their filename don't have '.csv' at the end
            abs_filename = os.path.join(playlists_path, filename)
            os.rename(abs_filename, abs_filename + ".csv")
            yield filename


def get_freetube_favorites_ids():
    with open("/home/filip/.config/FreeTube/playlists.db") as db:
        lines = db.readlines()
    playlist = json.loads(lines[-1])
    videos = playlist["videos"]
    video_ids = [video["videoId"] for video in videos]
    return video_ids


def timestamp_to_seconds(timestamp):
    timelocal = parser.parse(timestamp)
    unixtime = mktime(timelocal.utctimetuple())
    # warning: mktime may be inaccurate up to a few hours because of timezones
    # https://stackoverflow.com/a/7852891/11756613
    # but here, few hours aren't a problem
    return unixtime


def get_youtube_playlist_ids(playlist_name):
    filename = os.path.join(playlists_path, f"{playlist_name}.csv")
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


def get_youtube_watched_ids():
    """Returns a dictionary, where keys are video ids,
    and each value is a list of times when this video has been watched (in unix time).

    Unwatched videos aren't in this dictionary.
    """
    with open(history_path, encoding="utf-8") as file:
        lines = file.readlines()
    text = " ".join(lines)

    watched = re.findall(
        r"Watched.*?https://www.youtube.com\/watch\?v=(.{11}).*?<br>((Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) .*?)</div>",
        text,
    )

    ids, timestamps, _ = zip(*watched)
    unixtimes = [timestamp_to_seconds(timestamp) for timestamp in timestamps]

    id_set = set(ids)

    id_to_watched_times = dict()
    for id_ in id_set:
        id_to_watched_times[id_] = []
    for id_, watched_time in zip(ids, unixtimes):
        id_to_watched_times[id_].append(watched_time)

    return id_to_watched_times

import os
import re
import csv
import json
import pickle
import datetime
import networkx as nx
from time import time, mktime
from dateutil import parser

id_to_url = "https://www.youtube.com/watch?v={}"

home = os.path.expanduser("~")
graph_path_template = os.path.join(home, ".yourtube", "{}.pickle")
playlists_path = os.path.join(
    home, ".yourtube/Takeout/YouTube and YouTube Music/playlists"
)
history_path = os.path.join(
    home, ".yourtube/Takeout/YouTube and YouTube Music/history/watch-history.html"
)


"""
graph format:
    id:
        node identifier
        11 characters that identify video on youtube (can be found in URL)
    title:
        video title
        can be absent if the video hasn't been scraped yet
        can be None if the video has been removed from youtube
    time_scraped:
        time when the video has been scraped
        in unix time
    time_added:
        time when the video has been added to a playlist
        in unix time
        "Watched videos" isn't treated as a playlist
        "Liked videos" is
    from:
        playlist name that the video is from
    watched_time:
        time when the video has been watched
        in unix time
        it is absent if the video hasn't been watched

    clusters:
        ...

    TODO: handle situations where video is in multiple playlists?
"""


def save_graph(G, graph_name="graph"):
    graph_path = graph_path_template.format(graph_name)
    assert 0 == len(list(nx.selfloop_edges(G)))
    # selfloop edges shouldn't happen
    # G.remove_edges_from(nx.selfloop_edges(G))

    with open(graph_path, "wb") as handle:
        pickle.dump(G, handle, protocol=pickle.HIGHEST_PROTOCOL)
    # print("graph saved")


def load_graph(graph_name="graph"):
    graph_path = graph_path_template.format(graph_name)
    # load or create a Graph
    if os.path.isfile(graph_path):
        print("graph loaded")
        with open(graph_path, "rb") as handle:
            return pickle.load(handle)
    else:
        print("graph created")
        return nx.DiGraph()


def get_playlist_names():
    for filename in os.listdir(playlists_path):
        yield re.match(r"(.*)\.csv", filename)[1]


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
    with open(history_path) as file:
        lines = file.readlines()
    text = " ".join(lines)

    watched = re.findall(
        r"Watched.*?https://www.youtube.com\/watch\?v=(.{11}).*?<br>((Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) .*?)</div>",
        text,
    )

    ids, timestamps, _ = zip(*watched)
    unixtimes = [timestamp_to_seconds(timestamp) for timestamp in timestamps]
    return ids, unixtimes

import os
import re
import csv
import json
import pickle
import datetime
import pickledb
import networkx as nx
from time import time, mktime
from dateutil import parser

id_to_url = "https://www.youtube.com/watch?v={}"

home = os.path.expanduser("~")
graph_path_template = os.path.join(home, ".yourtube", "{}.pickle")
transcripts_path = os.path.join(home, ".yourtube", "transcripts.json")
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
        all the other fields can be absent if the video hasn't been scraped yet
    title:
        video title
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
    watched_times:
        list of times when the video has been watched, in unix time
        it is absent if the video hasn't been watched
    view_count:
        number of views on youtube
        can be None if the video is premium (so the views are ambiguous)
    like_count:
        number of likes on youtube
        can be None if likes are disabled
    channel_id:
        id of the channel of this video
        can be None if the video is unavailable
    category:
        category of the video
    length:
        video length in seconds
        can be None if the video is premium (so the views are ambiguous)
    keywords:
        keywords of the video as a list of strings
        can be an empty list if there are no keywords
    is_down:
        True if the video is unavailable
        can be absent if the video is up or hasn't been scraped


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

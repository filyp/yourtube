import csv
import json
import logging
import os
import pickle
import re
import zipfile
import glob
from time import mktime, time
from pathlib import Path

import networkx as nx
import pickledb
from dateutil import parser

from yourtube.neo4j_queries import (
    get_all_user_relevant_playlist_info,
    get_limited_user_relevant_video_info,
)
from yourtube.config import Config

logger = logging.getLogger("yourtube")
logger.setLevel(logging.DEBUG)

id_to_url = "https://www.youtube.com/watch?v={}"

data_path = os.path.join(os.sep, "yourtube", "data")
graph_path_template = os.path.join(data_path, "graph_cache", "{}.pickle")
clustering_cache_template = os.path.join(data_path, "clustering_cache", "{}.pickle")
saved_clusters_template = os.path.join(data_path, "saved_clusters", "{}", "{}")
transcripts_path = os.path.join(data_path, "transcripts.json")

takeouts_template = os.path.join(data_path, "takeouts", "{}")
playlists_path_template = os.path.join(
    takeouts_template, "Takeout", "YouTube and YouTube Music", "playlists"
)
history_path_template = os.path.join(
    takeouts_template, "Takeout", "YouTube and YouTube Music", "history", "watch-history.html"
)


def load_graph_from_neo4j(driver, user):
    # see if it's cached
    graph_path = graph_path_template.format(user)
    if os.path.isfile(graph_path):
        time_modified = os.path.getmtime(graph_path)
        if time() - time_modified < Config.graph_cache_time:
            logger.info("using cached graph")
            with open(graph_path, "rb") as handle:
                return pickle.load(handle)

    # load info about which videos have been watched
    id_to_watched_times = get_youtube_watched_ids(user)

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
        v2_video_id,
        v2_title,
        v2_view_count,
        v2_like_count,
        v2_time_scraped,
        v2_is_down,
    ) in info:
        # load the parameters returned by neo4j, and delete None values
        params_dict_v1 = dict(
            title=v1_title,
            view_count=v1_view_count,
            like_count=v1_like_count,
            time_scraped=v1_time_scraped,
            is_down=v1_is_down,
        )
        params_dict_v1 = {k: v for k, v in params_dict_v1.items() if v is not None}
        params_dict_v2 = dict(
            title=v2_title,
            view_count=v2_view_count,
            like_count=v2_like_count,
            time_scraped=v2_time_scraped,
            is_down=v2_is_down,
        )
        params_dict_v2 = {k: v for k, v in params_dict_v2.items() if v is not None}

        # check if they were watched
        params_dict_v1["watched"] = v1_video_id in id_to_watched_times
        params_dict_v2["watched"] = v2_video_id in id_to_watched_times

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

    # cache graph, but only if it's not emply
    if len(G.nodes) > 0:
        with open(graph_path, "wb") as handle:
            pickle.dump(G, handle, protocol=pickle.HIGHEST_PROTOCOL)

    return G


def load_joined_graph_of_many_users(driver, users):
    # load graphs of each user
    graphs = []
    for user in users:
        G = load_graph_from_neo4j(driver, user=user)
        graphs.append(G)

    # join them
    joined_graph = graphs[0]
    for G in graphs[1:]:
        # joined_graph.add_nodes_from(G.nodes(data=True))
        # joined_graph.add_edges_from(G.edges())
        if len(G.nodes) == 0:
            logger.error(f"user: {user}, tried to load an empty graph in multi-user mode")
        joined_graph.update(G)

    return joined_graph


def get_transcripts_db():
    return pickledb.load(transcripts_path, auto_dump=False)


def get_playlist_names(username):
    playlist_path = playlists_path_template.format(username)
    for filename in os.listdir(playlist_path):
        match = re.match(r"(.*)\.csv", filename)
        if match is not None:
            yield match[1]
        else:
            # it looks that playlists with a dot in their filename don't have '.csv' at the end
            abs_filename = os.path.join(playlist_path, filename)
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


def get_youtube_playlist_ids(playlist_name, username):
    playlists_path = playlists_path_template.format(username)
    filename = os.path.join(playlists_path, f"{playlist_name}.csv")
    with open(filename) as file:
        reader = csv.reader(file, delimiter=",")
        data_read = [row for row in reader]

    # strip metadata
    data_read = [row for row in data_read if len(row) == 2 and len(row[0]) == 11]
    if data_read:
        ids, timestamps = zip(*data_read)
    else:
        ids = []
        timestamps = []
    # strip whitespaces
    video_ids = [id_.strip() for id_ in ids]
    times_added = [timestamp_to_seconds(timestamp) for timestamp in timestamps]
    return video_ids, times_added


def get_youtube_watched_ids(username):
    """Returns a dictionary, where keys are video ids,
    and each value is a list of times when this video has been watched (in unix time).

    Unwatched videos aren't in this dictionary.
    """
    history_path = history_path_template.format(username)
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


def user_takeout_exists(username):
    return os.path.exists(playlists_path_template.format(username))


def get_usernames():
    for abs_path in glob.glob(playlists_path_template.format("*")):
        yield Path(abs_path).parts[-4]


def update_user_takeout(username, takeout_file_input):
    # make sure user's takeout folder exists
    user_takeout_dir = takeouts_template.format(username)
    Path(user_takeout_dir).mkdir(parents=True, exist_ok=True)

    # save takeout file
    takeout_filename = os.path.join(takeouts_template.format(username), "takeout.zip")
    takeout_file_input.save(takeout_filename)

    # unzip takeout file
    with zipfile.ZipFile(takeout_filename, "r") as zip_ref:
        zip_ref.extractall(Path(takeout_filename).parent)

    # verify that the takeout file is valid
    playlist_exist = os.path.exists(playlists_path_template.format(username))
    history_exists = os.path.exists(history_path_template.format(username))
    return playlist_exist and history_exists


def get_saved_clusters(username):
    pattern = saved_clusters_template.format(username, "*")
    cluster_names = []
    for abs_filename in glob.glob(pattern):
        filename = os.path.split(abs_filename)[1]
        cluster_name = filename.split(".")[0]
        cluster_names.append(cluster_name)

    # get public clusters of other users
    # if a cluster name starts with _, it is private, so avoid it
    pattern = saved_clusters_template.format("*", "[!_]*")
    for abs_filename in glob.glob(pattern):
        head, cluster_name = os.path.split(abs_filename)
        current_username = os.path.split(head)[1]
        if current_username == username:
            # this user's cluster were already added previously
            continue

        cluster_name = current_username + "/" + cluster_name
        cluster_names.append(cluster_name)

    return cluster_names

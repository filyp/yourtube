import glob
import logging
import os
from time import time

import networkx as nx

from yourtube.json_db import (
    get_video_recommendations,
    get_playlist_entries,
)

logger = logging.getLogger("yourtube")
logger.setLevel(logging.DEBUG)

data_path = os.path.expanduser("~/.yourtube/data")
clustering_cache_template = os.path.join(data_path, "clustering_cache", "{}.pickle")
saved_clusters_template = os.path.join(data_path, "saved_clusters", "{}", "{}")


def load_graph():
    G = nx.DiGraph()

    # add edges from video recommendations
    for v1_id, v1_is_down, v2_id, v2_is_down in get_video_recommendations():
        if v1_is_down:
            G.add_node(v1_id, is_down=True)
            continue
        G.add_node(v1_id)
        if v2_is_down:
            G.add_node(v2_id, is_down=True)
        else:
            G.add_node(v2_id)
        G.add_edge(v1_id, v2_id)

    # add playlist metadata from yt-dlp playlist entries
    for playlist_name, video_id, entry in get_playlist_entries():
        if video_id not in G.nodes:
            continue
        node = G.nodes[video_id]
        node["from"] = playlist_name
        node["title"] = entry.get("title")
        node["view_count"] = entry.get("view_count")
        node["channel"] = entry.get("channel")
        node["duration"] = entry.get("duration")

    return G


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

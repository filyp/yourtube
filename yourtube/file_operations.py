import logging
from pathlib import Path

import networkx as nx

from yourtube.json_db import (
    get_video_recommendations,
    get_playlist_entries,
)

logger = logging.getLogger("yourtube")
logger.setLevel(logging.DEBUG)

BASE_DIR = Path.home() / ".yourtube"
CLUSTERING_CACHE_DIR = BASE_DIR / "clustering_cache"
SAVED_CLUSTERS_DIR = BASE_DIR / "saved_clusters"


def clustering_cache_path(unique_string):
    return CLUSTERING_CACHE_DIR / f"{unique_string}.pickle"


def saved_cluster_path(username, cluster_name):
    return SAVED_CLUSTERS_DIR / username / cluster_name


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
    cluster_names = []
    for path in (SAVED_CLUSTERS_DIR / username).glob("*"):
        cluster_names.append(path.stem)

    # get public clusters of other users
    # if a cluster name starts with _, it is private, so avoid it
    for path in SAVED_CLUSTERS_DIR.glob("*/[!_]*"):
        if path.parent.name == username:
            # this user's clusters were already added previously
            continue
        cluster_names.append(f"{path.parent.name}/{path.name}")

    return cluster_names

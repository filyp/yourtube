import logging
from pathlib import Path

import networkx as nx

from yourtube.json_db import (
    all_video_ids,
    get_playlist_video_ids,
    get_playlist_entries,
    read_video,
)

logger = logging.getLogger("yourtube")
logger.setLevel(logging.DEBUG)

BASE_DIR = Path.home() / ".yourtube"
SAVED_CLUSTERS_DIR = BASE_DIR / "saved_clusters"


def saved_cluster_path(cluster_name):
    return SAVED_CLUSTERS_DIR / cluster_name


def load_graph():
    G = nx.DiGraph()

    # add edges from video recommendations
    # for v1_id in get_playlist_video_ids():
    for v1_id in all_video_ids():
        v1 = read_video(v1_id)
        if v1 is None or v1["is_down"]:
            continue
        G.add_node(v1_id)

        for v2_id in v1["recommendations"]:
            v2 = read_video(v2_id)
            if v2 is not None and not v2["is_down"]:
                # we already know we should skip it
                continue
            G.add_node(v2_id)
            G.add_edge(v1_id, v2_id)

    print(f"added {len(G.nodes)} nodes and {len(G.edges)} edges")

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


def get_saved_clusters():
    cluster_names = []
    for path in SAVED_CLUSTERS_DIR.glob("*"):
        if path.name.startswith("."):
            continue
        cluster_names.append(path.stem)
    return cluster_names

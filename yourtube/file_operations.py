import glob
import json
import logging
import os
from pathlib import Path

import networkx as nx
import pickledb

from yourtube.json_db import (
    get_all_user_relevant_playlist_info,
    get_limited_user_relevant_video_info,
)

logger = logging.getLogger("yourtube")
logger.setLevel(logging.DEBUG)

id_to_url = "https://www.youtube.com/watch?v={}"

data_path = os.path.expanduser("~/.yourtube/data")
clustering_cache_template = os.path.join(data_path, "clustering_cache", "{}.pickle")
saved_clusters_template = os.path.join(data_path, "saved_clusters", "{}", "{}")
transcripts_path = os.path.join(data_path, "transcripts.json")


def load_graph(user):
    info = get_limited_user_relevant_video_info(user)  # 200 ms
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

        G.add_node(v1_video_id, **params_dict_v1)
        G.add_node(v2_video_id, **params_dict_v2)
        G.add_edge(v1_video_id, v2_video_id)

    playlist_info = get_all_user_relevant_playlist_info(user)
    for playlist_name, video_id, time_added in playlist_info:
        if video_id not in G.nodes:
            # this means the video had no recommended videos, and wasn't matched by the previous step
            # so it's probably down
            continue
        G.nodes[video_id]["from"] = playlist_name
        G.nodes[video_id]["time_added"] = time_added
    return G


def load_joined_graph_of_many_users(users):
    # load graphs of each user
    graphs = []
    for user in users:
        G = load_graph(user=user)
        graphs.append(G)

    # join them
    joined_graph = graphs[0]
    for G in graphs[1:]:
        if len(G.nodes) == 0:
            logger.error(f"user: {user}, tried to load an empty graph in multi-user mode")
        joined_graph.update(G)

    return joined_graph


def get_transcripts_db():
    return pickledb.load(transcripts_path, auto_dump=False)


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

import os
import pickle
import networkx as nx
from time import time

id_to_url = "https://www.youtube.com/watch?v={}"
id_to_thumbnail = "https://i.ytimg.com/vi/{}/hqdefault.jpg"

graph_path = "../data/graph.pickle"


def save_graph(G):
    assert 0 == len(list(nx.selfloop_edges(G)))
    # selfloop edges shouldn't happen
    # G.remove_edges_from(nx.selfloop_edges(G))

    with open(graph_path, "wb") as handle:
        pickle.dump(G, handle, protocol=pickle.HIGHEST_PROTOCOL)
    # print("graph saved")


def load_graph():
    # load or create a Graph
    if os.path.isfile(graph_path):
        print("graph loaded")
        with open(graph_path, "rb") as handle:
            return pickle.load(handle)
    else:
        print("graph created")
        return nx.DiGraph()


def get_from_playlists_from_time_range(G, start, end=None):
    if end is None:
        end = time()
    return [
        id_
        for id_, node in G.nodes.data()
        if "time_added" in node and start < node["time_added"] < end
    ]

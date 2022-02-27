# note that they are all generators

from itertools import chain
from time import time


def added_in_last_n_years(G, ids, n=5):
    seconds_in_month = 60 * 60 * 24 * 30.4
    seconds_in_year = seconds_in_month * 12
    start_time = time() - seconds_in_year * n
    # round start_time to months, to prevent clustering being recalculated too frequently
    # returned ids will change only each month, so the cached value will be used
    start_time = start_time // seconds_in_month * seconds_in_month

    for id_ in ids:
        node = G.nodes[id_]
        if "time_added" not in node:
            continue
        if start_time < node["time_added"]:
            yield id_


def only_not_watched(G, ids):
    for id_ in ids:
        node = G.nodes[id_]
        if not node.get("watched"):
            yield id_


def only_watched(G, ids):
    for id_ in ids:
        node = G.nodes[id_]
        if node.get("watched"):
            yield id_


def from_category(G, ids, categories):
    # note: if some of the ids hasn't beed scraped, they will be filtered out
    # regardless of their category (because it isn't known)
    for id_ in ids:
        node = G.nodes[id_]
        if node.get("category") in categories:
            yield id_


def not_down(G, ids):
    for id_ in ids:
        node = G.nodes[id_]
        if not node.get("is_down"):
            yield id_


def get_neighborhood(G, ids):
    out_edges = G.out_edges(ids)
    return G.edge_subgraph(out_edges).nodes


def select_nodes_to_cluster(G, use_watched=False):
    sources = added_in_last_n_years(G, list(G.nodes), n=5)
    if use_watched:
        watched = only_watched(G, list(G.nodes))
        # note that some videos will be duplicated because of this chain
        # but it's more efficient this way
        sources = chain(sources, watched)

    sources = not_down(G, sources)
    return list(get_neighborhood(G, sources))

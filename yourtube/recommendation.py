import hashlib
import logging
import os
import pickle
from time import time

import networkx as nx
import numpy as np
from krakow import krakow
from krakow.utils import create_dendrogram, split_into_n_children
from scipy.cluster.hierarchy import to_tree

from yourtube.file_operations import clustering_cache_template
from yourtube.filtering_functions import *

logger = logging.getLogger("yourtube")
logger.setLevel(logging.DEBUG)


def cluster_subgraph(nodes_to_cluster, G, balance=2):
    # use cache
    # here we assume that the same set of nodes will have the same graph structure
    # this is not true, but collisions are very rare and not destructive
    sorted_nodes = sorted(nodes_to_cluster)
    unique_string = "".join(sorted_nodes)
    node_hash = hashlib.md5(unique_string.encode()).hexdigest()
    unique_string = f"{balance:.1f}_{node_hash}"
    cache_file = clustering_cache_template.format(unique_string)
    if os.path.isfile(cache_file):
        logger.info(f"using cached clustering: {cache_file}")
        start_time = time()
        with open(cache_file, "rb") as handle:
            res = pickle.load(handle)
            logger.info(f"loaded clustering in {time() - start_time:.3f} seconds")
            return res

    start_time = time()

    RecentDirected = G.subgraph(nodes_to_cluster)
    Recent = RecentDirected.to_undirected()

    # choose only the biggest connected component
    components = sorted(nx.connected_components(Recent), key=len, reverse=True)
    # for el in components[:5]:
    #     print(len(el))
    main_component = components[0]
    Main = Recent.subgraph(main_component)

    D = krakow(Main, alpha=balance, beta=1)
    tree = to_tree(D)
    # normalized_dasgupta_cost(Main, D)

    # convert leaf values to original ids
    main_ids_list = np.array(Main.nodes)

    def substitute_video_id(leaf):
        leaf.id = main_ids_list[leaf.id]

    tree.pre_order(substitute_video_id)

    logger.info(f"clustering took: {time() - start_time:.3f} seconds")

    # create image
    img = create_dendrogram(D, clusters_limit=100, width=17.8, height=1.5)

    # save to cache
    with open(cache_file, "wb") as handle:
        pickle.dump((tree, img), handle, protocol=pickle.HIGHEST_PROTOCOL)
    return tree, img


# ranking functions


def liked_to_views_ratio(G, id_):
    node = G.nodes[id_]
    try:
        return node["like_count"] / node["view_count"]
    except (KeyError, TypeError, ZeroDivisionError):
        return -1


class Recommender:
    def __init__(self, G, seed):
        self.G = G
        self.seed = seed
        assert 1 <= seed <= 1000000

    def compute_node_ranks(self, ids):
        """This function must be called on given ids before we can use recommender on those ids."""

        source_videos = added_in_last_n_years(self.G, ids)
        # note: these may not really be source videos!

        # compute node ranks
        self.node_ranks = dict()
        source_videos_set = set(source_videos)
        for id_ in ids:
            in_edges = self.G.in_edges(id_)
            in_nodes = {u for u, v in in_edges}
            rank = len(in_nodes & source_videos_set)
            self.node_ranks[id_] = rank

    def get_index(self, length, exploration):
        assert 0 <= exploration <= 1
        np.random.seed(self.seed + length)
        position = np.random.triangular(1 - exploration, 1, 1)
        # other potential distributions are: exponential, lognormal
        index = int(length * position)
        # just to be sure, that we don't get IndexError due to numerical rounding
        index = np.clip(index, 0, length - 1)
        return index

    def recommend_by_in_degree(self, ids, params):
        # if there if nothing, return nothing
        if len(ids) == 0:
            return ""

        index = self.get_index(len(ids), params["exploration"])

        ranks = [self.node_ranks[id_] for id_ in ids]
        # find the index on ids list of the video with index'th smallest rank
        index_on_ids_list = np.argpartition(ranks, index)[index]
        chosen_id = ids[index_on_ids_list]
        return chosen_id

    def build_wall(self, grandchildren, params):
        """Given a 2D array of clusters, for each of them recommend one video.

        Returns an array of the same dimensions as input.
        """
        ids_to_show_in_wall = []
        for grandchildren_from_a_child in grandchildren:
            ids_to_show_in_group = []
            for grandchild in grandchildren_from_a_child:
                # this line is the speed bottleneck
                ids = grandchild.pre_order()
                # filter ids
                if params["hide_watched"]:
                    ids = list(only_not_watched(self.G, ids))
                id_to_show = self.recommend_by_in_degree(ids, params)
                ids_to_show_in_group.append(id_to_show)
            ids_to_show_in_wall.append(ids_to_show_in_group)
        return ids_to_show_in_wall


class TreeClimber:
    def __init__(self, num_of_groups, videos_in_group):
        self.num_of_groups = num_of_groups
        self.videos_in_group = videos_in_group

    def reset(self, tree):
        self.tree = tree
        self.path = []
        self.branch_id = ""
        self.children, self.grandchildren = self.new_offspring(self.tree)

    def choose_column(self, i):
        """Returns -1 if it's already on the lowest cluster.
        If succesful, returns 0.
        """
        new_tree = self.children[i]
        try:
            new_children, new_grandchildren = self.new_offspring(new_tree)
        except ValueError:
            return -1

        self.path.append(self.tree)
        self.branch_id += str(i + 1)
        self.tree = new_tree
        self.children = new_children
        self.grandchildren = new_grandchildren
        return 0

    def go_back(self):
        """Returns -1 if it's already on the highest cluster.
        If succesful, returns 0.
        """
        if self.path == []:
            return -1
        self.tree = self.path.pop()
        self.branch_id = self.branch_id[:-1]
        self.children, self.grandchildren = self.new_offspring(self.tree)
        return 0

    def new_offspring(self, new_tree):
        new_children = split_into_n_children(new_tree, n=self.num_of_groups)
        new_grandchildren = [
            split_into_n_children(new_child, n=self.videos_in_group) for new_child in new_children
        ]
        return new_children, new_grandchildren

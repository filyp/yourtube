from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import pickle
from pathlib import Path
from time import time

import networkx as nx
import numpy as np

from krakow import reorder_dendrogram

# from yourtube.optimized_krakow import krakow
from .rust_krakow import krakow

from krakow.utils import create_dendrogram, split_into_n_children
from scipy.cluster.hierarchy import to_tree

from yourtube.file_operations import load_graph, saved_cluster_path
from yourtube.json_db import get_playlist_names, get_playlist_video_ids_by_name
from yourtube.scraping import get_title_oembed

logger = logging.getLogger("yourtube")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
    logger.addHandler(handler)


# @profile
def cluster_graph(G, balance_alpha=2, create_image=True):
    # note that using create_image=False opens the possibility, that the cached image will be None
    # so watchout for that

    start_time = time()

    # Use weakly_connected_components directly on DiGraph (treats it as undirected)
    components = sorted(nx.weakly_connected_components(G), key=len, reverse=True)
    # Sorted for deterministic ordering and to map back to original IDs
    main_component_nodes = sorted(components[0])
    vid_to_idx = {vid: idx for idx, vid in enumerate(main_component_nodes)}

    # Build edge list
    edges = [
        (vid_to_idx[u], vid_to_idx[v])
        for u, v in G.subgraph(main_component_nodes).edges()
    ]

    D = krakow(len(main_component_nodes), edges, alpha=balance_alpha)
    D = reorder_dendrogram(np.array(D))
    tree = to_tree(D)
    # clustering_quality = 1 - normalized_dasgupta_cost(Main, D)

    # convert leaf values back to original video ids
    def substitute_video_id(leaf):
        leaf.id = main_component_nodes[leaf.id]

    tree.pre_order(substitute_video_id)

    logger.info(f"clustering took: {time() - start_time:.3f} seconds")

    if create_image:
        img = create_dendrogram(D, clusters_limit=100, width=17.8, height=1.5)
        # with open("dendrogram.png", "wb") as f:
        #     f.write(img.getvalue())
    else:
        img = None

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
        assert 1 <= seed <= 9999

    def compute_node_ranks(self, ids, source_ids=None):
        """This function must be called on given ids before we can use recommender on those ids.

        Args:
            ids: All video IDs to compute ranks for
            source_ids: If provided, only count incoming edges from these source nodes.
                       If None, uses all ids as sources (original behavior).
        """
        if source_ids is None:
            source_ids = ids

        # compute node ranks
        self.node_ranks = dict()
        source_videos_set = set(source_ids)
        for id_ in ids:
            in_edges = self.G.in_edges(id_)
            in_nodes = {u for u, v in in_edges}
            rank = len(in_nodes & source_videos_set)
            self.node_ranks[id_] = rank

    def get_index(self, length, exploration):
        assert 0 <= exploration <= 1
        np.random.seed(self.seed + length)
        if exploration == 0:
            position = 1
        else:
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

        ranks = [self.node_ranks.get(id_, 0) for id_ in ids]
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
        if not self.path:
            return -1
        self.tree = self.path.pop()
        self.branch_id = self.branch_id[:-1]
        self.children, self.grandchildren = self.new_offspring(self.tree)
        return 0

    def new_offspring(self, new_tree):
        new_children = split_into_n_children(new_tree, n=self.num_of_groups)
        new_grandchildren = [
            split_into_n_children(new_child, n=self.videos_in_group)
            for new_child in new_children
        ]
        return new_children, new_grandchildren


class Engine:
    def __init__(self, parameters):
        self.G = load_graph()
        self.num_of_groups = parameters.num_of_groups
        self.videos_in_group = parameters.videos_in_group

        self.tree_climber = TreeClimber(self.num_of_groups, self.videos_in_group)
        self.recommender = Recommender(self.G, parameters.seed)

        # nodes_to_cluster = {n for n, deg in self.G.degree() if deg >= 2}
        nodes_to_cluster = self.G.nodes

        tree, self.dendrogram_img = cluster_graph(
            self.G.subgraph(nodes_to_cluster),
            parameters.clustering_balance_a,
        )
        self.video_ids = tree.pre_order()
        self.playlists = get_playlist_names()
        self.tree_climber.reset(tree)

    def recompute_ranks(self, playlist_name, range_start, range_end):
        """Recompute node ranks based on playlist and range."""
        source_ids = get_playlist_video_ids_by_name(
            playlist_name, range_start, range_end
        )
        source_ids = source_ids & set(self.video_ids)
        self.recommender.compute_node_ranks(self.video_ids, source_ids)

    def get_video_ids(self, recommendation_parameters):
        return self.recommender.build_wall(
            self.tree_climber.grandchildren, recommendation_parameters
        )

    def get_video_title(self, video_id):
        return self.G.nodes[video_id].get("title", "")

    def save_current_cluster(self, cluster_name):
        # sanitize cluster name
        cluster_name = cluster_name.replace("/", "-")
        if cluster_name == "":
            return "You must enter some name for this cluster, before saving it"

        path = saved_cluster_path(cluster_name)

        # fail if cluster already exists
        if Path(path).exists():
            return "Saving the cluster failed: name already exists"

        # Copy mutable data to avoid "dictionary changed size during iteration"
        # errors when concurrent requests modify the graph or node_ranks
        data_to_save = (
            self.tree_climber.tree,
            dict(self.recommender.node_ranks),
            self.G.copy(),
        )

        # make sure directory exists
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        # save cluster
        with open(path, "wb") as handle:
            pickle.dump(data_to_save, handle, protocol=pickle.HIGHEST_PROTOCOL)

        return "cluster saved successfully"

    def load_cluster(self, cluster_name):
        path = saved_cluster_path(cluster_name)
        with open(path, "rb") as handle:
            tree, node_ranks, graph = pickle.load(handle)
        self.tree_climber.reset(tree)
        self.recommender.node_ranks = node_ranks
        self.G = graph

    def fetch_videos(self, recommendation_parameters):
        ids = self.get_video_ids(recommendation_parameters)
        flat_ids = [id_ for row in ids for id_ in row]

        # scrape titles
        to_scrape = [id_ for id_ in flat_ids if not self.G.nodes[id_].get("title")]

        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_id = {
                executor.submit(get_title_oembed, vid): vid for vid in to_scrape
            }
            for future in as_completed(future_to_id):
                vid = future_to_id[future]
                try:
                    title = future.result()
                    self.G.nodes[vid]["title"] = title
                except Exception as e:
                    pass

import functools
import logging
import random
from threading import Thread
from time import sleep, time

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import panel as pn
from IPython.core.display import HTML, display
from krakow import krakow
from krakow.utils import split_into_n_children
from neo4j import GraphDatabase
from scipy.cluster.hierarchy import cut_tree, leaves_list, to_tree

logger = logging.getLogger("yourtube")
logger.setLevel(logging.DEBUG)

plt.style.use("dark_background")

pn.extension()
# pn.extension(template='vanilla')
# pn.extension(template='material', theme='dark')
# pn.extension('ipywidgets')

from yourtube.file_operations import (
    cluster_cache_path,
    id_to_url,
    load_graph_from_neo4j,
)
from yourtube.material_components import (
    MaterialButton,
    MaterialSwitch,
    required_modules,
)
from yourtube.scraping import scrape_from_list

id_to_thumbnail = "https://i.ytimg.com/vi/{}/mqdefault.jpg"
# id_to_thumbnail = "https://i.ytimg.com/vi/{}/maxresdefault.jpg"
# hq and sd usually has black stripes
# mq < hq < sd < maxres

# filtering functions
# note that they are all generators

from itertools import chain


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
    sources = added_in_last_n_years(G, G.nodes, n=5)
    if use_watched:
        watched = only_watched(G, G.nodes)
        # note that some videos will be duplicated because of this chain
        # but it's more efficient this way
        sources = chain(sources, watched)

    sources = not_down(G, sources)
    return list(get_neighborhood(G, sources))


def cluster_subgraph(nodes_to_cluster, G, balance=2):
    # TODO rethink how to cache, for now it must be turned off, to avoid shelve errors
    # # use cache
    # sorted_nodes = sorted(nodes_to_cluster)
    # unique_node_string = "".join(sorted_nodes)
    # unique_node_string += str(balance)
    # node_hash = hashlib.md5(unique_node_string.encode()).hexdigest()
    # with shelve.open(cluster_cache_path) as cache:
    #     if node_hash in cache:
    #         return cache[node_hash]

    start_time = time()
    logger.info("start clustering...")

    RecentDirected = G.subgraph(nodes_to_cluster)
    Recent = RecentDirected.to_undirected()

    # choose only the biggest connected component
    components = sorted(nx.connected_components(Recent), key=len, reverse=True)
    # for el in components[:5]:
    #     print(len(el))
    main_component = components[0]
    Main = Recent.subgraph(main_component)

    D = krakow(Main, balance=balance)
    tree = to_tree(D)

    # img = plot_dendrogram(D, clusters_limit=100, width=17.8, height=1.5)
    img = None

    # normalized_dasgupta_cost(Main, D)

    def convert_leaf_values_to_original_ids(tree, Graph):
        main_ids_list = np.array(Graph.nodes)

        def substitute_video_id(leaf):
            leaf.id = main_ids_list[leaf.id]

        tree.pre_order(substitute_video_id)

    convert_leaf_values_to_original_ids(tree, Main)

    # TODO rethink how to cache
    # # save to cache
    # with shelve.open(cluster_cache_path) as cache:
    #     cache[node_hash] = tree, img
    logger.info(f"clustering took: {time() - start_time:.3f} seconds")
    return tree, img


# ranking functions


def liked_to_views_ratio(G, id_):
    node = G.nodes[id_]
    try:
        return node["like_count"] / node["view_count"]
    except (KeyError, TypeError, ZeroDivisionError):
        return -1


# TODO move this to krakow
import io

from scipy.cluster.hierarchy import dendrogram


def plot_dendrogram(D, clusters_limit=100, width=10, height=4):
    # a hack to disable plotting, only return the image
    was_interactive = plt.isinteractive()
    plt.ioff()

    _ = plt.figure(figsize=(width, height))
    # display logarithm of cluster distances
    Dlog = D.copy()
    Dlog[:, 2] = np.log(Dlog[:, 2])
    # cut off the bottom part of the plot as it's not informative
    Dlog[:, 2][:-clusters_limit] *= 0
    Dlog[-clusters_limit:, 2] = Dlog[-clusters_limit:, 2] - Dlog[-clusters_limit, 2]

    dendrogram(Dlog, leaf_rotation=90.0, truncate_mode="lastp", p=clusters_limit)
    plt.axis("off")
    img = io.BytesIO()
    plt.savefig(img, bbox_inches="tight")

    # revert to the previous plt state
    if was_interactive:
        plt.ion()
    return img


class Recommender:
    def __init__(self, G, cutoff=0.7, seed=None):
        self.G = G
        self.cutoff = cutoff
        self.seed = seed if seed is not None else random.randint(1, 1000000)
        assert 0 < cutoff < 1

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

    def get_index(self, length):
        np.random.seed(self.seed + length)
        position = np.random.triangular(self.cutoff, 1, 1)
        # other potential distributions are: exponential, lognormal
        index = int(length * position)
        # just to be sure, that we don't get IndexError due to numerical rounding
        index = np.clip(index, 0, length - 1)
        return index

    def recommend_by_in_degree(self, ids):
        # if there if nothing, return nothing
        if len(ids) == 0:
            return ""

        index = self.get_index(len(ids))

        ranks = [self.node_ranks[id_] for id_ in ids]
        # find the index on ids list of the video with index'th smallest rank
        index_on_ids_list = np.argpartition(ranks, index)[index]
        chosen_id = ids[index_on_ids_list]
        return chosen_id

    def build_wall(self, grandchildren, hide_watched=False):
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
                if hide_watched:
                    ids = list(only_not_watched(self.G, ids))
                id_to_show = self.recommend_by_in_degree(ids)
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
        self.children, self.grandchildren = self.new_offspring(self.tree)
        return 0

    def new_offspring(self, new_tree):
        new_children = split_into_n_children(new_tree, n=self.num_of_groups)
        new_grandchildren = [
            split_into_n_children(new_child, n=self.videos_in_group) for new_child in new_children
        ]
        return new_children, new_grandchildren


class UI:
    def __init__(
        self,
        G,
        driver,
        num_of_groups,
        videos_in_group,
        clustering_balance,
        recommendation_cutoff,
        column_width,
        orientation,
        seed,
    ):
        # TODO orientation is temporarily broken
        self.G = G
        self.driver = driver
        self.num_of_groups = int(num_of_groups)
        self.videos_in_group = int(videos_in_group)
        # round to have less possible balance values, to better use cache
        self.clustering_balance = round(clustering_balance, 1)
        self.column_width = column_width
        self.orientation = orientation
        assert orientation in ["vertical", "horizontal"]
        self.grid_gap = 20
        self.row_height = column_width * 1.1
        self.scraping_thread = Thread()

        self.recommender = Recommender(G, recommendation_cutoff, seed)

        self.message_output = pn.pane.HTML('<div id="header" style="width:800px;"></div>')
        self.tree_climber = TreeClimber(self.num_of_groups, self.videos_in_group)
        # TODO note that vertical is currently broken!

        # define UI controls
        go_back_button = MaterialButton(
            label="Go back",
            on_click=self.go_back,
            style="width: 110px",
        )
        self.hide_watched_checkbox = MaterialSwitch(initial_value=False, width=40)
        self.hide_watched_checkbox.on_event(
            "switch_id", "click", self.update_displayed_videos_without_cache
        )

        top = pn.Row(
            go_back_button,
            pn.Spacer(width=20),
            self.hide_watched_checkbox,
            pn.pane.HTML("Hide watched videos"),
            required_modules,
        )

        # if there are too few videos in playlists, it's better to also use watched videos
        self.use_watched = len(list(added_in_last_n_years(G, G.nodes))) < 400

        # conscruct group choice buttons
        if self.orientation == "vertical":
            # TODO vertical layout
            label = "⮟"
        elif self.orientation == "horizontal":
            button_height = self.column_width * 9 // 16
            style = f"height: {button_height}px; width: 60px"
            label = "➤"
            button_gap = int(self.row_height - button_height)
        self.choice_buttons = []
        button_box = pn.Column()
        for i in range(self.num_of_groups):
            button = MaterialButton(label=label, style=style)
            # bind this button to its column choice
            button.on_click = functools.partial(self.choose_column, i=i)

            self.choice_buttons.append(button)
            # construct button box
            button_box.append(button)
            button_box.append(pn.Spacer(height=button_gap))
        # pop the last spacer
        button_box.pop(-1)

        self.video_wall = pn.pane.HTML("")
        if self.orientation == "vertical":
            # TODO vertical layout
            pass
        elif self.orientation == "horizontal":
            self.whole_output = pn.Column(
                top,
                self.message_output,
                # adding spacer with a width 0 gives a correct gap for some reason
                pn.Row(button_box, pn.Spacer(width=0), self.video_wall),
            )

        self.recluster(None)

    def recluster(self, _):
        nodes_to_cluster = select_nodes_to_cluster(
            self.G,
            use_watched=self.use_watched,
        )
        self._nodes = nodes_to_cluster
        # clear video_wall to indicate that something is happening
        self.video_wall.object = ""
        # self.message_output.object = ""
        # TODO align message output in a better way, maybe with GridSpec
        self.message_output.object = '<div id="header" style="width:800px;"></div>'

        tree, img = cluster_subgraph(nodes_to_cluster, self.G, self.clustering_balance)
        # TODO add image output as HTML

        video_ids = tree.pre_order()

        self.recommender.compute_node_ranks(video_ids)
        self.tree_climber.reset(tree)
        self.previous_ids_to_show = []

        self.update_displayed_videos_without_cache()

    def display_video_grid(self, ids, display_text=True):
        if self.orientation == "vertical":
            ids = np.transpose(ids).flatten()
            num_of_columns = self.num_of_groups
        elif self.orientation == "horizontal":
            ids = np.array(ids).flatten()
            num_of_columns = self.videos_in_group

        css_style = """
            <style>
            .wrapper {{
              display: grid;
              grid-template-columns:{};
              grid-gap: {}px;
            }}
            </style>
        """.format(
            f"{self.column_width}px " * num_of_columns,
            self.grid_gap,
        )
        html = '<div class="wrapper">'
        for id_ in ids:
            if id_ == "" or G.nodes[id_].get("is_down"):
                # it's "" if its cluster turned out empty after filtering
                # it can also be down
                # show an empty slot
                html += f'<div style="height: {self.row_height}px;"></div>'
                continue

            video_url = id_to_url.format(id_)
            image_url = id_to_thumbnail.format(id_)

            if display_text:
                # logger.debug(id_)
                title = self.G.nodes[id_]["title"]
                rank = self.recommender.node_ranks.get(id_)
                likes_to_views = liked_to_views_ratio(self.G, id_)
                likes_to_views = int(likes_to_views * 1000)
                info = f"rank: {rank}   l/v: {likes_to_views}"
                text = f'<a href="{video_url}" target="_blank" style="text-decoration: none; color:#EEEEEE;">{info}<br>{title}</a>'
            else:
                text = ""

            html += f"""
            <div style="height: {self.row_height}px;">
                <a href="{video_url}" target="_blank"><img src="{image_url}" style='width: 100%; object-fit: contain'/></a>
                {text}
            </div>"""
        html += "</div>"
        self.video_wall.object = css_style + html

    #     def choose_column(self, _widget, _event, _data, i):
    def choose_column(self, _change, i):
        # make sure that the previous scraping ended
        while self.scraping_thread.is_alive():
            sleep(0.05)

        self.message_output.object = ""

        exit_code = self.tree_climber.choose_column(i)
        if exit_code == -1:
            self.message_output.object = "already on the lowest cluster"
            return

        self.previous_ids_to_show.append(self.ids_to_show)
        self.ids_to_show = self.potential_ids_to_show[i]
        self.update_displayed_videos()

    # def go_back(self, _widget, _event, _data):
    def go_back(self, _event):
        # make sure that the previous scraping ended
        while self.scraping_thread.is_alive():
            sleep(0.05)

        self.message_output.object = ""

        exit_code = self.tree_climber.go_back()
        if exit_code == -1:
            self.message_output.object = "already on the highest cluster"
            return

        self.ids_to_show = self.previous_ids_to_show.pop()
        self.update_displayed_videos()

    def update_displayed_videos_without_cache(self, _event=None):
        self.ids_to_show = self.recommender.build_wall(
            self.tree_climber.grandchildren, self.hide_watched_checkbox.value
        )
        scrape_from_list(
            self.ids_to_show,
            self.driver,
            skip_if_fresher_than=float("inf"),
            non_verbose=True,
            G=self.G,
        )
        self.update_displayed_videos()

    def update_displayed_videos(self, _widget=None, _event=None, _data=None):
        self.display_video_grid(self.ids_to_show)
        # threading is needed, because panel updates its widgets only when the main thread is idle
        self.scraping_thread = Thread(target=self.fetch_new_videos)
        self.scraping_thread.start()

    def fetch_new_videos(self):
        self.potential_ids_to_show = []
        for i in range(self.num_of_groups):
            potential_tree = self.tree_climber.children[i]
            try:
                _, potential_grandchildren = self.tree_climber.new_offspring(potential_tree)
            except ValueError:
                empty_wall = np.full((self.num_of_groups, self.videos_in_group), "")
                self.potential_ids_to_show.append(empty_wall)
                continue

            # potential_granchildren has a dimension: (num_of_groups, videos_in_group)
            ids_to_show_in_wall = self.recommender.build_wall(
                potential_grandchildren, self.hide_watched_checkbox.value
            )
            self.potential_ids_to_show.append(ids_to_show_in_wall)

        scrape_from_list(
            self.potential_ids_to_show,
            self.driver,
            skip_if_fresher_than=float("inf"),
            non_verbose=True,
            G=self.G,
        )


#######################################################################################

driver = GraphDatabase.driver("neo4j://localhost:7687", auth=("neo4j", "yourtube"))

start_time = time()
logger.info("start loading graph...")
G = load_graph_from_neo4j(driver, user="default")
logger.info(f"loading graph took: {time() - start_time:.3f} seconds")


parameters = dict(
    num_of_groups=3,
    videos_in_group=5,
    clustering_balance=1.4,
    recommendation_cutoff=0.9,
    column_width=260,
    orientation="horizontal",
    seed=None,
)

ui = UI(G, driver, **parameters)

# # only sane templates are FastListTemplate and VanillaTemplate and MaterialTemplate
template = pn.template.MaterialTemplate(title="YourTube", theme=pn.template.DarkTheme)

# dummy_slider = pn.widgets.FloatSlider(name="Phase", start=0, end=np.pi)
# template.sidebar.append(dummy_slider)

template.main.append(ui.whole_output)
template.servable()

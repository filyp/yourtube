import functools
import hashlib
import logging
import os
import pickle
import random
from threading import Thread
from time import time

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import panel as pn
import param
from krakow import krakow
from krakow.utils import create_dendrogram, split_into_n_children
from neo4j import GraphDatabase
from scipy.cluster.hierarchy import leaves_list, to_tree

logger = logging.getLogger("yourtube")
logger.setLevel(logging.DEBUG)

plt.style.use("dark_background")

# pn.extension doesn't support loading
pn.extension(
    # js_files={
    #     'mdc': 'https://unpkg.com/material-components-web@latest/dist/material-components-web.min.js',
    #     "vue": "https://cdn.jsdelivr.net/npm/vue@2.x/dist/vue.js",
    #     "vuetify": "https://cdn.jsdelivr.net/npm/vuetify@2.x/dist/vuetify.js",
    # },
    # css_files=[
    #     'https://unpkg.com/material-components-web@latest/dist/material-components-web.min.css',
    #     "https://fonts.googleapis.com/icon?family=Material+Icons",
    #     "https://cdn.jsdelivr.net/npm/@mdi/font@6.x/css/materialdesignicons.min.css",
    #     "https://cdn.jsdelivr.net/npm/vuetify@2.x/dist/vuetify.min.css",
    #     "https://fonts.googleapis.com/css?family=Roboto:100,300,400,500,700,900",
    # ],
)
# pn.extension(template='vanilla')
# pn.extension(template='material', theme='dark')
# pn.extension('ipywidgets')

from yourtube.file_operations import (
    clustering_cache_template,
    id_to_url,
    load_graph_from_neo4j,
)
from yourtube.filtering_functions import *
from yourtube.html_components import (
    MaterialButton,
    MaterialSlider,
    MaterialSwitch,
    MaterialTextField,
    VideoGrid,
    required_modules,
)
from yourtube.scraping import scrape_from_list


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
    def __init__(self, G, cutoff, seed):
        self.G = G
        self.cutoff = cutoff
        self.seed = seed
        assert 0 < cutoff < 1
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


class UI:
    info_template = '<div id="message_output" style="width:400px;">{}</div>'

    def __init__(
        self,
        G,
        driver,
        parameters,
    ):
        # TODO orientation is temporarily broken
        self.G = G
        self.driver = driver

        self.num_of_groups = parameters.num_of_groups
        self.videos_in_group = parameters.videos_in_group
        self.clustering_balance = parameters.clustering_balance
        self.column_width = parameters.column_width
        self.orientation = parameters.orientation
        self.show_image = parameters.show_image

        self.grid_gap = 20
        self.row_height = self.column_width * 1.0
        self.scraping_thread = Thread()

        self.image_output = pn.pane.PNG()
        self.message_output = pn.pane.HTML("")
        self.tree_climber = TreeClimber(self.num_of_groups, self.videos_in_group)
        # TODO note that vertical is currently broken!

        self.exploration_slider = pn.widgets.FloatSlider(
            name="Exploration", start=0, end=1, step=0.01, value=0.1
        )
        self.recommender = Recommender(G, 1 - self.exploration_slider.value, parameters.seed)

        # define UI controls
        go_back_button = MaterialButton(
            label="Go back",
            style="width: 110px",
        )
        go_back_button.on_click = self.go_back

        self.hide_watched_checkbox = MaterialSwitch(initial_value=False, width=40)
        self.hide_watched_checkbox.on_event("switch_id", "click", self.update_displayed_videos)

        refresh_button = MaterialButton(
            label="Refresh",
            style="width: 110px",
        )
        refresh_button.on_click = self.update_displayed_videos

        top = pn.Row(
            go_back_button,
            pn.Spacer(width=20),
            self.hide_watched_checkbox,
            pn.pane.HTML("Hide watched videos"),
            self.exploration_slider,
            refresh_button,
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

        if self.orientation == "vertical":
            num_of_columns = self.num_of_groups
        elif self.orientation == "horizontal":
            num_of_columns = self.videos_in_group
        self.video_wall = VideoGrid(
            self.num_of_groups * self.videos_in_group,
            num_of_columns,
            self.column_width,
            self.row_height,
            self.grid_gap,
        )

        if self.orientation == "vertical":
            # TODO vertical layout
            pass
        elif self.orientation == "horizontal":
            self.whole_output = pn.Column(
                self.image_output,
                top,
                self.message_output,
                pn.Spacer(height=5),
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
        # TODO # clear video_wall to indicate that something is happening
        # self.video_wall.object = ""

        self.message_output.object = ""

        tree, img = cluster_subgraph(nodes_to_cluster, self.G, self.clustering_balance)
        if self.show_image:
            self.image_output.object = img

        video_ids = tree.pre_order()
        self.recommender.compute_node_ranks(video_ids)
        self.tree_climber.reset(tree)

        self.update_displayed_videos()

    def display_video_grid(self):
        self.recommender.cutoff = 1 - self.exploration_slider.value
        ids = self.recommender.build_wall(
            self.tree_climber.grandchildren, self.hide_watched_checkbox.value
        )

        if self.orientation == "vertical":
            ids = np.transpose(ids).flatten()
        elif self.orientation == "horizontal":
            ids = np.array(ids).flatten()

        texts = []
        for i, id_ in enumerate(ids):
            if id_ == "" or G.nodes[id_].get("is_down"):
                # it's "" if its cluster turned out empty after filtering
                # it can also be down
                ids[i] = "RqJVa0fl01w"  # confused Travolta
                texts.append("-")
                continue
            # logger.debug(id_)
            if "title" in self.G.nodes[id_]:
                title = self.G.nodes[id_]["title"]
            else:
                title = ""
            # TODO refine and show video info
            # rank = self.recommender.node_ranks.get(id_)
            # likes_to_views = liked_to_views_ratio(self.G, id_)
            # likes_to_views = int(likes_to_views * 1000)
            # info = f"rank: {rank}   l/v: {likes_to_views}"
            # text = f"{info}<br>{title}"
            text = title
            texts.append(text)

        self.video_wall.ids = list(ids)
        self.video_wall.texts = texts
        self.video_wall.update()

    def choose_column(self, _change, i):
        exit_code = self.tree_climber.choose_column(i)
        self.message_output.object = self.info_template.format(self.tree_climber.branch_id)

        if exit_code == -1:
            self.message_output.object = self.info_template.format("already on the lowest cluster")
            return

        self.update_displayed_videos()

    def go_back(self, _event):
        exit_code = self.tree_climber.go_back()
        self.message_output.object = self.info_template.format(self.tree_climber.branch_id)

        if exit_code == -1:
            self.message_output.object = self.info_template.format("already on the highest cluster")
            return

        self.update_displayed_videos()

    def update_displayed_videos(self, _widget=None, _event=None, _data=None):
        self.display_video_grid()
        # threading is needed, because panel updates its widgets only when the main thread is idle
        self.scraping_thread = Thread(target=self.fetch_current_videos)
        self.scraping_thread.start()

    def fetch_current_videos(self):
        self.recommender.cutoff = 1 - self.exploration_slider.value
        ids = self.recommender.build_wall(
            self.tree_climber.grandchildren, self.hide_watched_checkbox.value
        )

        # scrape current videos
        scrape_from_list(
            ids,
            self.driver,
            skip_if_fresher_than=float("inf"),  # skip if already scraped anytime
            non_verbose=True,
            G=self.G,
        )
        # display current videos
        self.display_video_grid()

        # find potential videos
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

        # scrape potential videos in advance
        scrape_from_list(
            self.potential_ids_to_show,
            self.driver,
            skip_if_fresher_than=float("inf"),  # skip if already scraped anytime
            non_verbose=True,
            G=self.G,
        )


#######################################################################################

driver = GraphDatabase.driver("neo4j://localhost:7687", auth=("neo4j", "yourtube"))

start_time = time()
G = load_graph_from_neo4j(driver, user="default")
logger.info(f"loading graph took: {time() - start_time:.3f} seconds")


class Parameters(param.Parameterized):
    seed = param.Integer()
    clustering_balance = param.Number(1.4, bounds=(1, 2.5), step=0.1)
    num_of_groups = param.Integer(3, bounds=(2, 10), step=1)
    videos_in_group = param.Integer(5, bounds=(1, 10), step=1)
    show_image = param.Boolean(True)
    column_width = param.Integer(260, bounds=(100, 500), step=10)
    orientation = param.ObjectSelector("horizontal", ["horizontal", "vertical"])


parameters = Parameters(seed=random.randint(1, 1000000))

# # only sane templates are FastListTemplate and VanillaTemplate and MaterialTemplate
template = pn.template.MaterialTemplate(title="YourTube", theme=pn.template.DarkTheme)

ui = UI(G, driver, parameters)
ui_wrapper = pn.Row(ui.whole_output)
template.main.append(ui_wrapper)


def refresh(_event):
    logger.info("refreshed")
    template.main[0][0] = pn.Spacer()
    new_ui = UI(G, driver, parameters)
    template.main[0][0] = new_ui.whole_output


refresh_button = pn.widgets.Button(name="Refresh")
refresh_button.on_click(refresh)

template.sidebar.append(parameters)
template.sidebar.append(refresh_button)
template.servable()

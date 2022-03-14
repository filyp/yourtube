import functools
import logging
import random
from time import time

import matplotlib.pyplot as plt
import numpy as np
import panel as pn
import param
from neo4j import GraphDatabase

from yourtube.file_operations import (
    user_takeout_exists,
    update_user_takeout,
    load_joined_graph_of_many_users,
    get_saved_clusters,
)
from yourtube.html_components import (
    MaterialButton,
    MaterialSwitch,
    MaterialTextField,
    VideoGrid,
    required_modules,
)
from yourtube.recommendation import Engine
from yourtube.config import Config, Msgs

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


class UI:
    def __init__(
        self,
        engine,
        parameters,
    ):

        self.engine = engine
        self.num_of_groups = parameters.num_of_groups
        self.videos_in_group = parameters.videos_in_group
        self.column_width = parameters.column_width

        self.grid_gap = 20
        self.row_height = self.column_width * 1.0

        self.image_output = pn.pane.PNG()
        self.message_output = pn.pane.HTML("")

        self.exploration_slider = pn.widgets.FloatSlider(
            name="Exploration", start=0, end=1, step=0.01, value=0.1
        )

        # define UI controls
        go_back_button = MaterialButton(
            label="Go back",
            style="width: 110px; height:57px",
        )
        go_back_button.on_click = self.go_back

        self.hide_watched_checkbox = MaterialSwitch(initial_value=False, width=40)
        self.hide_watched_checkbox.on_event("switch_id", "click", self.update_displayed_videos)

        refresh_button = MaterialButton(
            label="Refresh",
            style="width: 110px; height:57px",
        )
        refresh_button.on_click = self.update_displayed_videos

        self.cluster_to_save_name_field = MaterialTextField(
            label="Cluster name",
            value="Enter cluster name...",
        )
        save_cluster_button = MaterialButton(
            label="Save cluster",
            style="width: 110px; height:57px",
        )
        save_cluster_button.on_click = self.save_current_cluster

        self.saved_cluster_selector = pn.widgets.Select(
            name="Saved clusters", options=get_saved_clusters(parameters.username)
        )
        load_cluster_button = MaterialButton(
            label="Load cluster",
            style="width: 110px; height:57px",
        )
        load_cluster_button.on_click = self.load_cluster

        top = pn.Row(
            go_back_button,
            pn.Spacer(width=20),
            self.hide_watched_checkbox,
            pn.pane.HTML("Hide watched videos"),
            self.exploration_slider,
            refresh_button,
            pn.Spacer(width=20),
            self.cluster_to_save_name_field,
            save_cluster_button,
            pn.Spacer(width=20),
            self.saved_cluster_selector,
            load_cluster_button,
            required_modules,
        )

        # conscruct group choice buttons
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

        num_of_columns = self.videos_in_group
        self.video_wall = VideoGrid(
            self.num_of_groups * self.videos_in_group,
            num_of_columns,
            self.column_width,
            self.row_height,
            self.grid_gap,
        )

        self.whole_output = pn.Column(
            self.image_output,
            top,
            self.message_output,
            pn.Spacer(height=5),
            # adding spacer with a width 0 gives a correct gap for some reason
            pn.Row(button_box, pn.Spacer(width=0), self.video_wall),
        )

        if parameters.show_dendrogram:
            # image can be None
            if self.engine.dendrogram_img is None:
                logger.info("cannot display image: no image in cache")
            else:
                self.image_output.object = self.engine.dendrogram_img

        self.update_displayed_videos()

    def get_recommendation_parameters(self):
        return dict(
            hide_watched=self.hide_watched_checkbox.value,
            exploration=self.exploration_slider.value,
        )

    def display_video_grid(self):
        ids = self.engine.get_video_ids(self.get_recommendation_parameters())
        ids = np.array(ids).flatten()

        texts = []
        for i, id_ in enumerate(ids):
            if id_ == "" or self.engine.is_video_down(id_):
                # it's "" if its cluster turned out empty after filtering
                # it can also be down
                ids[i] = "RqJVa0fl01w"  # confused Travolta
                texts.append("-")
                continue
            # logger.debug(id_)
            title = self.engine.get_video_title(id_)
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
        exit_code = self.engine.choose_column(i)
        self.show_message(self.engine.get_branch_id())

        if exit_code == -1:
            self.show_message("already on the lowest cluster")
            return

        self.update_displayed_videos()

    def go_back(self, _event):
        exit_code = self.engine.go_back()
        self.show_message(self.engine.get_branch_id())

        if exit_code == -1:
            self.show_message("already on the highest cluster")
            return

        self.update_displayed_videos()

    def save_current_cluster(self, _event):
        self.engine.save_current_cluster(self.cluster_to_save_name_field.value)

    def load_cluster(self, _event):
        self.engine.load_cluster(self.saved_cluster_selector.value)

    def update_displayed_videos(self, _widget=None, _event=None, _data=None):
        self.display_video_grid()
        self.engine.fetch_videos(self.get_recommendation_parameters())

    def show_message(self, message):
        info_template = '<div id="message_output" style="width:400px;">{}</div>'
        self.message_output.object = info_template.format(message)


#######################################################################################


class Parameters(param.Parameterized):
    seed = param.Integer()
    clustering_balance_a = param.Number(1.7, bounds=(1, 2.5), step=0.1)
    clustering_balance_b = param.Number(1, bounds=(1, 2.5), step=0.1)
    num_of_groups = param.Integer(3, bounds=(2, 10), step=1)
    videos_in_group = param.Integer(5, bounds=(1, 10), step=1)
    show_dendrogram = param.Boolean(False)
    column_width = param.Integer(260, bounds=(100, 500), step=10)
    username = param.String(default="default")


parameters = Parameters(seed=random.randint(1, 9999))
takeout_file_input = pn.widgets.FileInput(accept=".zip", multiple=False)
# pn.state.location.sync(parameters, ["username"])

driver = GraphDatabase.driver("neo4j://neo4j:7687", auth=("neo4j", Config.neo4j_password))

# # only sane templates are FastListTemplate and VanillaTemplate and MaterialTemplate
template = pn.template.MaterialTemplate(title="YourTube", theme=pn.template.DarkTheme)
template.main.append(pn.Row([pn.Spacer()]))


def refresh(_event):
    # it looks that it needs to be global, so that ui gets dereferenced, and can disappear
    # otherwise it is still bound to the new panel buttons, probably due to some panel quirk
    # and this causes each click to be executed double
    global ui, engine, G, takeout_file_input
    logger.info("refreshed")
    template.main[0][0] = pn.Spacer()

    usernames = parameters.username.split("+")
    if len(usernames) == 1:
        username = usernames[0]
        if "/" in username:
            logger.info(f"bad username: {username}")
            template.main[0][0] = pn.pane.Markdown(Msgs.bad_username)
            return
        if (not user_takeout_exists(username)) and (takeout_file_input.value is None):
            template.main[0][0] = pn.pane.Markdown(Msgs.user_doesnt_exist.format(username))
            return
        elif (not user_takeout_exists(username)) and (takeout_file_input.value is not None):
            logger.info("creating new user")
            takeout_ok = update_user_takeout(username, takeout_file_input)
            if takeout_ok:
                logger.info(f"created new user: {username}")
                template.main[0][0] = pn.pane.Markdown(Msgs.user_created)
            else:
                logger.error(f"failed to create a new user: {username}")
                template.main[0][0] = pn.pane.Markdown(Msgs.user_creation_failed)
            return
        elif user_takeout_exists(username) and (takeout_file_input.value is not None):
            logger.info(f"someone tried to create a new user with existing username: {username}")
            template.main[0][0] = pn.pane.Markdown(Msgs.user_already_exists)
            return
    else:
        # multiple users!
        for username in usernames:
            if "/" in username:
                logger.info(f"bad username: {username}")
                template.main[0][0] = pn.pane.Markdown(Msgs.bad_username)
                return
            if not user_takeout_exists(username):
                template.main[0][0] = pn.pane.Markdown(Msgs.user_doesnt_exist.format(username))
                return

    start_time = time()
    # G = load_graph_from_neo4j(driver, user=parameters.username)
    G = load_joined_graph_of_many_users(driver, usernames)
    logger.info(f"loading graph took: {time() - start_time:.3f} seconds")
    logger.info(f"user: {parameters.username}, graph size: {len(G.nodes)}")
    if len(G.nodes) == 0:
        logger.error(f"user: {parameters.username}, tried to load an empty graph")
        template.main[0][0] = pn.pane.Markdown(Msgs.trying_to_load_empty_graph)
        return

    # ensure correct param values
    if parameters.seed < 1 or parameters.seed > 9999:
        parameters.seed = random.randint(1, 9999)

    engine = Engine(G, driver, parameters)
    ui = UI(engine, parameters)
    engine.display_callback = ui.display_video_grid
    engine.message_callback = ui.show_message

    template.main[0][0] = ui.whole_output


refresh_button = pn.widgets.Button(name="Refresh")
refresh_button.on_click(refresh)

template.sidebar.append(parameters)
template.sidebar.append(takeout_file_input)
template.sidebar.append(refresh_button)
template.servable()

refresh(None)

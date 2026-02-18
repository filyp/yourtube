import base64
import io
import logging
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from yourtube import config
from yourtube.file_operations import get_saved_clusters
from yourtube.recommendation import Engine
from yourtube.scraping import get_title_oembed

plt.style.use("dark_background")

logger = logging.getLogger("yourtube")

app_dir = Path(__file__).parent
app = FastAPI()
app.mount("/static", StaticFiles(directory=app_dir / "static"), name="static")
templates = Jinja2Templates(directory=app_dir / "templates")


@dataclass
class AppState:
    engine: Engine | None = None
    exploration: float = 0.1
    message: str = ""
    num_of_groups: int = 3
    videos_in_group: int = 5
    column_width: int = 230
    selected_playlist: str = ""
    playlist_range: tuple = (0.0, 1.0)


state = AppState()


def build_engine():
    params = SimpleNamespace(
        seed=config.clustering_seed,
        clustering_balance_a=config.balance_alpha,
        num_of_groups=state.num_of_groups,
        videos_in_group=state.videos_in_group,
    )

    state.engine = Engine(params)

    if len(state.engine.G.nodes) == 0:
        state.engine = None
        state.message = "Nothing to show :("
    else:
        state.message = ""
        state.selected_playlist = state.engine.playlists[0]
        state.engine.recompute_ranks(state.selected_playlist, *state.playlist_range)


def wall_context():
    engine = state.engine
    if engine is None:
        return {"video_data": None, "videos_flat": [], "children_sizes": [], "message": state.message}

    params = {"exploration": state.exploration}
    ids_2d = engine.get_video_ids(params)

    videos_flat = []
    for row in ids_2d:
        for vid in row:
            videos_flat.append({"id": vid, "title": engine.get_video_title(vid)})

    children_sizes = [len(c.pre_order()) for c in engine.tree_climber.children]
    button_height = state.column_width * 9 // 16

    return {
        "video_data": True,
        "videos_flat": videos_flat,
        "children_sizes": children_sizes,
        "num_of_groups": state.num_of_groups,
        "videos_in_group": state.videos_in_group,
        "column_width": state.column_width,
        "row_height": state.column_width * 1.0,
        "grid_gap": 20,
        "button_height": button_height,
        "message": state.message,
    }


def dendrogram_b64():
    if not config.show_dendrogram or not state.engine or not state.engine.dendrogram_img:
        return None
    # dendrogram_img is already a BytesIO object with PNG data
    state.engine.dendrogram_img.seek(0)
    return f"data:image/png;base64,{base64.b64encode(state.engine.dendrogram_img.getvalue()).decode()}"


def full_context(request):
    ctx = {"request": request, "state": state, "saved_clusters": get_saved_clusters()}
    ctx.update(wall_context())
    ctx["dendrogram_src"] = dendrogram_b64()
    ctx["playlists"] = state.engine.playlists
    ctx["selected_playlist"] = state.selected_playlist
    ctx["playlist_range"] = state.playlist_range
    return ctx


def wall_response(request):
    return templates.TemplateResponse("partials/video_wall.html", {"request": request, **wall_context()})


@app.on_event("startup")
def startup():
    build_engine()


@app.post("/reset", response_class=HTMLResponse)
def reset(request: Request):
    global state
    state = AppState()
    build_engine()
    return templates.TemplateResponse("index.html", full_context(request))


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", full_context(request))


@app.post("/update-num-of-groups", response_class=HTMLResponse)
def update_num_of_groups(request: Request, num_of_groups: int = Form(...)):
    state.num_of_groups = num_of_groups
    state.engine.tree_climber.num_of_groups = num_of_groups
    state.engine.tree_climber.children, state.engine.tree_climber.grandchildren = \
        state.engine.tree_climber.new_offspring(state.engine.tree_climber.tree)
    return wall_response(request)


@app.post("/update-videos-in-group", response_class=HTMLResponse)
def update_videos_in_group(request: Request, videos_in_group: int = Form(...)):
    state.videos_in_group = videos_in_group
    state.engine.tree_climber.videos_in_group = videos_in_group
    state.engine.tree_climber.children, state.engine.tree_climber.grandchildren = \
        state.engine.tree_climber.new_offspring(state.engine.tree_climber.tree)
    return wall_response(request)


@app.post("/update-column-width", response_class=HTMLResponse)
def update_column_width(request: Request, column_width: int = Form(...)):
    state.column_width = column_width
    return wall_response(request)


@app.post("/update-rank-playlist", response_class=HTMLResponse)
def update_rank_playlist(request: Request, rank_playlist: str = Form(...)):
    state.selected_playlist = rank_playlist
    state.engine.recompute_ranks(state.selected_playlist, *state.playlist_range)
    return wall_response(request)


@app.post("/update-playlist-range", response_class=HTMLResponse)
def update_playlist_range(request: Request, range_start: float = Form(...), range_end: float = Form(...)):
    state.playlist_range = (range_start, range_end)
    state.engine.recompute_ranks(state.selected_playlist, *state.playlist_range)
    return wall_response(request)


@app.get("/title/{video_id}", response_class=HTMLResponse)
def title(video_id: str):
    # return cached title if available
    title = state.engine.get_video_title(video_id) if state.engine else ""
    if not title:
        try:
            title = get_title_oembed(video_id)
            if state.engine:
                state.engine.G.nodes[video_id]["title"] = title
        except Exception:
            title = ""
    return HTMLResponse(title)


@app.post("/choose-column/{i}", response_class=HTMLResponse)
def choose_column(request: Request, i: int):
    exit_code = state.engine.choose_column(i)
    if exit_code == -1:
        state.message = "already on the lowest cluster"
    else:
        state.message = state.engine.get_branch_id()
    return wall_response(request)


@app.post("/go-back", response_class=HTMLResponse)
def go_back(request: Request):
    exit_code = state.engine.go_back()
    if exit_code == -1:
        state.message = "already on the highest cluster"
    else:
        state.message = state.engine.get_branch_id()
    return wall_response(request)


@app.post("/update-exploration", response_class=HTMLResponse)
def update_exploration(request: Request, exploration: float = Form(...)):
    state.exploration = exploration
    return wall_response(request)


@app.post("/save-cluster", response_class=HTMLResponse)
def save_cluster(request: Request, cluster_name: str = Form("")):
    msg = state.engine.save_current_cluster(cluster_name)
    state.message = msg
    ctx = {"request": request, **wall_context(), "saved_clusters": get_saved_clusters()}
    return templates.TemplateResponse("partials/video_wall.html", ctx)


@app.post("/load-cluster", response_class=HTMLResponse)
def load_cluster(request: Request, saved_cluster: str = Form(...)):
    state.engine.load_cluster(saved_cluster)
    state.message = f"loaded cluster: {saved_cluster}"
    return wall_response(request)

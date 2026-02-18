import base64
import io
import logging
import random
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

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
    seed: int = field(default_factory=lambda: random.randint(1, 9999))
    clustering_balance_a: float = 1.7
    num_of_groups: int = 3
    videos_in_group: int = 5
    show_dendrogram: bool = False
    column_width: int = 390


state = AppState()


def build_engine():
    if state.seed < 1 or state.seed > 9999:
        state.seed = random.randint(1, 9999)

    params = SimpleNamespace(
        seed=state.seed,
        clustering_balance_a=state.clustering_balance_a,
        num_of_groups=state.num_of_groups,
        videos_in_group=state.videos_in_group,
    )

    state.engine = Engine(params)

    if len(state.engine.G.nodes) == 0:
        state.engine = None
        state.message = "Nothing to show :("
    else:
        state.message = ""


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
    if not state.show_dendrogram or not state.engine or not state.engine.dendrogram_img:
        return None
    buf = io.BytesIO()
    state.engine.dendrogram_img.savefig(buf, format="png", bbox_inches="tight")
    return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"


def full_context(request):
    ctx = {"request": request, "state": state, "saved_clusters": get_saved_clusters()}
    ctx.update(wall_context())
    ctx["dendrogram_src"] = dendrogram_b64()
    return ctx


def wall_response(request):
    return templates.TemplateResponse("partials/video_wall.html", {"request": request, **wall_context()})


@app.on_event("startup")
def startup():
    build_engine()


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", full_context(request))


@app.post("/refresh-engine", response_class=HTMLResponse)
def refresh_engine(
    request: Request,
    seed: int = Form(...),
    clustering_balance_a: float = Form(...),
    num_of_groups: int = Form(...),
    videos_in_group: int = Form(...),
    show_dendrogram: bool = Form(False),
    column_width: int = Form(...),
):
    state.seed = seed
    state.clustering_balance_a = clustering_balance_a
    state.num_of_groups = num_of_groups
    state.videos_in_group = videos_in_group
    state.show_dendrogram = show_dendrogram
    state.column_width = column_width
    build_engine()
    return templates.TemplateResponse("index.html", full_context(request))


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
    return wall_response(request)


@app.post("/load-cluster", response_class=HTMLResponse)
def load_cluster(request: Request, saved_cluster: str = Form(...)):
    state.engine.load_cluster(saved_cluster)
    state.message = f"loaded cluster: {saved_cluster}"
    return wall_response(request)

import os
import pathlib
import subprocess
from pathlib import Path

from yourtube.file_operations import (
    clustering_cache_template,
    saved_clusters_template,
    takeouts_template,
)
from yourtube.json_db import ensure_directories

__version__ = "0.7.0"


dir_ = pathlib.Path(__file__).parent.resolve()
app_path = os.path.join(dir_, "YourTube.py")


def run():
    # TODO once poetry-core 1.1.0 drops, this could be made more elegantly, directly with a bash script
    subprocess.run(["panel", "serve", "--show", "--port=8866", app_path])
    # "--autoreload",
    # if this command cannot import yourtube, setting PYTHONPATH is needed
    # https://stackoverflow.com/questions/37275033/running-export-command-with-pythons-subprocess-does-not-work


def install():
    print("\n\nCreating necessary paths...")
    Path(clustering_cache_template).parent.mkdir(parents=True, exist_ok=True)
    Path(saved_clusters_template).parent.parent.mkdir(parents=True, exist_ok=True)
    Path(takeouts_template).parent.mkdir(parents=True, exist_ok=True)

    print("\n\nSetting up database...")
    ensure_directories()

    print("\n\nInstalled successfully")

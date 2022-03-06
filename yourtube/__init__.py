import os
import pathlib
import subprocess
from pathlib import Path

from neo4j import GraphDatabase

from yourtube.neo4j_queries import create_constraints
from yourtube.file_operations import graph_path_template, clustering_cache_template, saved_clusters_template

__version__ = "0.7.0"


dir_ = pathlib.Path(__file__).parent.resolve()
app_path = os.path.join(dir_, "YourTube.py")
installer_path = os.path.join(dir_, "install.sh")


def run():
    # TODO once poetry-core 1.1.0 drops, this could be made more elegantly, directly with a bash script
    subprocess.run(["panel", "serve", "--show", "--port=8866", app_path])
    # "--autoreload",
    # if this command cannot import yourtube, setting PYTHONPATH is needed
    # https://stackoverflow.com/questions/37275033/running-export-command-with-pythons-subprocess-does-not-work


def install():
    print("\n\nCreating necessary paths...")
    Path(graph_path_template).parent.mkdir(parents=True, exist_ok=True) # equivalent of mkdir -p
    Path(clustering_cache_template).parent.mkdir(parents=True, exist_ok=True)
    Path(saved_clusters_template).parent.parent.mkdir(parents=True, exist_ok=True)

    print("\n\nSetting up database...")
    driver = GraphDatabase.driver("neo4j://neo4j:7687", auth=("neo4j", "yourtube"))
    # this creates neeeded constraints (which by the way sets up indexes)
    with driver.session() as s:
        s.write_transaction(create_constraints)

    print("\n\nInstalled successfully")

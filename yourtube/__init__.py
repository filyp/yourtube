__version__ = "0.7.0"

import os
import pathlib
import subprocess

from neo4j import GraphDatabase

from yourtube.neo4j_queries import create_constraints

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
    # TODO once poetry-core 1.1.0 drops, this could be made more elegantly, directly with a bash script
    subprocess.run(["bash", installer_path])

    print("\n\nSet up database")
    driver = GraphDatabase.driver("neo4j://localhost:7687", auth=("neo4j", "yourtube"))
    # this creates neeeded constraints (which by the way sets up indexes)
    with driver.session() as s:
        s.write_transaction(create_constraints)

    print("\n\nInstalled successfully")

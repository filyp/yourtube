__version__ = "0.6.0"

import os
import subprocess
import pathlib

dir_ = pathlib.Path(__file__).parent.resolve()
app_path = os.path.join(dir_, "YourTube.ipynb")


def run():
    # TODO once poetry-core 1.1.0 drops, this could be made more elegantly, directly with a bash script
    # or maybe directly calling voila?
    subprocess.run(["voila", "--theme=dark", app_path])

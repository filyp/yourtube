__version__ = "0.2.0"

import shlex
import subprocess
import pathlib

dir_ = pathlib.Path(__file__).parent.resolve()


def run():
    # TODO once poetry-core 1.1.0 drops, this could be made more elegantly, directly with a bash script
    # or maybe directly calling voila?
    cmd = f"voila --theme=dark {dir_}/UI.ipynb"
    subprocess.run(shlex.split(cmd))

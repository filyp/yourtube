__version__ = "0.1.4"

import shlex
import subprocess
import pathlib

dir = pathlib.Path(__file__).parent.resolve()


def run():
    # TODO once poetry-core 1.1.0 drops, this could be made more elegantly, directly with a bash script
    # or maybe directly calling voila?
    cmd = f"voila --theme=dark {dir}/YourTube.ipynb"
    subprocess.run(shlex.split(cmd))

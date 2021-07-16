import shlex
import subprocess
import pathlib

dir = pathlib.Path(__file__).parent.resolve()


def run():
    cmd = f"voila --theme=dark {dir}/YourTube.ipynb"
    subprocess.run(shlex.split(cmd))

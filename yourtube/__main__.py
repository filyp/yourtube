import shlex
import subprocess


def run():
    cmd = "voila --theme=dark yourtube/YourTube.ipynb"
    subprocess.run(shlex.split(cmd))

# Installation

## Install OpenJDK11

For example on macOS:
```
brew install openjdk11
```
Or on Ubuntu:
```
sudo apt install openjdk-11-jdk
```

## Install YourTube

```bash
pip3 install poetry
git clone git@github.com:filyp/YourTube.git
cd yourtube
poetry install
poetry run yourtube-install
```

## Export YouTube data and scrape it

Then, follow instructions from README to export youtube data, and run:
```
poetry run yourtube-scrape
poetry run yourtube-scrape-watched
```

Now, run yourtube with:
```bash
poetry run yourtube
```


# Useful info
[performance tips for panel apps](https://awesome-panel.readthedocs.io/en/latest/performance.html)
[awesome-panel](https://github.com/marcskovmadsen/awesome-panel)
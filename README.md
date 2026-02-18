# YourTube

![build](https://github.com/filyp/YourTube/actions/workflows/build.yml/badge.svg)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)


Better youtube recommendations

- [x] More autonomy when choosing what to watch
- [x] Very customizable
- [x] Recommendations for two or more people
- [x] You can install it locally for completely private recommendations
- [x] Sharing and browsing information bubbles
- [ ] Less clickbait

# FAQ

<details>
  <summary>How does it work?</summary>

- For every video you have liked on youtube, its recommended videos are collected.
- This way, we create a graph, where two videos are connected if one recomends the other.
- Now we divide this graph into clusters (groups of videos around common theme). For example we can have a  `folk rock` cluster, or a `science podcasts` cluster or a `travel vlogs` cluster.
- Small clusters are a part of larger clusters. For example `folk rock` and `boomer rock` are inside of `rock` cluster, and `rock` is inside `music`.
- This forms a tree, with big branches (like `music`), splitting into smaller and smaller branches and twigs.
- Now, to choose what to watch you can start at the trunk, and "climb" this tree, by choosing which branch to go into.
- Note, that some clusters are too big to be clearly labeled, but by looking at the videos in them, you can usually get a general idea about this cluster's theme.
</details>

<details>
  <summary>How are the clusters found?</summary>

- When a group of videos is densely connected, it's assumed do be a cluster. When two clusters are well connected, they are joined into a bigger cluster. The exact method we use is [here](https://github.com/filyp/krakow).
</details>

<details>
  <summary>Why rely on youtube recommendations instead of providing our own and having more control over them?</summary>

- Creating a recommender system from scratch is much harder than you may think at first. In addition to having accurate recommendations, you also have to defend against attacks, like click farms trying to boost some content, or intelligence agencies spreading misinformation. You also have to detect illegal or NSFL stuff, and filter it out. See [this](https://www.youtube.com/watch?v=1PGm8LslEb4) to get a sense of how hard this is.
- Another critical problem is the network effect. To build a good recommender system, we need data from a lot of users. To have a lot of users, we need a good recommender system.
- For these reasons, it's better to start with an existing recomender system as a "bottom layer", and then build any new features we want, on top of it.
</details>

# Local installation

```bash
git clone https://github.com/filyp/yourtube.git
cd yourtube
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Fetch playlists

Fetch your liked and watch later playlists using yt-dlp (uses browser cookies for authentication):
```bash
.venv/bin/yourtube-fetch-playlists
.venv/bin/yourtube-scrape
```

Playlist data will be saved to `~/.yourtube/playlists/`.

## Running

```bash
.venv/bin/yourtube
```

YourTube should be now available at: `http://localhost:8866/`

from time import time

import networkx as nx

from yourtube import __version__
from yourtube.scraping import get_content, get_title, Scraper

id_ = "dQw4w9WgXcQ"
G = nx.DiGraph()


def test_version():
    with open("pyproject.toml") as file:
        lines = file.readlines()
    for line in lines:
        if "version = " in line:
            version = line.replace("version = ", "")
            version = version.replace('"', "")
            version = version.replace("\n", "")
            break
    assert __version__ == version


def test_scraping():
    with Scraper(driver=None, G=G) as scraper:
        scraper.scrape_from_list([id_], non_verbose=True)


def test_scraping_title():
    assert G.nodes[id_]["title"] == "Rick Astley - Never Gonna Give You Up (Official Music Video)"


def test_scraping_view_count():
    assert G.nodes[id_]["view_count"] > 1001659175


def test_scraping_like_count():
    assert G.nodes[id_]["like_count"] > 10792474


def test_scraping_channel_id():
    assert G.nodes[id_]["channel_id"] == "UCuAXFkgsw1L7xaCfnd5JJOw"


def test_scraping_time_scraped():
    assert time() - 3600 < G.nodes[id_]["time_scraped"] < time()


def test_scraping_category():
    assert G.nodes[id_]["category"] == "Music"


def test_scraping_length():
    assert G.nodes[id_]["length"] == 212


def test_scraping_keywords():
    assert set(G.nodes[id_]["keywords"]).issuperset([
        "rick astley",
        "Never Gonna Give You Up",
        "nggyu",
        "never gonna give you up lyrics",
        "rick rolled",
    ])


def test_title_special_chars():
    content, id_ = get_content("gmxSGVQEXuc")
    title = get_title(content)
    assert title == """test"&ŒœŠšŸˆ˜   –—‘’‚“”„†‡‰‹›€~!@#$%^&*()_+[]{};'\\:"|,./?"""

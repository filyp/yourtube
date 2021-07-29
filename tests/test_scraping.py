import networkx as nx
from time import time

from yourtube.scraping import scrape_from_list

id_ = "dQw4w9WgXcQ"
G = nx.DiGraph()


def test_scraping():
    scrape_from_list([id_], G, non_verbose=True)


def test_scraping_title():
    assert (
        G.nodes[id_]["title"]
        == "Rick Astley - Never Gonna Give You Up (Official Music Video)"
    )


def test_scraping_view_count():
    assert G.nodes[id_]["view_count"] > 1001659175


def test_scraping_like_count():
    assert G.nodes[id_]["like_count"] > 10792474


def test_scraping_channel_id():
    assert G.nodes[id_]["channel_id"] == "UCuAXFkgsw1L7xaCfnd5JJOw"


def test_scraping_time_scraped():
    assert time() - 3600 < G.nodes[id_]["time_scraped"] < time()

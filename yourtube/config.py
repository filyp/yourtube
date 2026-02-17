import os
from dataclasses import dataclass


seconds_in_day = 60 * 60 * 24


@dataclass
class Config:
    # videos saved in youtube earlier than this will be ignored
    scrape_playlist_items_from_last_n_years = 3

    # when scraping periodically, skip videos which have been already scraped recently
    periodic_scraping_skip_if_fresher_than = seconds_in_day * 7

    # path to the JSON file database
    json_db_path = os.path.expanduser("~/.yourtube/json_db")


@dataclass
class Msgs:
    trying_to_load_empty_graph = """
        #### There's nothing to show to you :(
        Either we didn't scrape your videos yet, or your playlists were empty.
    """

from dataclasses import dataclass


seconds_in_day = 60 * 60 * 24


@dataclass
class Config:
    # videos saved in youtube earlier than this will be ignored
    scrape_playlist_items_from_last_n_years = 3

    # when scraping periodically, skip videos which have been already scraped recently
    periodic_scraping_skip_if_fresher_than = seconds_in_day * 7

    # to improve graph loading times, keep a cache of the graph loaded from neo4j, for this time:
    graph_cache_time = seconds_in_day * 3

    # password to the neo4j database
    neo4j_password = "yourtube"

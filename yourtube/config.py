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


@dataclass
class Msgs:
    user_doesnt_exist = """
        #### Username "{}" doesn't exist
        To create a new user, type your username and upload your youtube takeout.
    """
    user_created = """
        #### Created new user successfully!
        You should be able to use the app tomorrow, after your videos get scraped.\n
        Thanks for your patience!
    """
    user_creation_failed = """
        #### Failed to create a new user
        The file you uploaded doesn't seem to be a valid youtube takeout.
    """
    trying_to_load_empty_graph = """
        #### There's nothing to show to you :(
        Either we didn't scrape your videos yet, or your yourtube takeout was empty.
    """
    user_already_exists = """
        #### There already exists a user with this name
        Try a different username.
    """

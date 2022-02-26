import logging
import re
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed, CancelledError
from time import time

import numpy as np
import requests
from neo4j import GraphDatabase
from tqdm import tqdm
from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    YouTubeTranscriptApi,
)

from yourtube.file_operations import (
    get_playlist_names,
    get_transcripts_db,
    get_youtube_playlist_ids,
    get_youtube_watched_ids,
    id_to_url,
)
from yourtube.neo4j_queries import *

seconds_in_day = 60 * 60 * 24
seconds_in_month = seconds_in_day * 30.4


def get_content(id_):
    url = id_to_url.format(id_)
    content = requests.get(url, cookies={"CONSENT": "YES+1"}, timeout=60)
    return content


def get_transript(id_):
    try:
        return YouTubeTranscriptApi.get_transcript(id_)
    except (TranscriptsDisabled, NoTranscriptFound):
        return None


def get_recommended_ids(content, id_):
    all_urls = re.findall(r"watch\?v=(.{11})", content.text)
    recs = list(set(all_urls))
    if id_ in recs:
        recs.remove(id_)
    return recs


def get_title(content):
    text = content.text.replace("\n", " ")
    candidates = re.findall(r"<title>(.*?) - YouTube</title>", text)
    assert len(candidates) == 1
    title = candidates[0]

    # make title human readable
    title = title.replace("&#39;", "'")
    title = title.replace("&amp;", "&")
    title = title.replace("&quot;", '"')
    return title


def get_view_count(content):
    candidates = re.findall(r'"viewCount":"([0-9]+)"', content.text)
    candidates = set(candidates)
    assert 1 <= len(candidates) <= 2
    if len(candidates) == 2:
        # premium videos list 2 different video versions
        return None
    view_count = candidates.pop()
    return int(view_count)


def get_like_count(content):
    candidates = re.findall(
        r'{"iconType":"LIKE"},"defaultText":{"accessibility":{"accessibilityData":{"label":"(.*?)"',
        content.text,
    )
    candidates = set(candidates)
    assert len(candidates) <= 1
    if candidates:
        like_string = candidates.pop()
    else:
        # likes are probably disabled
        return None
    like_string = like_string.replace("\xa0", "")
    like_string = like_string.replace(",", "")
    like_count = re.findall(r"[0-9]+", like_string)
    if like_count == []:
        # there are no likes
        return 0
    return int(like_count[0])


def get_channel_id(content):
    candidates = re.findall(
        r'"subscribeCommand":{"clickTrackingParams":".*?","commandMetadata":{"webCommandMetadata":{"sendPost":true,"apiUrl":"/youtubei/v1/subscription/subscribe"}},"subscribeEndpoint":{"channelIds":\["(.*?)"\]',
        content.text,
    )
    candidates = set(candidates)
    assert len(candidates) <= 1
    channel_id = candidates.pop() if candidates else None
    # no candidates probably means that the video is unavailable
    return channel_id


def get_category(content):
    candidates = re.findall(r'"category":"(.*?)"', content.text)
    candidates = set(candidates)
    assert 1 <= len(candidates) <= 2
    if len(candidates) == 2:
        assert candidates == {"Trailers", "Movies"}
        # youtube movies have these two categories, so just say it's a movie
        return "Movies"
    category = candidates.pop()
    category = category.replace("\\u0026", "&")
    return category


def get_length(content):
    candidates = re.findall(r'"videoDetails":.*?"lengthSeconds":"(.*?)"', content.text)
    candidates = set(candidates)
    assert 1 <= len(candidates) <= 2
    if len(candidates) == 2:
        # premium videos list 2 different lengths
        return None
    length = candidates.pop()
    return int(length)


def get_keywords(content):
    candidates = re.findall(r'"keywords":\[(.*?)\]', content.text)
    candidates = set(candidates)
    assert len(candidates) <= 1
    if len(candidates) == 0:
        # there are no keywords
        return []
    keywords = candidates.pop()
    keywords = keywords.replace('"', "")
    keywords = keywords.split(",")
    return keywords


def scrape_content(content, id_, G=None, driver=None):
    """
    if driver is not None, save the content into neo4j
    if G is not None, in addition to saving to neo4j, also update G
    """

    recs = get_recommended_ids(content, id_)
    if len(recs) <= 1:
        # this video is probably removed from youtube
        if driver is not None:
            with driver.session() as s:
                s.write_transaction(mark_video_as_down, id_)
        if G is not None:
            G.add_node(id_)
            G.nodes[id_]["is_down"] = True
        return

    video_info = dict()
    video_info["video_id"] = id_
    try:
        video_info["title"] = get_title(content)
        video_info["view_count"] = get_view_count(content)
        video_info["like_count"] = get_like_count(content)
        video_info["channel_id"] = get_channel_id(content)
        video_info["category"] = get_category(content)
        video_info["length"] = get_length(content)
        video_info["keywords"] = get_keywords(content)
        video_info["time_scraped"] = time()
    except Exception:
        print("\n\nscraping failed for video: ", id_)
        raise

    if driver is not None:
        with driver.session() as s:
            s.write_transaction(update_video, recs, **video_info)
    if G is not None:
        logging.debug(f"adding node : {id_}")
        G.add_node(id_, **video_info)
        for rec in recs:
            G.add_edge(id_, rec)


def get_content_and_save(id_, G=None, driver=None):
    try:
        content = get_content(id_)
    except Exception as ex:
        # TODO will this even be displayed if it's inside a thread?
        print("failed to get content of a video: %s" % (ex))
        return
    scrape_content(content, id_, G, driver)

class Scraper:
    def __init__(self, driver=None, G=None):
        # this has to be ThreadPool not ProcessPool, because driver cannot be serialized by pickle
        self.executor = ThreadPoolExecutor(max_workers=8)
        self.driver = driver
        self.G = G
        # Either driver or G (or both) must be given.
        assert (driver is not None) or (G is not None)
        self.futures = set()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.executor.shutdown(wait=True)
        return False
    
    def choose_which_video_to_skip(self, ids, skip_if_fresher_than):
        ids_to_scrape = []
        for id_ in ids:
            if self.G is not None:
                # if G is given, use it to skip already scraped nodes
                if id_ in self.G.nodes:
                    node = self.G.nodes[id_]
                    # check if this video is down
                    if "is_down" in node and node["is_down"]:
                        continue
                    # check if this video was already scraped recently
                    if (
                        skip_if_fresher_than is not None
                        and "time_scraped" in node
                        and time() - node["time_scraped"] < skip_if_fresher_than
                    ):
                        continue
                # no reason to skip this video
                ids_to_scrape.append(id_)
            else:
                # if G is not given, use neo4j to decide what to skip
                with self.driver.session() as s:
                    result = s.read_transaction(check_if_this_video_was_scraped, id_)
                if result == []:
                    # it is not present in the database, so scrape
                    ids_to_scrape.append(id_)
                    continue
                time_scraped, is_down = result[0]
                if is_down:
                    # down videos should be skipped
                    continue
                if time_scraped is None:
                    # it is present in the database, but wasn't scraped yet
                    ids_to_scrape.append(id_)
                    continue
                if skip_if_fresher_than is None:
                    # don't skip any scraped videos
                    ids_to_scrape.append(id_)
                    continue
                if time() - time_scraped < skip_if_fresher_than:
                    # this video was already scraped recently, so skip
                    continue
                else:
                    # it was scraped, but long ago, so scrape it
                    ids_to_scrape.append(id_)
                    continue
        return ids_to_scrape

    def scrape_from_list(self, ids, skip_if_fresher_than=None, non_verbose=False, wait=True):
        """
        Scrapes videos from the ids list and adds them to neo4j database and/or networkx graph

        note that if wait=False, self.futures can eat up all the RAM if a very large list of ids is provided

        ids:
            can be multidimensional, as long as it is convertible to numpy array
            it can contain "" elements - they will be skipped
        skip_if_fresher_than:
            is in seconds
            if set, videos scraped more recently than this time will be skipped

        wait:
            if set as True, it will block until all the videos get scraped
            otherwise, it will just submit them to get scraped in the background

        """
        # flatten
        ids = np.array(ids).flatten()
        # remove "" elements (they represent empty clusters)
        ids = [id_ for id_ in ids if id_ != ""]
        ids_to_scrape = self.choose_which_video_to_skip(ids, skip_if_fresher_than)

        if not non_verbose:
            print(f"skipped {len(ids) - len(ids_to_scrape)} videos")
        
        self.futures = set()
        for id_ in ids_to_scrape:
            future = self.executor.submit(get_content_and_save, id_, self.G, self.driver)
            self.futures.add(future)
            # print(id_)

        if wait:
            for future in tqdm(
                as_completed(self.futures),
                total=len(ids_to_scrape),
                ncols=80,
                smoothing=0.05,
                disable=non_verbose,
            ):
                try:
                    res = future.result()
                    # print(future)
                except CancelledError:
                    pass

                # delete this entry, to prevent this list from eating all the RAM
                try:
                    self.futures.remove(future)
                except KeyError:
                    pass
    
    def cancel_all_tasks(self):
        # it is a copy, because self.futures can be changexd by other thread while this loop runs
        for future in self.futures.copy():
            future.cancel()
            # print("cancelled: ", future)
        self.futures = set()


def only_added_in_last_n_years(ids_to_add, times_added, n=5):
    seconds_in_year = 60 * 60 * 24 * 365
    start_time = time() - seconds_in_year * n

    filtered_pairs = []
    for id_to_add, time_added in zip(ids_to_add, times_added):
        if start_time < time_added:
            filtered_pairs.append((id_to_add, time_added))

    if filtered_pairs == []:
        return [], []

    filtered_ids_to_add, filtered_times_to_add = zip(*filtered_pairs)
    return filtered_ids_to_add, filtered_times_to_add


def scrape_playlist(
    username, playlist_name, driver, years=5, skip_if_fresher_than=seconds_in_month
):
    ids_to_add, times_added = get_youtube_playlist_ids(playlist_name)
    ids_to_add, times_added = only_added_in_last_n_years(ids_to_add, times_added, n=years)

    with Scraper(driver=driver, G=None) as scraper:
        scraper.scrape_from_list(ids_to_add, skip_if_fresher_than=skip_if_fresher_than)

    with driver.session() as s:
        # ensure that this playlist exists in database
        s.write_transaction(ensure_playlist_exists, username, playlist_name)
        # add data about the time they were added and from which playlist and user
        for video_id, time_added in zip(ids_to_add, times_added):
            s.write_transaction(
                add_info_that_video_is_in_playlist, username, playlist_name, video_id, time_added
            )


#######################################################################################
# exposed functions:


def scrape_all_playlists(username="default", years=5):
    driver = GraphDatabase.driver("neo4j://localhost:7687", auth=("neo4j", "yourtube"))

    for playlist_name in get_playlist_names():
        print()
        print("scraping: ", playlist_name)
        scrape_playlist(
            username, playlist_name, driver, years=years, skip_if_fresher_than=seconds_in_day
        )


def scrape_watched():
    driver = GraphDatabase.driver("neo4j://localhost:7687", auth=("neo4j", "yourtube"))

    id_to_watched_times = get_youtube_watched_ids()
    # note: it looks that in watched videos, there are only stored watches from the last 5 years

    ids_to_add = list(id_to_watched_times.keys())
    with Scraper(driver=driver, G=None) as scraper:
        scraper.scrape_from_list(ids_to_add, skip_if_fresher_than=seconds_in_month)

    # add data about the time they were added
    # assumes that the videos already exist in the DB (they were added in the previous step)
    # todo? this should be mandatory, even if we aren't scraping all the watched
    with driver.session() as s:
        for video_id, watched_times in id_to_watched_times.items():
            s.write_transaction(add_watched_times, video_id, watched_times)


def scrape_transcripts_from_watched_videos():
    # note that already scraped videos won't be skipped
    # as is the case with other scraping functions
    # also no saving db in case of some failure
    id_to_watched_times = get_youtube_watched_ids()
    # note: it looks that in watched videos, there are only stored watches from the last 5 years
    ids = id_to_watched_times.keys()

    transcripts_db = get_transcripts_db()

    with ProcessPoolExecutor(max_workers=8) as executor:
        future_to_id = {executor.submit(get_transript, id_): id_ for id_ in ids}
        for future in tqdm(
            as_completed(future_to_id),
            total=len(ids),
            ncols=80,
            smoothing=0.05,
        ):
            id_ = future_to_id[future]
            try:
                transcript = future.result()
            except Exception as ex:
                print("thread generated an exception: %s" % (ex))
                continue
            transcripts_db[id_] = transcript

            # delete this dict entry, to prevent this dict from eating all the RAM
            del future_to_id[future]

    transcripts_db.dump()

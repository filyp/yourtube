import logging
import re
from concurrent.futures import (
    CancelledError,
    ProcessPoolExecutor,
    as_completed,
)
from time import time

import numpy as np
import requests
from tqdm import tqdm
# from youtube_transcript_api import (
#     NoTranscriptFound,
#     TranscriptsDisabled,
#     YouTubeTranscriptApi,
# )

from yourtube.json_db import (
    check_if_this_video_was_scraped,
    get_playlist_video_ids,
    update_video,
)

logger = logging.getLogger("yourtube")


def get_content(id_):
    url = f"https://www.youtube.com/watch?v={id_}"
    content = requests.get(url, cookies={"CONSENT": "YES+1"}, timeout=60)
    return content, id_


def get_recommended_ids(content, id_):
    all_urls = re.findall(r"watch\?v=(.{11})", content.text)
    recs = list(set(all_urls))
    if id_ in recs:
        recs.remove(id_)
    return recs


def scrape_content(content, id_, G=None):
    """
    if G is not None, also update the in-memory graph G
    """
    recs = get_recommended_ids(content, id_)
    if len(recs) <= 1:
        # this video is probably removed from youtube
        update_video(id_, [], time(), is_down=True)
        if G is not None:
            G.add_node(id_)
            G.nodes[id_]["is_down"] = True
        return

    update_video(id_, recs, time())
    if G is not None:
        logging.debug(f"adding node : {id_}")
        G.add_node(id_, time_scraped=time())
        for rec in recs:
            G.add_edge(id_, rec)


class Scraper:
    def __init__(self, G=None):
        self.executor = ProcessPoolExecutor(max_workers=8)
        self.G = G
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
                # if G is not given, use json_db to decide what to skip
                result = check_if_this_video_was_scraped(id_)
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

    def scrape_from_list(self, ids, skip_if_fresher_than=None, non_verbose=False):
        """
        Scrapes videos from the ids list and saves recommendations to ~/.yourtube/videos/

        ids:
            can be multidimensional, as long as it is convertible to numpy array
            it can contain "" elements - they will be skipped
        skip_if_fresher_than:
            is in seconds
            if set, videos scraped more recently than this time will be skipped
        """
        # flatten
        ids = np.array(ids).flatten()
        # remove "" elements (they represent empty clusters)
        ids = [id_ for id_ in ids if id_ != ""]
        ids_to_scrape = self.choose_which_video_to_skip(ids, skip_if_fresher_than)

        if not non_verbose:
            print(
                f"skipped {len(ids) - len(ids_to_scrape)} videos, to scrape {len(ids_to_scrape)}"
            )

        futures = set()
        for id_ in ids_to_scrape:
            future = self.executor.submit(get_content, id_)
            futures.add(future)
        self.futures = futures.copy()

        for future in tqdm(
            as_completed(futures),
            total=len(ids_to_scrape),
            ncols=80,
            smoothing=0.05,
            disable=non_verbose,
        ):
            try:
                content, id_ = future.result()
                scrape_content(content, id_, self.G)
            except CancelledError:
                pass
            except Exception as ex:
                print("failed to get content of a video: %s" % (ex))

            # delete this entry, to prevent this list from eating all the RAM
            futures.remove(future)
            try:
                self.futures.remove(future)
            except KeyError:
                # some other thread could have changed self.futures
                pass

    def cancel_all_tasks(self):
        # it is a copy, because self.futures can be changed by other thread while this loop runs
        for future in self.futures.copy():
            future.cancel()


def scrape_recommendations(skip_if_fresher_than=60 * 60 * 24 * 7):
    """Scrape recommendations for all videos found in playlist JSONs."""
    video_ids = get_playlist_video_ids()
    print(f"Found {len(video_ids)} videos in playlists")

    with Scraper() as scraper:
        scraper.scrape_from_list(
            list(video_ids), skip_if_fresher_than=skip_if_fresher_than
        )

    print("\nSCRAPING FINISHED")


# def get_transript(id_):
#     try:
#         return YouTubeTranscriptApi.get_transcript(id_)
#     except (TranscriptsDisabled, NoTranscriptFound):
#         return None


# with ProcessPoolExecutor(max_workers=8) as executor:
#     future_to_id = {executor.submit(get_transript, id_): id_ for id_ in ids}
#     for future in tqdm(
#         as_completed(future_to_id),
#         total=len(ids),
#         ncols=80,
#         smoothing=0.05,
#     ):
#         id_ = future_to_id[future]
#         try:
#             transcript = future.result()
#         except Exception as ex:
#             print("thread generated an exception: %s" % (ex))
#             continue
#         transcripts_db[id_] = transcript

#         # delete this dict entry, to prevent this dict from eating all the RAM
#         del future_to_id[future]

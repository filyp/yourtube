import logging
import re
import time
from concurrent.futures import (
    CancelledError,
    ProcessPoolExecutor,
    as_completed,
)

import requests
from tqdm import tqdm

# from youtube_transcript_api import (
#     NoTranscriptFound,
#     TranscriptsDisabled,
#     YouTubeTranscriptApi,
# )
from yourtube.json_db import get_playlist_video_ids, read_video, update_video

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


def scrape_content(content, id_):
    """
    if G is not None, also update the in-memory graph G
    """
    recommendations = get_recommended_ids(content, id_)
    if len(recommendations) <= 1:
        # this video is probably removed from youtube
        update_video(id_, recommendations=[], is_down=True)
    else:
        update_video(id_, recommendations=recommendations)


def get_title_oembed(video_id):
    r = requests.get(
        f"https://www.youtube.com/oembed?url=https://youtube.com/watch?v={video_id}&format=json"
    )
    return r.json()["title"]


class Scraper:
    def __init__(self):
        self.executor = ProcessPoolExecutor(max_workers=8)
        self.futures = set()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.executor.shutdown(wait=True)
        return False

    def choose_which_video_to_skip(self, ids, skip_if_fresher_than=float("inf")):
        ids_to_scrape = []
        for id_ in ids:
            data = read_video(id_)
            if data is None:
                # it is not present in the database, so scrape
                ids_to_scrape.append(id_)
                continue
            if data.get("is_down", False):
                # down videos should be skipped
                continue

            if time.time() - data["time_scraped"] > skip_if_fresher_than:
                # it was scraped, but long ago, so scrape it
                ids_to_scrape.append(id_)

        return ids_to_scrape

    def scrape_from_list(self, ids, skip_if_fresher_than=float("inf")):
        """
        Scrapes videos from the ids list and saves recommendations to ~/.yourtube/videos/

        ids:
            iterable of video IDs
        skip_if_fresher_than:
            is in seconds
            if set, videos scraped more recently than this time will be skipped
        """
        ids_to_scrape = self.choose_which_video_to_skip(ids, skip_if_fresher_than)

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
        ):
            try:
                content, id_ = future.result()
                scrape_content(content, id_)
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


def scrape_recommendations(skip_if_fresher_than=60 * 60 * 24 * 3):
    """Scrape recommendations for all videos found in playlist JSONs."""
    video_ids = get_playlist_video_ids()
    print(f"Found {len(video_ids)} videos in playlists")

    with Scraper() as scraper:
        scraper.scrape_from_list(video_ids, skip_if_fresher_than=skip_if_fresher_than)

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

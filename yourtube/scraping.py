import re
import requests
from time import time
from tqdm import tqdm
from concurrent.futures import as_completed, ThreadPoolExecutor, ProcessPoolExecutor
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
)

from yourtube.file_operations import (
    save_graph,
    load_graph,
    id_to_url,
    get_playlist_names,
    get_youtube_playlist_ids,
    get_youtube_watched_ids,
    get_transcripts_db,
)

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
    assert len(candidates) == 1
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


def scrape_content(content, id_, G):
    recs = get_recommended_ids(content, id_)
    if not recs:
        # this video is probably removed from youtube
        # TODO maybe the node should be removed too
        G.add_node(id_)
        G.nodes[id_]["is_down"] = True
        return
    for rec in recs:
        G.add_edge(id_, rec)

    try:
        G.nodes[id_]["title"] = get_title(content)
        G.nodes[id_]["view_count"] = get_view_count(content)
        G.nodes[id_]["like_count"] = get_like_count(content)
        G.nodes[id_]["channel_id"] = get_channel_id(content)
        G.nodes[id_]["category"] = get_category(content)
        G.nodes[id_]["length"] = get_length(content)
        G.nodes[id_]["keywords"] = get_keywords(content)
        G.nodes[id_]["time_scraped"] = time()
    except Exception:
        print("\n\nscraping failed for video: ", id_)
        raise


def scrape_from_list(ids, G, skip_if_fresher_than=None, non_verbose=False):
    """
    Scrapes videos from the ids_to_add list and adds them to graph G

    skip_if_fresher_than is in seconds
    if set, videos scraped more recently than this time will be skipped
    """
    # decide which videos to skip
    ids_to_scrape = []
    for id_ in ids:
        if id_ in G.nodes:
            node = G.nodes[id_]
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
        ids_to_scrape.append(id_)

    if not non_verbose:
        print(f"skipped {len(ids) - len(ids_to_scrape)} videos")

    with ProcessPoolExecutor(max_workers=5) as executor:
        future_to_id = {executor.submit(get_content, id_): id_ for id_ in ids_to_scrape}
        for future in tqdm(
            as_completed(future_to_id),
            total=len(ids_to_scrape),
            ncols=80,
            smoothing=0.05,
            disable=non_verbose,
        ):
            id_ = future_to_id[future]
            try:
                content = future.result()
            except Exception as ex:
                print("thread generated an exception: %s" % (ex))
                continue
            scrape_content(content, id_, G)


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


def scrape_playlist(playlist_name, G, years=5, skip_if_fresher_than=seconds_in_month):
    ids_to_add, times_added = get_youtube_playlist_ids(playlist_name)
    ids_to_add, times_added = only_added_in_last_n_years(
        ids_to_add, times_added, n=years
    )

    scrape_from_list(ids_to_add, G, skip_if_fresher_than=skip_if_fresher_than)

    # add data about the time they were added
    for id_, time_added in zip(ids_to_add, times_added):
        if id_ in G:
            G.nodes[id_]["time_added"] = time_added
            G.nodes[id_]["from"] = playlist_name


# exposed functions:


def scrape_all_playlists(years=5):
    G = load_graph()

    try:
        for playlist_name in get_playlist_names():
            print()
            print("scraping: ", playlist_name)
            scrape_playlist(
                playlist_name, G, years=years, skip_if_fresher_than=seconds_in_day
            )
    except:
        save_graph(G)
        print("We crashed. Saving the graph...")
        raise

    save_graph(G)


def scrape_watched():
    G = load_graph()

    try:
        id_to_watched_times = get_youtube_watched_ids()
        # note: it looks that in watched videos, there are only stored watches from the last 5 years

        ids_to_add = id_to_watched_times.keys()
        scrape_from_list(ids_to_add, G, skip_if_fresher_than=seconds_in_month)

        # add data about the time they were added
        for id_, watched_times in id_to_watched_times.items():
            if id_ in G:
                G.nodes[id_]["watched_times"] = watched_times
    except:
        save_graph(G)
        print("We crashed. Saving the graph...")
        raise

    save_graph(G)


def scrape_transcripts_from_watched_videos():
    # note that already scraped videos won't be skipped
    # as is the case with other scraping functions
    # also no saving db in case of some failure
    id_to_watched_times = get_youtube_watched_ids()
    # note: it looks that in watched videos, there are only stored watches from the last 5 years
    ids = id_to_watched_times.keys()

    transcripts_db = get_transcripts_db()

    with ProcessPoolExecutor(max_workers=5) as executor:
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

    transcripts_db.dump()

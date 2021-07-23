import re
import requests
from time import time
from tqdm import tqdm


from yourtube.file_operations import (
    save_graph,
    load_graph,
    id_to_url,
    get_playlist_names,
    get_youtube_playlist_ids,
    get_youtube_watched_ids,
)

seconds_in_month = 60 * 60 * 24 * 30.4


def get_content(id_):
    url = id_to_url.format(id_)
    content = requests.get(url, cookies={"CONSENT": "YES+1"})
    return content


def get_recommended_ids(content, id_):
    all_urls = re.findall(r"watch\?v=(.{11})", content.text)
    recs = list(set(all_urls))
    if id_ in recs:
        recs.remove(id_)
    return recs


def get_title(content):
    candidates = re.findall(r'title="(.*?)"', content.text)
    candidates = set(candidates)
    if "YouTube" in candidates:
        candidates.remove("YouTube")
    assert len(candidates) == 1
    title = candidates.pop()
    return title


def get_view_count(content):
    candidates = re.findall(r'"viewCount":"([0-9]+)"', content.text)
    candidates = set(candidates)
    assert len(candidates) == 1
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
    like_count = re.findall(r"[0-9]+", like_string)[0]
    return int(like_count)


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


def scrape(id_, G):
    content = get_content(id_)
    recs = get_recommended_ids(content, id_)
    if not recs:
        # this video is probably removed from youtube
        return
    for rec in recs:
        G.add_edge(id_, rec)

    try:
        G.nodes[id_]["title"] = get_title(content)
        G.nodes[id_]["view_count"] = get_view_count(content)
        G.nodes[id_]["like_count"] = get_like_count(content)
        G.nodes[id_]["channel_id"] = get_channel_id(content)
        G.nodes[id_]["time_scraped"] = time()
    except:
        print("\n\nscraping failed for video: ", id_)
        raise


def scrape_from_list(ids_to_add, G, skip_if_fresher_than=None):
    """
    Scrapes videos from the ids_to_add list and adds them to graph G

    skip_if_fresher_than is in seconds
    if set, videos scraped earlier than this time will be skipped
    """
    print(f"adding {len(ids_to_add)} nodes")

    skipped = 0
    for id_ in tqdm(ids_to_add, ncols=80):
        # check if this video was already scraped recently
        if (
            skip_if_fresher_than is not None
            and id_ in G.nodes
            and "time_scraped" in G.nodes[id_]
            and time() - G.nodes[id_]["time_scraped"] < skip_if_fresher_than
        ):
            skipped += 1
            continue

        # TODO maybe omit videos where title is None
        # they are down but are tried do to be scraped every time
        scrape(id_, G)

    print(f"skipped {skipped} videos")


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


def scrape_playlist(playlist_name, G, years=5):
    ids_to_add, times_added = get_youtube_playlist_ids(playlist_name)
    ids_to_add, times_added = only_added_in_last_n_years(
        ids_to_add, times_added, n=years
    )

    scrape_from_list(ids_to_add, G, skip_if_fresher_than=seconds_in_month)

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
            scrape_playlist(playlist_name, G, years=years)
    except:
        save_graph(G)
        print("We crashed. Saving the graph...")
        raise

    save_graph(G)


def scrape_watched(years=5):
    G = load_graph()

    try:
        ids_to_add, watched_times = get_youtube_watched_ids()
        ids_to_add, watched_times = only_added_in_last_n_years(
            ids_to_add, watched_times, n=years
        )

        scrape_from_list(ids_to_add, G, skip_if_fresher_than=seconds_in_month)

        # add data about the time they were added
        for id_, watched_time in zip(ids_to_add, watched_times):
            if id_ in G:
                G.nodes[id_]["watched_time"] = watched_time
    except:
        save_graph(G)
        print("We crashed. Saving the graph...")
        raise

    save_graph(G)

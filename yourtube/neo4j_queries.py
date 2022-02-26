import inspect


# it's a decorator, that lets us define queries with no boilerplate code
# the docstring is the query
# see below for examples
# queries can be run like this::
# with driver.session() as session:
#     result = session.write_transaction(function_name, arg1, arg2, ...)
def query(func):
    query_string = func.__doc__
    signature = inspect.signature(func)
    params = list(signature.parameters)

    def inner(tx, *args):
        arg_dict = dict(zip(params, args))
        return tx.run(query_string, **arg_dict).values()

    return inner


"""
graph format:
    id:
        node identifier
        11 characters that identify video on youtube (can be found in URL)
        all the other fields can be absent if the video hasn't been scraped yet
    title:
        video title
    time_scraped:
        time when the video has been scraped
        in unix time
    time_added:
        time when the video has been added to a playlist
        in unix time
        "Watched videos" isn't treated as a playlist
        "Liked videos" is
    watched_times:
        list of times when the video has been watched, in unix time
        it is absent if the video hasn't been watched
    view_count:
        number of views on youtube
        can be None if the video is premium (so the views are ambiguous)
    like_count:
        number of likes on youtube
        can be None if likes are disabled
    channel_id:
        id of the channel of this video
        can be None if the video is unavailable
    category:
        category of the video
    length:
        video length in seconds
        can be None if the video is premium (so the views are ambiguous)
    keywords:
        keywords of the video as a list of strings
        can be an empty list if there are no keywords
    is_down:
        True if the video is unavailable
        can be absent if the video is up or hasn't been scraped


    clusters:
        ...
"""


# create a uniqueness constraint on video_id
@query
def create_constraints(tx):
    """
    CREATE CONSTRAINT ON (v:video) ASSERT v.video_id IS UNIQUE
    """
    # todo a uniqueness constraint on playlist could be added
    # for the pair (playlist_name, username)


def update_video(tx, recs, **video_info):
    # add all the video information
    tx.run(
        """
        MERGE (v:video {video_id: $video_id})
        SET v.title = $title
        SET v.view_count = $view_count
        SET v.like_count = $like_count
        SET v.channel_id = $channel_id
        SET v.category = $category
        SET v.length = $length
        SET v.keywords = $keywords
        SET v.time_scraped = $time_scraped
        SET v.is_down = false
        """,
        **video_info
    )

    # delete previous edges before adding new ones
    tx.run(
        """
        MATCH (v1:video {video_id: $video_id})-[r:RECOMMENDS]->(v2:video)
        DELETE r
        """
    )

    for rec in recs:
        # make sure all the recommended nodes are present in the DB
        tx.run(
            "MERGE (v:video {video_id: $rec})",
            rec=rec,
        )

        # create edges
        tx.run(
            """
            MATCH 
                (a:video {video_id: $video_id}), 
                (b:video {video_id: $rec})
            MERGE (a)-[:RECOMMENDS]->(b)
            """,
            video_id=video_info["video_id"],
            rec=rec,
        )


@query
def delete_all():
    """
    MATCH (v)
    DETACH DELETE v
    """


@query
def mark_video_as_down(video_id):
    """
    MERGE (v:video {video_id: $video_id})
    SET v.is_down = true
    """


@query
def ensure_playlist_exists(username, playlist_name):
    "MERGE (p:playlist {username: $username, playlist_name: $playlist_name})"


@query
def add_info_that_video_is_in_playlist(username, playlist_name, video_id, time_added):
    """
    MATCH
        (p:playlist {username: $username, playlist_name: $playlist_name}),
        (v:video {video_id: $video_id})
    MERGE (p)-[:HAS {time_added: $time_added}]->(v)
    """


# @query
# def get_user_relevant_edges(username):
#     """
#     MATCH (p:playlist {username: $username})-[:HAS]->(v1:video)-[:RECOMMENDS]->(v2:video)
#     RETURN v1.video_id, v2.video_id
#     """


@query
def get_all_user_relevant_video_info(username):
    """
    MATCH (p:playlist {username: $username})-[:HAS]->(v1:video)-[:RECOMMENDS]->(v2:video)
    RETURN v1, v2
    """


@query
def get_all_user_relevant_playlist_info(username):
    """
    MATCH (p:playlist {username: $username})-[r:HAS]->(v:video)
    RETURN p.playlist_name, v.video_id, r.time_added
    """


@query
def get_limited_user_relevant_video_info(username):
    """
    MATCH (p:playlist {username: $username})-[:HAS]->(v1:video)-[:RECOMMENDS]->(v2:video)
    RETURN v1.video_id, v1.title, v1.view_count, v1.like_count, v1.time_scraped, v1.is_down, v1.watched, v2.video_id, v2.title, v2.view_count, v2.like_count, v2.time_scraped, v2.is_down, v2.watched
    """


@query
def add_watched_times(video_id, watched_times):
    """
    MATCH (v:video {video_id: $video_id})
    SET v.watched_times = $watched_times
    SET v.watched = true
    """


@query
def check_if_this_video_was_scraped(video_id):
    """
    MATCH (v:video {video_id: $video_id})
    RETURN v.time_scraped, v.is_down
    """

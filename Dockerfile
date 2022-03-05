FROM python:3.10

WORKDIR /yourtube

RUN pip install --no-cache-dir poetry

COPY pyproject.toml .
COPY poetry.lock .

RUN poetry install

# RUN mkdir -p data/clustering_cache
# RUN mkdir -p data/graph_cache
# RUN mkdir -p data/saved_clusters

ENV PYTHONPATH "${PYTHONPATH}:/yourtube"

COPY yourtube yourtube

CMD [ "poetry", "run", "yourtube" ]
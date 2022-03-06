FROM python:3.10

WORKDIR /yourtube

RUN pip install --no-cache-dir poetry

COPY pyproject.toml .
COPY poetry.lock .

RUN poetry install

ENV PYTHONPATH "${PYTHONPATH}:/yourtube"

COPY yourtube yourtube

CMD [ "poetry", "run", "yourtube" ]
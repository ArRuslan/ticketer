FROM python:3.11-alpine

ENV POETRY_HOME=/opt/poetry
ENV POETRY_CACHE_DIR=/opt/.cache
ENV PATH="${PATH}:${POETRY_HOME}/bin"

WORKDIR "/ticketer"

COPY poetry.lock poetry.lock
COPY pyproject.toml pyproject.toml

# TODO: add libmagic when images will be added
RUN apk update && apk add --no-cache git bash && apk add --no-cache --virtual build-deps gcc libc-dev && \
    python -m venv $POETRY_HOME && $POETRY_HOME/bin/pip install -U pip setuptools && $POETRY_HOME/bin/pip install poetry && \
    poetry install --only main --no-interaction --no-root --no-dev && poetry add gunicorn && \
    apk del build-deps && \
    rm -rf /root/.cache $POETRY_CACHE_DIR/cache $POETRY_CACHE_DIR/artifacts

COPY . .
RUN chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
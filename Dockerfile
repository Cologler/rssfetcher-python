FROM python:3.12.11-alpine AS python-base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    POETRY_VIRTUALENVS_IN_PROJECT=true


FROM python-base AS poetry-base

WORKDIR /app

# setup poetry
RUN --mount=type=cache,target=/root/.cache \
    pip install --user poetry==2.1.1


FROM poetry-base

# install deps
COPY pyproject.toml poetry.lock ./
RUN --mount=type=cache,target=/root/.cache \
    python -m poetry install --sync

# copy src
COPY rssfetcher rssfetcher

# configure app
EXPOSE 8000

ENV RSSFETCHER_CONFIG=/etc/rssfetcher/config.yml
ENV UVICORN_HOST=0.0.0.0

VOLUME [ "/etc/rssfetcher", "/root/.local/state/rssfetcher" ]

# start
ENTRYPOINT [ "python", "-m", "poetry", "run" ]
CMD [ "fastapi", "run", "rssfetcher" ]

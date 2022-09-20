set dotenv-load

fetch:
    poetry run python -m rssfetcher

start:
    poetry run uvicorn rssfetcher:app

build:
    docker build . -t rssfetcher

pack:
    mkdir -p dist
    tar -cf dist/out.tar --exclude .git --exclude=.venv --exclude=dist --exclude=*.tar *

set dotenv-load

export-dependencies:
    poetry export --without-hashes > requirements.txt

fetch:
    poetry run python -m rssfetcher

start:
    poetry run uvicorn rssfetcher:app

test:
    poetry run python -m pytest

build: export-dependencies
    docker build . -t rssfetcher

pack-tar: export-dependencies
    mkdir -p dist
    tar -cf dist/out.tar --exclude=.* --exclude=dist --exclude=tests --exclude=*.tar *

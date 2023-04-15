set dotenv-load

fetch:
    poetry run python -m rssfetcher

start:
    poetry run uvicorn rssfetcher:app

test:
    poetry run python -m pytest

export-requirements:
    poetry export --without-hashes > requirements.txt

publish-docker-image: export-requirements
    mkdir -p dist
    docker build . --tag rssfetcher
    docker save --output dist/rssfetcher-image.tar rssfetcher

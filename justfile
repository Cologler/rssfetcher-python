set dotenv-load

fetch:
    poetry run python -m rssfetcher

start:
    poetry run uvicorn rssfetcher:app

test:
    poetry run python -m pytest

export-requirements:
    poetry export --without-hashes > requirements.txt

docker-build:
    docker build -t rssfetcher:$(date +%Y%m%d_%H%M%S) -t rssfetcher:dev .

docker-export-image: docker-build
    mkdir -p dist
    docker save --output dist/rssfetcher-image.tar rssfetcher:dev

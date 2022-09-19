start:
    poetry run uvicorn rssfetcher:main

build:
    docker build . -t rssfetcher

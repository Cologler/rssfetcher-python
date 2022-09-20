fetch:
    poetry run python -m rssfetcher.__init__

start:
    poetry run uvicorn rssfetcher:main

build:
    docker build . -t rssfetcher

pack:
    mkdir -p dist
    tar -cf dist/out.tar --exclude .git --exclude=.venv --exclude=dist --exclude=*.tar *

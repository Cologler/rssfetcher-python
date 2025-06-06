set dotenv-load

app_name := 'rssfetcher'

fetch:
    poetry run python -m rssfetcher

start:
    poetry run uvicorn rssfetcher:app

test:
    poetry run python -m pytest

export-requirements:
    poetry export --without-hashes > requirements.txt

docker-build:
    docker build -t {{app_name}}:$(date +%Y%m%d_%H%M%S) -t {{app_name}}:dev .

docker-export-image: docker-build
    mkdir -p dist
    docker save --output dist/{{app_name}}-image.tar {{app_name}}:dev
    zstd -f dist/{{app_name}}-image.tar -o dist/{{app_name}}-image.tar.zst
    rm dist/{{app_name}}-image.tar

docker-backup-image: docker-export-image
    cp dist/{{app_name}}-image.tar.zst "$OneDrive/Backups/app/docker/images/{{app_name}}/{{app_name}}_$(date +%Y%m%d_%H%M%S).tar.zst"

FROM python:3.12-alpine

WORKDIR /usr/src/app

COPY requirements.txt requirements.txt
COPY rssfetcher rssfetcher

RUN pip install --user -r requirements.txt
RUN mkdir -p ~/.local/state/rssfetcher

EXPOSE 8000

ENV RSSFETCHER_CONFIG=/etc/rssfetcher/config.yml
ENV UVICORN_HOST=0.0.0.0

VOLUME /etc/rssfetcher

CMD [ "python", "-m", "uvicorn", "rssfetcher:app" ]

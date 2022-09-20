FROM python:3.10.7

WORKDIR /usr/src/app

COPY . .

RUN mkdir -p ~/.local/state/rssfetcher
RUN pip install poetry
RUN poetry install

EXPOSE 8000

ENV RSSFETCHER_CONFIG=/etc/rssfetcher/config.yml
ENV UVICORN_HOST=0.0.0.0

VOLUME /etc/rssfetcher

CMD [ "poetry", "run", "uvicorn", "rssfetcher:app" ]

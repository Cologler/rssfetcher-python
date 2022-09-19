FROM python:3.10.7

WORKDIR /usr/src/app

COPY . .

RUN pip install poetry
RUN poetry install

EXPOSE 8000

ENV RSSFETCHER_CONFIG=/etc/rssfetcher/config.yml

VOLUME /etc/rssfetcher

CMD [ "poetry", "run", "uvicorn", "rssfetcher:app" ]

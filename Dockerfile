FROM python:3.10.7-alpine3.16

WORKDIR /usr/src/app

COPY requirements.txt /requirements.txt
RUN pip install --user -r /requirements.txt

COPY . .

RUN mkdir -p ~/.local/state/rssfetcher

EXPOSE 8000

ENV RSSFETCHER_CONFIG=/etc/rssfetcher/config.yml
ENV UVICORN_HOST=0.0.0.0

VOLUME /etc/rssfetcher

CMD [ "python", "-m", "uvicorn", "rssfetcher:app" ]

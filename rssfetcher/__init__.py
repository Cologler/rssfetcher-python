# -*- coding: utf-8 -*-
#
# Copyright (c) 2020~2999 - Cologler <skyoflw@gmail.com>
# ----------
# require packages:
#   - pyyaml
#   - requests
# ----------

from typing import *
import logging
import os
import sys
from contextlib import suppress
from collections import ChainMap
from time import monotonic, sleep
import queue
import threading

import yaml
import schedule
from fastapi import FastAPI
from pydantic import BaseSettings

from .core import get_logger, fetch_feed
from .cfg import ConfigHelper

def _fetch_feeds(conf: ConfigHelper, feeds: list):
    options = conf.conf_data.get('options', {})

    with conf.open_store() as store:
        # fetch from internet:
        fetched = []
        for feed_id, feed_section in feeds:
            try:
                items = fetch_feed(feed_id, feed_section)
            except Exception as error:
                get_logger().error('fetch %r failure with %s', feed_id, error, exc_info=True)
            else:
                for item in items:
                    fetched.append(tuple(item.get(x) for x in store.COLUMN_NAMES))

        # save:
        store.init_store()
        count = store.get_count()

        store.upsert(fetched)
        count = store.get_count() - count
        get_logger().info('total added %s rss', count)

        kept_count = options.get('kept_count')
        if isinstance(kept_count, int) and kept_count >= 10: # hard limit
            removed_count = store.remove_old_items(kept_count)
        else:
            removed_count = 0
        get_logger().info('removed outdated %r items.', removed_count)

        store.commit()


class RssFetcherWorker:
    def __init__(self, conf: ConfigHelper) -> None:
        self._conf = conf
        self._job_queue = queue.Queue()

    def start(self):
        job_queue = self._job_queue

        for feed_id, feed_section in self._conf.iter_feeds():
            job_args = (feed_id, feed_section)
            minutes = max(feed_section.get('interval', 15), 5)
            schedule.every(minutes).minutes.do(job_queue.put, job_args)
            job_queue.put(job_args)

        def run_on_background(func):
            threading.Thread(target=func, daemon=True).start()

        def filter_unique_feeds(feeds):
            s = set()
            for f in feeds:
                if f[0] not in s:
                    s.add(f[0])
                    yield f

        def get_feeds_in_10s():
            feeds = [job_queue.get()]
            start = monotonic()
            wait_time = 10
            while wait_time > 0:
                if feeds[-1] is None:
                    break
                try:
                    last = job_queue.get(timeout=wait_time)
                except queue.Empty:
                    break
                else:
                    feeds.append(last)
                wait_time = start + 10 - monotonic()
            return feeds

        @run_on_background
        def worker_main():
            while True:
                feeds = get_feeds_in_10s()
                try:
                    if None not in feeds:
                        unique_feeds = list(filter_unique_feeds(feeds))
                        get_logger().info('Receive %d fetch jobs.', len(unique_feeds))
                        assert unique_feeds
                        _fetch_feeds(self._conf, unique_feeds)
                finally:
                    for _ in range(len(feeds)):
                        job_queue.task_done()

        @run_on_background
        def schedule_main():
            try:
                while schedule.idle_seconds() is not None:
                    schedule.run_pending()
                    sleep(1)
            except KeyboardInterrupt:
                pass

        return job_queue

    def shutdown(self):
        self._job_queue.put(None)
        self._job_queue.join()


def configure_logger():
    logging_options = dict(
        format='%(asctime)s [%(levelname)s] - %(name)s: %(message)s',
        datefmt='%m/%d/%Y %I:%M:%S %p',
        level=logging.INFO
    )
    get_logger().setLevel(logging.INFO)
    logging.basicConfig(**logging_options)

class Settings(BaseSettings):
    config: str

    class Config:
        env_prefix = 'RSSFETCHER_'


def create_app(conf: ConfigHelper):

    app = FastAPI()

    worker = RssFetcherWorker(conf)
    app.on_event("startup")(worker.start)
    app.on_event("shutdown")(worker.shutdown)

    @app.get("/items/")
    async def get_items(start_rowid: int = 0, limit: int = None):
        limit_max = 1000
        limit = min(max(limit, 1), limit_max) if isinstance(limit, int) else limit_max

        with conf.open_store() as store:
            readed_items = store.read_items(start_rowid, limit + 1)
            return {
                'end': len(readed_items) <= limit,
                'items': readed_items[:limit],
            }

    @app.get("/items-count")
    async def get_items_count():
        with conf.open_store() as store:
            return {
                'count': store.get_count()
            }

    return app

def _load_settings(argv):
    settings = Settings()
    return settings

def _load_config(conf_path: str) -> dict:
    if os.path.isfile(conf_path):
        with suppress(FileNotFoundError):
            with open(conf_path, mode='r', encoding='utf8') as fp:
                data = yaml.safe_load(fp)
                get_logger().info('Load config from %s', conf_path)
                return data
        get_logger().error('Unable open file: %s', conf_path)
    else:
        get_logger().error('No such file: %s', conf_path)
    exit(1)

def _main_base(argv):
    configure_logger()
    settings = _load_settings(argv)
    conf_data = _load_config(settings.config)
    conf = ConfigHelper(conf_data)
    with conf.open_store() as store:
        store.init_store()
        store.commit()
    return conf

def fetch_once(argv):
    conf = _main_base(argv)
    _fetch_feeds(conf, list(conf.iter_feeds()))

def _get_app(argv):
    conf = _main_base(argv)
    return create_app(conf)

if __name__ == '__main__':
    exit(fetch_once(sys.argv[1:]) or 0)
else:
    app = _get_app(sys.argv[1:])

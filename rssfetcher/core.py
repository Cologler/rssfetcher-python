# -*- coding: utf-8 -*-
#
# Copyright (c) 2022~2999 - Cologler <skyoflw@gmail.com>
# ----------
#
# ----------

import logging
import os
import queue
import threading
import xml.etree.ElementTree as et
from contextlib import suppress
from functools import cache
from io import StringIO
from time import monotonic, sleep
from urllib.parse import urlparse

import requests
import schedule
from pydantic import ValidationError
from pydantic_settings import BaseSettings

from .cfg import ConfigHelper, FeedSection
from .models import RssItemRowRecord


@cache
def get_logger():
    return logging.getLogger('rssfetcher')

def dump_xml(el: et.Element):
    sb = StringIO()
    tr = et.ElementTree(el)
    tr.write(sb, encoding='unicode', short_empty_elements=False)
    return sb.getvalue()

def fetch_feed(feed_id: str, feed_section: FeedSection):
    collected_items: list[RssItemRowRecord] = []

    url = feed_section.get('url')
    if url and feed_section.get('enable', True):
        logger = get_logger().getChild(url)
        proxies = feed_section.get('proxies')
        if proxies is None:
            proxy = feed_section.get('proxy')
            if proxy:
                scheme = urlparse(proxy).scheme
                if not scheme:
                    scheme = urlparse(url).scheme or 'http'
                    proxy = scheme + '://' + proxy
                proxies = {}
                proxies[scheme] = proxy

        if proxies:
            logger.info('use proxies: %s', proxies)

        try:
            r = requests.get(url, proxies=proxies, timeout=(5, 60))
        except requests.ConnectionError as error:
            logger.error('raised %s: %s', type(error).__name__, error)
            return []

        try:
            r.raise_for_status()
        except requests.HTTPError as error:
            logger.error('raised %s: %s', type(error).__name__, error)
            return []

        r.encoding = 'utf8'
        try:
            body = r.text
        except (requests.ConnectionError, requests.Timeout) as error:
            logger.error('raised %s: %s', type(error).__name__, error)
        else:
            try:
                el = et.fromstring(body)
            except et.ParseError:
                logger.error('invalid xml.')
            else:
                def read_element_text(elements: list[et.Element | None] | et.Element | None):
                    if not isinstance(elements, list):
                        elements = [elements]
                    for el in elements:
                        if el is not None:
                            return el.text

                for item in el.iter('item'):
                    if unique_id := read_element_text([item.find('guid'), item.find('title')]):
                        rd: RssItemRowRecord = {
                            'feed_id': feed_id,
                            'rss_id': unique_id,
                            'title': read_element_text(item.find('title')),
                            'pub_date': read_element_text(item.find('pubDate')),
                            'raw': dump_xml(item)
                        }
                        if desc := item.find('description'):
                            rd['description'] = desc.text
                        collected_items.append(rd)
                    else:
                        logger.warning('item %r has no unique id', item)

                logger.info('total found %s items',len(collected_items))

    return collected_items

def fetch_feeds(conf: ConfigHelper, feeds: list):
    options = conf.conf_data.get('options', {})

    with conf.open_store() as store:
        # fetch from internet:
        fetched: list[RssItemRowRecord] = []
        for feed_id, feed_section in feeds:
            try:
                items = fetch_feed(feed_id, feed_section)
            except Exception as error:
                get_logger().error('fetch %r failure with %s', feed_id, error, exc_info=True)
            else:
                fetched.extend(items)

        if not fetched:
            return

        # save:
        count = store.get_count()

        store.upsert(fetched)
        count = store.get_count() - count
        get_logger().info('total added %s rss', count)

        kept_count = options.get('kept_count') if options else None
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
                        fetch_feeds(self._conf, unique_feeds)
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


class Settings(BaseSettings):
    config: str

    class Config:
        env_prefix = 'RSSFETCHER_'


def _main_base(argv):
    import yaml

    def configure_logger():
        logging.basicConfig(
            format='%(asctime)s [%(levelname)s] - %(name)s: %(message)s',
            datefmt='%m/%d/%Y %I:%M:%S %p',
            level=logging.INFO
        )
        get_logger().setLevel(logging.INFO)

    def _load_settings(argv):
        try:
            settings = Settings() # type: ignore
        except ValidationError as e:
            get_logger().error(e)
            exit()
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

    configure_logger()
    settings = _load_settings(argv)
    conf_data = _load_config(settings.config)
    conf = ConfigHelper(conf_data)
    with conf.open_store() as store:
        store.init_store()
        store.commit()
    return conf

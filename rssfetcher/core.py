# -*- coding: utf-8 -*-
#
# Copyright (c) 2022~2999 - Cologler <skyoflw@gmail.com>
# ----------
#
# ----------

import logging
import queue
import threading
import xml.etree.ElementTree as et
from functools import cache
from io import StringIO
from time import monotonic, sleep
from urllib.parse import urlparse

import requests
from pydantic import ValidationError
from schedule import Scheduler

from .cfg import ConfigHelper, FeedSection
from .models import RssItemRowRecord
from .settings import Settings


@cache
def get_logger():
    return logging.getLogger('rssfetcher')

def dump_xml(el: et.Element):
    sb = StringIO()
    tr = et.ElementTree(el)
    tr.write(sb, encoding='unicode', short_empty_elements=False)
    return sb.getvalue()

def _read_element_text(elements: list[et.Element | None] | et.Element | None):
    '''
    Read text from an element or a list of elements.
    '''
    if elements is not None:
        if not isinstance(elements, list):
            elements = [elements]
        for el in elements:
            if el is not None:
                return el.text

def _element_to_RssItemRowRecord(feed_id: str, item: et.Element, *, logger: logging.Logger) -> RssItemRowRecord | None:
    '''
    Convert an XML item element to a RssItemRowRecord.
    '''
    if unique_id := _read_element_text([item.find('guid'), item.find('title')]):
        rd: RssItemRowRecord = {
            'feed_id': feed_id,
            'rss_id': unique_id,
            'title': _read_element_text(item.find('title')),
            'raw': dump_xml(item)
        }
        return rd
    else:
        logger.warning('item %r has no unique id', item)
        return None

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
                for item in el.iter('item'):
                    if rd := _element_to_RssItemRowRecord(feed_id, item, logger=logger):
                        collected_items.append(rd)

                logger.info('total found %s items',len(collected_items))

    return collected_items

def fetch_feeds(config_helper: ConfigHelper, feeds: list):
    options = config_helper.get_config().config_data.get('options', {})
    kept_count = options.get('kept_count') if options else None

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

    with config_helper.open_store() as store:
        # save:
        count = store.get_count()
        store.upsert(fetched)
        count = store.get_count() - count
        get_logger().info('total added %s rss', count)

        # remove old items:
        if isinstance(kept_count, int) and kept_count >= 10: # hard limit
            removed_count = store.remove_old_items(kept_count)
        else:
            removed_count = 0
        get_logger().info('removed outdated %r items.', removed_count)

        store.commit()

type _JobQueueItem = tuple[str, FeedSection]

class RssFetcherWorker:
    def __init__(self, conf: ConfigHelper) -> None:
        self._config_helper = conf
        self._job_queue: queue.Queue[_JobQueueItem | None] = queue.Queue()
        self._is_shutdown = False
        self._scheduler = Scheduler()

    def start(self):
        job_queue = self._job_queue
        scheduler = self._scheduler

        def run_on_background(func):
            threading.Thread(target=func, daemon=True).start()

        @run_on_background
        def consumer():
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

            while True:
                feeds = get_feeds_in_10s()
                try:
                    if None not in feeds:
                        unique_feeds = list(filter_unique_feeds(feeds))
                        get_logger().info('Receive %d fetch jobs.', len(unique_feeds))
                        assert unique_feeds
                        fetch_feeds(self._config_helper, unique_feeds)
                finally:
                    for _ in range(len(feeds)):
                        job_queue.task_done()

        @run_on_background
        def producer():
            def put_job(job: _JobQueueItem):
                if not self._is_shutdown:
                    job_queue.put(job)
                else:
                    scheduler.clear()

            for feed_id, feed_section in self._config_helper.iter_feeds():
                job_args: _JobQueueItem = (feed_id, feed_section)
                minutes = max(feed_section.get('interval', 15), 5)
                scheduler.every(minutes).minutes.do(put_job, job_args)
                put_job(job_args)

            try:
                while scheduler.idle_seconds is not None:
                    scheduler.run_pending()
                    sleep(1)
            except KeyboardInterrupt:
                pass

    def shutdown(self):
        get_logger().info('Shutting down RssFetcherWorker...')
        self._is_shutdown = True
        self._job_queue.put(None)
        self._job_queue.join()


def configure_logger():
    logging.basicConfig(
        format='%(asctime)s [%(levelname)s] - %(name)s: %(message)s',
        datefmt='%m/%d/%Y %I:%M:%S %p',
        level=logging.INFO
    )
    get_logger().setLevel(logging.INFO)


def load_config_helper():
    def _load_settings():
        try:
            return Settings() # type: ignore
        except ValidationError as e:
            get_logger().error(e)
            exit()

    settings = _load_settings()
    config_helper = ConfigHelper(settings.config)
    return config_helper

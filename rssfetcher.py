# -*- coding: utf-8 -*-
#
# Copyright (c) 2020~2999 - Cologler <skyoflw@gmail.com>
# ----------
# require packages:
#   - pyyaml
#   - requests
# ----------

import logging
import sqlite3
from urllib.parse import urlparse
import xml.etree.ElementTree as et
import os
from io import StringIO
import sys
from contextlib import suppress
from collections import ChainMap
from time import monotonic, sleep
import queue
import threading

import requests
import yaml
import schedule


def get_logger():
    return logging.getLogger('rssfetcher')

def dump_xml(el):
    sb = StringIO()
    tr = et.ElementTree(el)
    tr.write(sb, encoding='unicode', short_empty_elements=False)
    return sb.getvalue()

def fetch_feed(feed_id: str, feed_section: dict):
    items = []
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
                    rd = {
                        'feed_id': feed_id,
                        'rss_id': item.find('guid').text,
                        'title': item.find('title').text,
                        'pub_date': item.find('pubDate').text,
                        'raw': dump_xml(item)
                    }
                    description = item.find('description')
                    if description is not None:
                        rd['description'] = description.text
                    items.append(rd)
                logger.info('total found %s items',len(items))
    return items


class RssStore:
    COLUMN_NAMES = ('feed_id', 'rss_id', 'title', 'raw')


class SqliteRssStore(RssStore):
    TABLE_NAME = 'rss'

    def __init__(self, conn_str: str) -> None:
        self._conn = sqlite3.connect(conn_str)
        self._cur = None

    def __enter__(self):
        self._cur = self._conn.cursor()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._cur and self._cur.close()
        self._conn and self._conn.close()

    def init_store(self):
        DEF_COL = ', '.join([
            self.COLUMN_NAMES[0] + ' TEXT NOT NULL',
            self.COLUMN_NAMES[1] + ' TEXT NOT NULL',
            self.COLUMN_NAMES[2] + ' TEXT',
            self.COLUMN_NAMES[3] + ' TEXT',
            'PRIMARY KEY ({}, {})'.format(self.COLUMN_NAMES[0], self.COLUMN_NAMES[1]),
        ])
        SQL_CREATE = 'CREATE TABLE IF NOT EXISTS {} ({});'.format(self.TABLE_NAME, DEF_COL)
        self._cur.execute(SQL_CREATE)

    def get_count(self) -> int:
        SQL_COUNT = 'SELECT COUNT({}) FROM {}'.format(self.COLUMN_NAMES[0], self.TABLE_NAME)
        return self._cur.execute(SQL_COUNT).fetchone()[0]

    def upsert(self, items):
        SQL_INSERT = 'INSERT OR IGNORE INTO {} VALUES ({});'.format(self.TABLE_NAME, ",".join("?" for _ in self.COLUMN_NAMES))
        self._cur.executemany(SQL_INSERT, items)

    def remove_old_items(self, kept_count: int):
        assert isinstance(kept_count, int) and kept_count > 0 # hard limit

        max_rowid = self._cur.execute('SELECT MAX(ROWID) FROM {}'.format(self.TABLE_NAME)).fetchone()[0]
        return self._cur.execute('DELETE FROM {} WHERE ROWID <= {}'.format(self.TABLE_NAME, max_rowid - kept_count)).rowcount

    def commit(self):
        self._conn.commit()


def _load_conf(conf_path: str) -> dict:
    if os.path.isfile(conf_path):
        with suppress(FileNotFoundError):
            with open(conf_path, mode='r', encoding='utf8') as fp:
                return yaml.safe_load(fp)
        get_logger().error('Unable open file: %s', conf_path)
    else:
        get_logger().error('No such file: %s', conf_path)
    exit(1)

def _conf_iter_feeds(conf_data: dict):
    default = conf_data.get('default', {})
    for feed_id, feed_section in conf_data.get('feeds', {}).items():
        yield feed_id, ChainMap(feed_section, default)

def _fetch_feeds(conf_data: dict, feeds: list):
    options = conf_data.get('options', {})

    with SqliteRssStore(conf_data.get('database', 'rss.sqlite3')) as store:
        # fetch from internet:
        fetched = []
        for feed_id, feed_section in feeds:
            try:
                items = fetch_feed(feed_id, feed_section)
            except Exception as error:
                get_logger().error('fetch %r failure with %s', error, exc_info=True)
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

def _start_worker(conf_data: dict):

    job_queue = queue.Queue()

    def get_feeds_in_10s():
        feeds = [job_queue.get()]
        start = monotonic()
        wait_time = 10
        while wait_time > 0:
            try:
                feeds.append(job_queue.get(timeout=wait_time))
            except queue.Empty:
                break
            wait_time = start + 10 - monotonic()

        rv = []
        s = set()
        for f in feeds:
            if f[0] not in s:
                rv.append(f)
                s.add(f[0])
        return rv

    def worker_main():
        while True:
            feeds = get_feeds_in_10s()
            get_logger().info('Receive %d fetch jobs.', len(feeds))
            assert feeds
            _fetch_feeds(conf_data, feeds)
            for _ in range(len(feeds)):
                job_queue.task_done()

    worker_thread = threading.Thread(target=worker_main, daemon=True)
    worker_thread.start()

    for feed_id, feed_section in _conf_iter_feeds(conf_data):
        job_args = (feed_id, feed_section)
        minutes = max(feed_section.get('interval', 15), 5)
        schedule.every(minutes).minutes.do(job_queue.put, job_args)

    while schedule.idle_seconds() is not None:
        schedule.run_pending()
        try:
            sleep(1)
        except KeyboardInterrupt:
            break

    job_queue.join() # wait all enqueued tasks

def _pop_options_kvp(argv, key):
    option_name = '--logger'
    try:
        index = argv.index(option_name)
    except ValueError:
        index = -1
    option_value = None
    if index >= 0 and len(argv) > index + 1:
        argv.pop(index)
        return argv.pop(index)
    return None

def configure_logger(argv):
    logging_options = dict(
        filename='rssfetcher.log',
        format='%(asctime)s [%(levelname)s] - %(name)s: %(message)s',
        datefmt='%m/%d/%Y %I:%M:%S %p',
        level=logging.INFO
    )
    option_value = _pop_options_kvp(argv, '--logger')
    if option_value == 'console':
        logging_options.pop('filename', None)
    logging.basicConfig(**logging_options)

def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    configure_logger(argv)
    try:
        conf_data = _load_conf(argv[0])
        _start_worker(conf_data)
    except Exception as error: # pylint: disable=W0703
        get_logger().error('main raised: %s', error, exc_info=True)

if __name__ == '__main__':
    main()

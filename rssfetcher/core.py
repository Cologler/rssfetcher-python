# -*- coding: utf-8 -*-
#
# Copyright (c) 2022~2999 - Cologler <skyoflw@gmail.com>
# ----------
#
# ----------

from functools import cache
from io import StringIO
from urllib.parse import urlparse
import xml.etree.ElementTree as et
import logging

import requests

from .stores import open_store

@cache
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

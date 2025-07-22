# -*- coding: utf-8 -*-
#
# Copyright (c) 2022~2999 - Cologler <skyoflw@gmail.com>
# ----------
#
# ----------

from rssfetcher.core import fetch_feed, fetch_feeds
from rssfetcher.stores import RssStore

async def _fetch_from_url(url: str):
    return fetch_feed('', { 'url': url })

async def test_fetch_feed_failed_should_return_empty_list():
    assert [] == await _fetch_from_url('http://127.0.0.1:7777')

async def test_fetch_feed_real_dest():
    items = fetch_feed('', {
        'url': 'https://dmhy.org/topics/rss/rss.xml'
    })
    assert items
    assert set(items[0]).issuperset(RssStore.COLUMN_NAMES)

# -*- coding: utf-8 -*-
# 
# Copyright (c) 2025~2999 - Cologler <skyoflw@gmail.com>
# ----------
# 
# ----------

from rssfetcher.stores import open_store

def test_store():
    with open_store(":memory:") as store:
        store.init_store()
        assert store.get_count() == 0

        store.upsert([
            {'feed_id': 'feed1', 'rss_id': 'rss1', 'title': 'Title 1', 'raw': '<item>Content 1</item>'},
            {'feed_id': 'feed2', 'rss_id': 'rss2', 'title': 'Title 2', 'raw': '<item>Content 2</item>'}
        ])

        assert store.get_count() == 2
        items = store.read_items(0, 10)
        assert len(items) == 2
        assert items[0]['title'] == 'Title 1'
        assert items[1]['title'] == 'Title 2'

# -*- coding: utf-8 -*-
#
# Copyright (c) 2022~2999 - Cologler <skyoflw@gmail.com>
# ----------
#
# ----------

from collections import ChainMap

from .stores import open_store

class ConfigHelper:
    def __init__(self, conf_data: dict) -> None:
        self.conf_data = conf_data

    def open_store(self):
        return open_store(self.conf_data.get('database', 'rss.sqlite3'))

    def iter_feeds(self):
        default = self.conf_data.get('default', {})
        for feed_id, feed_section in self.conf_data.get('feeds', {}).items():
            yield feed_id, ChainMap(feed_section, default)

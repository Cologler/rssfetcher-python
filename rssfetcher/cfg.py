# -*- coding: utf-8 -*-
#
# Copyright (c) 2022~2999 - Cologler <skyoflw@gmail.com>
# ----------
#
# ----------

from typing import TypedDict, Tuple, Dict, Optional, Iterable
from collections import ChainMap

from .stores import open_store

class ConfigError(Exception):
    pass

class ProxiesSection(TypedDict):
    pass

class FeedSection(TypedDict):
    url: str
    enable: Optional[bool]
    proxy: Optional[str]
    proxies: Optional[Dict[str, str]]

class OptionsSection(TypedDict):
    kept_count: Optional[int]

class RootSection(TypedDict):
    database: Optional[str]
    options: Optional[OptionsSection]
    default: Optional[FeedSection]
    feeds: Optional[Dict[str, FeedSection]]

class ConfigHelper:
    def __init__(self, conf_data: dict) -> None:
        self.conf_data: RootSection = conf_data

    def open_store(self):
        return open_store(self.conf_data.get('database', 'rss.sqlite3'))

    def iter_feeds(self) -> Iterable[Tuple[str, FeedSection]]:
        default = self.conf_data.get('default', {})
        for feed_id, feed_section in self.conf_data.get('feeds', {}).items():
            yield feed_id, ChainMap(feed_section, default)

# -*- coding: utf-8 -*-
#
# Copyright (c) 2022~2999 - Cologler <skyoflw@gmail.com>
# ----------
#
# ----------

import os
from collections import ChainMap
from contextlib import suppress
from logging import getLogger
from typing import Dict, Iterable, NotRequired, Optional, Tuple, TypedDict

import yaml
from cachetools import cachedmethod

from .stores import SqliteRssStore, open_store

logger = getLogger(__name__)


class ConfigError(Exception):
    pass


class ProxiesSection(TypedDict):
    pass


class FeedSection(TypedDict):
    url: str
    enable: NotRequired[bool]
    proxy: NotRequired[str]
    proxies: NotRequired[Dict[str, str]]


class OptionsSection(TypedDict):
    kept_count: NotRequired[int]


class RootSection(TypedDict):
    database: Optional[str]
    options: Optional[OptionsSection]
    default: Optional[FeedSection]
    feeds: Optional[Dict[str, FeedSection]]


class Config:
    def __init__(self, config_data: RootSection) -> None:
        self.config_data: RootSection = config_data
        self._cache = {}

    def get_conn_str(self) -> str:
        return self.config_data.get('database') or 'rss.sqlite3'

    def open_store(self) -> SqliteRssStore:
        return open_store(self.get_conn_str())

    @cachedmethod(cache=lambda x: x._cache)
    def init_store(self) -> None:
        logger.info('Init store at %s', self.get_conn_str())
        with self.open_store() as store:
            store.init_store()
            store.commit()

    def iter_feeds(self) -> Iterable[Tuple[str, FeedSection]]:
        default = self.config_data.get('default')
        if feeds := self.config_data.get('feeds'):
            for feed_id, feed_section in feeds.items():
                yield feed_id, ChainMap(feed_section, default or {}) # type: ignore


class ConfigHelper:
    def __init__(self, config_path: str | None) -> None:
        self.__config_path = config_path
        self.__config: Config | None = None

    def open_store(self) -> SqliteRssStore:
        return self.get_config().open_store()

    def iter_feeds(self) -> Iterable[Tuple[str, FeedSection]]:
        yield from self.get_config().iter_feeds()

    def _load_config_from_path(self, path: str) -> RootSection:
        if os.path.isfile(path):
            with suppress(FileNotFoundError):
                with open(path, mode='r', encoding='utf8') as fp:
                    data = yaml.safe_load(fp)
                    logger.info('Load config from %s', path)
                    return data
            logger.error('Unable open file: %s', path)
        else:
            logger.error('No such file: %s', path)
        exit(1)

    def get_config(self) -> Config:
        '''
        Get config snapshot.
        '''
        if self.__config is None:
            if self.__config_path is None:
                raise ConfigError('Config path is not set.')
            self.__config = Config(self._load_config_from_path(self.__config_path))
            logger.info('Config loaded from %s', self.__config_path)
            logger.info('Database: %s', self.__config.get_conn_str())

        return self.__config

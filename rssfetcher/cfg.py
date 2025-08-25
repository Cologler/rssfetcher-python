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
from typing import Dict, Iterable, Literal, NotRequired, Optional, Tuple, TypedDict

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
    guid_from: NotRequired[Literal['title', 'content']]


class OptionsSection(TypedDict):
    kept_count: NotRequired[int]


class RootSection(TypedDict):
    database: Optional[str]
    options: Optional[OptionsSection]
    default: Optional[FeedSection]
    feeds: Optional[Dict[str, FeedSection]]


class Config:
    def __init__(self, config_data: RootSection, *, mtime_ns: int) -> None:
        self.config_data: RootSection = config_data
        self.mtime_ns = mtime_ns
        self._cache = {}

    def get_conn_str(self) -> str:
        return self.config_data.get('database') or 'rss.sqlite3'

    def open_store(self) -> SqliteRssStore:
        return open_store(self.get_conn_str())

    @cachedmethod(cache=lambda x: x._cache)
    def init_store(self) -> None:
        '''
        This method is cached so it is safe to call multi times.
        '''
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

    @property
    def config_path(self) -> str:
        if (config_path := self.__config_path) is None:
            raise ConfigError('Config path is not set.')
        return config_path

    def open_store(self) -> SqliteRssStore:
        return self.get_config().open_store()

    def iter_feeds(self) -> Iterable[Tuple[str, FeedSection]]:
        yield from self.get_config().iter_feeds()

    def _load_config(self, path: str) -> Config | None:
        config_content: RootSection | None = None
        mtime_ns = -1

        if os.path.isfile(path):
            with suppress(FileNotFoundError):
                with open(path, mode='r', encoding='utf8') as fp:
                    config_content = yaml.safe_load(fp)
                    mtime_ns = os.stat(fp.fileno()).st_mtime_ns
                    logger.info('Load config from %s', path)
            logger.warning('Unable open file: %s', path)
        else:
            logger.warning('No such file: %s', path)

        if config_content is not None:
            return Config(config_content, mtime_ns=mtime_ns)

    def reload_config(self) -> bool:
        config_path = self.config_path

        if (config := self._load_config(config_path)) is not None:
            is_store_updated = self.__config is None or self.__config.get_conn_str() != config.get_conn_str()
            self.__config = config
            logger.info('Config loaded from %s', config_path)
            logger.info('Database: %s', config.get_conn_str())
            if is_store_updated:
                config.init_store()
            else:
                logger.info('Database connect string not changed, skip init.')
            return True

        return False

    def reload_config_if_updated(self) -> bool:
        '''
        Return True if updated and reloaded.
        '''
        config_path = self.config_path

        with suppress(FileNotFoundError):
            mtime_ns = os.stat(config_path).st_mtime_ns
            if mtime_ns != self.get_config().mtime_ns:
                logger.info('Config file (%s) is updated, try reload...', config_path)
                if self.reload_config():
                    logger.info('Reload completed')
                    return True
                else:
                    logger.warning('Reload failed')

        return False

    def get_config(self) -> Config:
        '''
        Get config snapshot.
        '''
        if self.__config is None:
            if not self.reload_config():
                raise ConfigError('Unable load config')
            assert self.__config is not None

        return self.__config

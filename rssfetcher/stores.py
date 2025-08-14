# -*- coding: utf-8 -*-
#
# Copyright (c) 2022~2999 - Cologler <skyoflw@gmail.com>
# ----------
#
# ----------

import sqlite3

from .models import RssItemRowRecord


class RssStore:
    COLUMN_NAME_FEED_ID = 'feed_id'
    COLUMN_NAME_RSS_ID = 'rss_id'
    COLUMN_NAME_TITLE = 'title'
    COLUMN_NAME_RAW = 'raw'

    COLUMN_NAMES = (
        COLUMN_NAME_FEED_ID,
        COLUMN_NAME_RSS_ID,
        COLUMN_NAME_TITLE,
        COLUMN_NAME_RAW
    )


class SqliteRssStore(RssStore):
    TABLE_NAME = 'rss'

    def __init__(self, conn_str: str) -> None:
        self.__conn_str = conn_str
        self.__conn: sqlite3.Connection | None = None
        self.__cur: sqlite3.Cursor | None = None

    def __enter__(self):
        self.__conn = sqlite3.connect(self.__conn_str, check_same_thread=False)
        self.__cur = self.__conn.cursor()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if cur := self.__cur:
            cur.close()
        self.__cur = None

        if conn := self.__conn:
            conn.close()
        self.__conn = None

    @property
    def _conn(self):
        if conn := self.__conn:
            return conn
        # If connection is not initialized, raise an error
        raise RuntimeError("Connection is not initialized")

    @property
    def _cur(self):
        if cur := self.__cur:
            return cur
        # If cursor is not initialized, raise an error
        raise RuntimeError("Cursor is not initialized")

    def init_store(self):
        DEF_COL = ', '.join([
            self.COLUMN_NAME_FEED_ID + ' TEXT NOT NULL',
            self.COLUMN_NAME_RSS_ID  + ' TEXT NOT NULL',
            self.COLUMN_NAME_TITLE   + ' TEXT',
            self.COLUMN_NAME_RAW     + ' TEXT',
            'PRIMARY KEY ({}, {})'.format(self.COLUMN_NAME_FEED_ID, self.COLUMN_NAME_RSS_ID),
        ])
        SQL_CREATE = 'CREATE TABLE IF NOT EXISTS {} ({});'.format(self.TABLE_NAME, DEF_COL)
        self._cur.execute(SQL_CREATE)

    def get_count(self) -> int:
        SQL_COUNT = 'SELECT COUNT({}) FROM {}'.format(self.COLUMN_NAME_FEED_ID, self.TABLE_NAME)
        return self._cur.execute(SQL_COUNT).fetchone()[0]

    def get_min_id(self) -> int:
        SQL_MIN = 'SELECT MIN(ROWID) FROM {}'.format(self.TABLE_NAME)
        return self._cur.execute(SQL_MIN).fetchone()[0]

    def get_max_id(self) -> int:
        SQL_MIN = 'SELECT MAX(ROWID) FROM {}'.format(self.TABLE_NAME)
        return self._cur.execute(SQL_MIN).fetchone()[0]

    def upsert(self, items: list[RssItemRowRecord]):
        def torow(item: RssItemRowRecord | tuple) -> tuple:
            if isinstance(item, dict):
                return tuple(item.get(x) for x in self.COLUMN_NAMES)
            assert len(item) == len(self.COLUMN_NAMES), "Item length does not match column names length"
            return item
        rows = [torow(item) for item in items]
        SQL_INSERT = 'INSERT OR IGNORE INTO {} VALUES ({});' \
            .format(self.TABLE_NAME, ",".join("?" for _ in self.COLUMN_NAMES))
        self._cur.executemany(SQL_INSERT, rows)

    def remove_old_items(self, kept_count: int):
        assert isinstance(kept_count, int) and kept_count > 0 # hard limit

        max_rowid = self._cur.execute('SELECT MAX(ROWID) FROM {}'.format(self.TABLE_NAME)).fetchone()[0]
        if max_rowid is None:
            # no items
            return 0
        cur = self._cur.execute('DELETE FROM {} WHERE ROWID <= {}'.format(self.TABLE_NAME, max_rowid - kept_count))
        return cur.rowcount

    def commit(self):
        self._conn.commit()

    def read_items(self, start_rowid: int, limit: int) -> list[sqlite3.Row]:
        sql = 'SELECT ROWID, * FROM {} WHERE ROWID > {} ORDER BY ROWID LIMIT {}'.format(
            self.TABLE_NAME, start_rowid, limit
        )

        self._cur.row_factory = sqlite3.Row # type: ignore
        reader = self._cur.execute(sql)
        items = reader.fetchall()
        return items

    def read_items_as_dict(self, start_rowid: int, limit: int) -> list[dict[str, object]]:
        return [dict(x) for x in self.read_items(start_rowid=start_rowid, limit=limit)]


def open_store(conn_str: str):
    return SqliteRssStore(conn_str)

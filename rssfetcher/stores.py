# -*- coding: utf-8 -*-
#
# Copyright (c) 2022~2999 - Cologler <skyoflw@gmail.com>
# ----------
#
# ----------

import sqlite3


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

    def upsert(self, items):
        SQL_INSERT = 'INSERT OR IGNORE INTO {} VALUES ({});' \
            .format(self.TABLE_NAME, ",".join("?" for _ in self.COLUMN_NAMES))
        self._cur.executemany(SQL_INSERT, items)

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

    def read_items(self, start_rowid: int, limit: int):
        sql = 'SELECT ROWID, * FROM {} WHERE ROWID > {} ORDER BY ROWID LIMIT {}'.format(
            self.TABLE_NAME, start_rowid, limit
        )

        self._cur.row_factory = sqlite3.Row
        reader = self._cur.execute(sql)
        items = reader.fetchall()
        return items


def open_store(conn_str: str):
    return SqliteRssStore(conn_str)

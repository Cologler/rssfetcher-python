# -*- coding: utf-8 -*-
# 
# Copyright (c) 2025~2999 - Cologler <skyoflw@gmail.com>
# ----------
# 
# ----------

from typing import TypedDict


class RssItemRowRecord(TypedDict):
    feed_id: str
    rss_id: str
    title: str | None
    raw: str

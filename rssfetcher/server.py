# -*- coding: utf-8 -*-
#
# Copyright (c) 2022~2999 - Cologler <skyoflw@gmail.com>
# ----------
#
# ----------

import sys

from fastapi import FastAPI

from .core import RssFetcherWorker, _main_base
from .cfg import ConfigHelper

def create_app(conf: ConfigHelper):

    app = FastAPI()

    worker = RssFetcherWorker(conf)
    app.on_event("startup")(worker.start)
    app.on_event("shutdown")(worker.shutdown)

    @app.get("/items/")
    async def get_items(start_rowid: int = 0, limit: int = None):
        limit_max = 1000
        limit = min(max(limit, 1), limit_max) if isinstance(limit, int) else limit_max

        with conf.open_store() as store:
            readed_items = store.read_items(start_rowid, limit + 1)
            return {
                'end': len(readed_items) <= limit,
                'items': readed_items[:limit],
            }

    @app.get("/items-count")
    async def get_items_count():
        with conf.open_store() as store:
            return {
                'count': store.get_count()
            }

    return app

def default_app(argv = sys.argv):
    conf = _main_base(argv[1:])
    return create_app(conf)

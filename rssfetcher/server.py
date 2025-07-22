# -*- coding: utf-8 -*-
#
# Copyright (c) 2022~2999 - Cologler <skyoflw@gmail.com>
# ----------
#
# ----------

import sys

from fastapi import FastAPI, Response

from .core import RssFetcherWorker, _main_base
from .cfg import ConfigHelper

def create_app(conf: ConfigHelper):

    worker = RssFetcherWorker(conf)

    app = FastAPI(
        on_startup=[worker.start],
        on_shutdown=[worker.shutdown],
    )

    @app.head("/items")
    @app.get("/items")
    async def get_items(start_rowid: int = 0, limit: int | None = None):
        limit_max = 1000
        limit = min(max(limit, 1), limit_max) if isinstance(limit, int) else limit_max

        with conf.open_store() as store:
            readed_items = store.read_items(start_rowid, limit + 1)
            return {
                'end': len(readed_items) <= limit,
                'items': readed_items[:limit],
            }

    @app.head("/status")
    @app.get("/status")
    async def get_status():
        with conf.open_store() as store:
            return {
                'count': store.get_count(),
                'min_id': store.get_min_id(),
                'max_id': store.get_max_id(),
            }

    @app.head('/ping')
    @app.get('/ping')
    def ping():
        return Response(status_code=200)

    return app

def default_app(argv = sys.argv):
    conf = _main_base(argv[1:])
    return create_app(conf)

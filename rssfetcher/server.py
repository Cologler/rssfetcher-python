# -*- coding: utf-8 -*-
#
# Copyright (c) 2022~2999 - Cologler <skyoflw@gmail.com>
# ----------
#
# ----------

from contextlib import asynccontextmanager, contextmanager
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Request, Response

from .cfg import Config
from .core import RssFetcherWorker, configure_logger, load_config_helper
from .stores import SqliteRssStore


def _get_config_from_request(request: Request):
    return request.app.state.config_helper.get_config()


ConfigType = Annotated[Config, Depends(_get_config_from_request)]


@contextmanager
def _open_store(config: ConfigType):
    with config.open_store() as store:
        yield store


StoreType = Annotated[SqliteRssStore, Depends(_open_store)]

router = APIRouter()


@router.head("/items")
@router.get("/items")
async def get_items(
    store: StoreType,
    start_rowid: int = 0, limit: int | None = None,
):
    limit_max = 1000
    limit = min(max(limit, 1), limit_max) if isinstance(
        limit, int) else limit_max

    readed_items = store.read_items(start_rowid, limit + 1)
    return {
        'end': len(readed_items) <= limit,
        'items': readed_items[:limit],
    }


@router.head("/status")
@router.get("/status")
async def get_status(
    store: StoreType,
):
    return {
        'count': store.get_count(),
        'min_id': store.get_min_id(),
        'max_id': store.get_max_id(),
    }


@router.head('/ping')
@router.get('/ping')
def ping():
    return Response(status_code=200)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logger()

    config_helper = load_config_helper()
    config_helper.get_config().init_store()
    app.state.config_helper = config_helper

    worker = RssFetcherWorker(config_helper)
    worker.start()

    yield

    worker.shutdown()

app = FastAPI(
    lifespan=lifespan,
)
app.add_api_route('', router)

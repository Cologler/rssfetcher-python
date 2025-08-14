# -*- coding: utf-8 -*-
#
# Copyright (c) 2022~2999 - Cologler <skyoflw@gmail.com>
# ----------
#
# ----------

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Annotated, cast

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.security import APIKeyHeader, APIKeyQuery

from .cfg import Config, ConfigHelper
from .core import RssFetcherWorker, configure_logger, load_config_helper
from .settings import SettingsDeps
from .stores import SqliteRssStore


def _get_config_from_request(request: Request) -> Config:
    config_helper = cast(ConfigHelper, request.app.state.config_helper)
    return config_helper.get_config()

ConfigDeps = Annotated[Config, Depends(_get_config_from_request)]

def _open_store(config: ConfigDeps) -> Iterator[SqliteRssStore]:
    with config.open_store() as store:
        yield store

StoreDeps = Annotated[SqliteRssStore, Depends(_open_store, use_cache=False)]


def _verify_api_key(
    settings: SettingsDeps,
    header_api_key: Annotated[str | None, Depends(APIKeyHeader(name="x-key", auto_error=False))],
    query_api_key: Annotated[str | None, Depends(APIKeyQuery(name="api_key", auto_error=False))],
) -> None:
    if secret_key := settings.secret_key:
        if not header_api_key and not query_api_key:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authenticated")
        if secret_key not in (header_api_key, query_api_key):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API key")


router = APIRouter()


@router.head("/items", dependencies=[Depends(_verify_api_key)])
@router.get("/items", dependencies=[Depends(_verify_api_key)])
async def get_items(
    store: StoreDeps,
    start_rowid: int = 0, limit: int | None = None,
) -> dict:
    limit_max = 1000
    limit = min(max(limit, 1), limit_max) if isinstance(
        limit, int) else limit_max

    readed_items = store.read_items_as_dict(start_rowid, limit + 1)
    return {
        'end': len(readed_items) <= limit,
        'items': readed_items[:limit],
    }


@router.head("/status", dependencies=[Depends(_verify_api_key)])
@router.get("/status", dependencies=[Depends(_verify_api_key)])
async def get_status(
    store: StoreDeps,
) -> dict:
    return {
        'count': store.get_count(),
        'min_id': store.get_min_id(),
        'max_id': store.get_max_id(),
    }


@router.head('/ping')
@router.get('/ping')
def ping() -> Response:
    return Response(status_code=200)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logger()

    config_helper = load_config_helper()
    config_helper.get_config().init_store()
    app.state.config_helper = config_helper

    worker = RssFetcherWorker(config_helper)

    worker.start()
    try:
        yield
    finally:
        worker.shutdown()

app = FastAPI(
    lifespan=lifespan,
)
app.include_router(router)

# -*- coding: utf-8 -*-
# 
# Copyright (c) 2025~2999 - Cologler <skyoflw@gmail.com>
# ----------
# 
# ----------

from typing import Annotated

from fastapi import Depends
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {
        'env_prefix': 'RSSFETCHER_',
    }

    config: str | None = None
    secret_key: str | None = None

def load_settings() -> Settings:
    return Settings()

# error if use Depends(Settings)
SettingsDeps = Annotated[Settings, Depends(load_settings)]

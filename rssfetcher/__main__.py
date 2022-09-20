# -*- coding: utf-8 -*-
#
# Copyright (c) 2022~2999 - Cologler <skyoflw@gmail.com>
# ----------
#
# ----------

from typing import *
import os
import sys

from .core import _main_base, fetch_feeds

def fetch_once(argv = sys.argv):
    conf = _main_base(argv[1:])
    fetch_feeds(conf, list(conf.iter_feeds()))

if __name__ == '__main__':
    exit(fetch_once() or 0)

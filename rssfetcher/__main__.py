# -*- coding: utf-8 -*-
#
# Copyright (c) 2022~2999 - Cologler <skyoflw@gmail.com>
# ----------
#
# ----------

import sys

from .core import fetch_feeds, configure_logger, load_config_helper

def fetch_once(argv = sys.argv):
    configure_logger()
    conf = load_config_helper()
    try:
        fetch_feeds(conf, list(conf.iter_feeds()))
    except KeyboardInterrupt:
        print('User cancel.')
        return 1

if __name__ == '__main__':
    exit(fetch_once() or 0)

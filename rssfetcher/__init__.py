# -*- coding: utf-8 -*-
#
# Copyright (c) 2020~2999 - Cologler <skyoflw@gmail.com>
# ----------
# require packages:
#   - pyyaml
#   - requests
# ----------

if __name__ == 'rssfetcher':
    from .server import default_app
    app = default_app()

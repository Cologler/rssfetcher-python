# -*- coding: utf-8 -*-
# 
# Copyright (c) 2025~2999 - Cologler <skyoflw@gmail.com>
# ----------
# 
# ----------

from hashlib import sha1


def create_unique_id(content: str) -> str:
    '''
    Create unique identifier.
    '''
    hashed = sha1(content.encode('utf-8', errors='ignore')).hexdigest()
    return f'sha1:{hashed}'

# SPDX-FileCopyrightText: 2023 MobileAtlas <https://www.mobileatlas.eu/>
#
# SPDX-License-Identifier: GPL-3.0-only

import requests
import functools
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry


def get_requests_retry_session(
    retries=5,
    backoff_factor=0.3,
    status_forcelist=(429, 500, 502, 503, 504),
    timeout=30,
    session=None,
):
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    # set default timeout
    for method in ('get', 'options', 'head', 'post', 'put', 'patch', 'delete'):
        setattr(session, method, functools.partial(getattr(session, method), timeout=timeout))
    return session
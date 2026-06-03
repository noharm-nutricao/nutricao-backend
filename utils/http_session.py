"""Sessão HTTP compartilhada.

Um único ``requests.Session()`` no escopo do módulo, reusado entre invocações "quentes" da Lambda
(keep-alive / pooling por host). Retry com parcimônia:

- ``read=0``: não re-tenta timeouts de leitura — uma chamada ao LLM pode levar ~25s; re-tentar
  estouraria o limite de 30s da Lambda / 29s do API Gateway.
- ``status_forcelist=[502, 503]``: só re-tenta falhas rápidas do provedor. **504 fica de fora** (um
  timeout do modelo re-tentado provavelmente repetiria o estouro de tempo).
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

session: requests.Session = requests.Session()

_retry = Retry(
    total=2,
    connect=2,
    read=0,
    status_forcelist=[502, 503],
    backoff_factor=0.3,
    allowed_methods=frozenset(["GET", "POST"]),
    respect_retry_after_header=True,
)

session.mount("https://", HTTPAdapter(max_retries=_retry))
session.mount("http://", HTTPAdapter(max_retries=_retry))

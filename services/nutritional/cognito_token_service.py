"""Service: token M2M do Cognito (client_credentials) com cache no Postgres (issue #88).

Passo 1 do fluxo: obter um ``access_token`` válido. Na maioria das requisições é cache HIT (o token
vale ~1h); só renova quando expira. Sem cookie XSRF (fluxo M2M).
"""

from datetime import datetime, timedelta, timezone

import requests

from config import Config
from exception.validation_error import ValidationError
from repository.nutritional import cognito_token_repository
from utils import logger, status
from utils.cryptutils import decrypt_data, encrypt_data
from utils.http_session import session

_TIMEOUT = (3.05, 10)
_EXPIRY_MARGIN_SECONDS = 60


def get_access_token() -> str:
    """Devolve um ``access_token`` válido (do cache ou renovado no Cognito)."""
    cached = cognito_token_repository.get_valid_token()
    if cached is not None:
        return decrypt_data(cached.access_token)

    access_token, expires_in, token_type = _request_cognito_token()

    # expires_in vem em SEGUNDOS de validade; margem de 60s evita usar token "no fio".
    expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=expires_in - _EXPIRY_MARGIN_SECONDS
    )
    cognito_token_repository.upsert_token(
        encrypt_data(access_token), expires_at, token_type
    )
    return access_token


def _request_cognito_token() -> tuple[str, int, str]:
    """POST ao Cognito; retorna (access_token, expires_in, token_type)."""
    try:
        resp = session.post(
            Config.COGNITO_TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "client_credentials",
                "client_id": Config.COGNITO_CLIENT_ID,
                "client_secret": Config.COGNITO_CLIENT_SECRET,
                "scope": Config.COGNITO_SCOPE,
            },
            timeout=_TIMEOUT,
        )
    except requests.exceptions.Timeout as e:
        logger.backend_logger.error(f"Cognito timeout: {e}")
        raise ValidationError(
            "Tempo limite ao autenticar no provedor",
            "errors.gatewayTimeout",
            status.HTTP_504_GATEWAY_TIMEOUT,
        )
    except requests.exceptions.RequestException as e:
        logger.backend_logger.error(f"Cognito request error: {e}")
        raise ValidationError(
            "Falha ao autenticar no provedor",
            "errors.badGateway",
            status.HTTP_502_BAD_GATEWAY,
        )

    if resp.status_code != status.HTTP_200_OK:
        logger.backend_logger.error(
            f"Cognito non-200: {resp.status_code} {resp.text}"
        )
        raise ValidationError(
            "Falha ao autenticar no provedor",
            "errors.badGateway",
            status.HTTP_502_BAD_GATEWAY,
        )

    data = resp.json()
    return (
        data["access_token"],
        int(data["expires_in"]),
        data.get("token_type", "Bearer"),
    )

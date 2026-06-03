"""Repository: cache do token M2M do Cognito em ``public.cognito_token_cache`` (issue #88).

A tabela pode ainda não existir (sem migration). Nesse caso a busca devolve ``None`` e o upsert é
no-op → o serviço degrada **sem cache** (busca o token direto no Cognito a cada request), sem DDL em
runtime e sem erro de "relation does not exist".
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import insert

from models.main import db, dbSession
from models.nutritional import CognitoTokenCache


def _current_schema() -> str:
    """Schema do tenant ativo, lido das execution options da conexão."""
    connection = db.session.connection()
    return (
        connection.get_execution_options()
        .get("schema_translate_map", {})
        .get(None)
        or "demo"
    )


def _is_cognito_table_ready() -> bool:
    """True se ``public.cognito_token_cache`` existe."""
    return bool(
        db.session.execute(
            text(
                "SELECT EXISTS ("
                "    SELECT 1 FROM information_schema.tables "
                "    WHERE table_schema = 'public' "
                "      AND table_name = 'cognito_token_cache'"
                ")"
            )
        ).scalar()
    )


def get_valid_token() -> Optional[CognitoTokenCache]:
    """Retorna o token ainda válido (``expires_at > now()``) ou ``None`` (inclui tabela ausente)."""
    if not _is_cognito_table_ready():
        return None

    return (
        db.session.query(CognitoTokenCache)
        .filter(
            CognitoTokenCache.id == 1,
            CognitoTokenCache.expires_at > func.now(),
        )
        .first()
    )


def upsert_token(
    access_token_encrypted: str,
    expires_at: datetime,
    token_type: str = "Bearer",
) -> None:
    """UPSERT atômico do singleton (``id = 1``) com commit imediato.

    ``INSERT ... ON CONFLICT (id) DO UPDATE`` + ``commit`` logo após: libera o row-lock da linha e
    torna o token visível **antes** da chamada longa ao LLM. Reaplica o schema do tenant após o
    commit (o ``schema_translate_map`` é perdido). No-op se a tabela ainda não existe.
    """
    if not _is_cognito_table_ready():
        return

    schema: str = _current_schema()

    values: dict = {
        "access_token": access_token_encrypted,
        "token_type": token_type,
        "expires_at": expires_at,
        "updated_at": func.now(),
    }

    stmt: dict = (
        insert(CognitoTokenCache)
        .values(id=1, **values)
        .on_conflict_do_update(index_elements=["id"], set_=values)
    )

    db.session.execute(stmt)
    db.session.commit()
    dbSession.setSchema(schema)

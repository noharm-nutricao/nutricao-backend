from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from repository.nutritional_temp import nutritional_nrs_repository as repo
from services.temp_nutritional.nutritional_dtos import NrsScoreDTO


@pytest.fixture(autouse=True)
def clear_lru_cache() -> None:
    repo.get_cid_mappings_cached.cache_clear()


# Delegation wrappers

def test_get_nrs_assessment_delegates_to_internal(monkeypatch: pytest.MonkeyPatch) -> None:
    internal = MagicMock(return_value="ok")
    monkeypatch.setattr(repo, "_get_nrs_assessment", internal)

    result = repo.get_nrs_assessment(123)

    assert result == "ok"
    internal.assert_called_once_with(repo.db.session, 123)


def test_get_or_create_triagem_delegates_to_internal(monkeypatch: pytest.MonkeyPatch) -> None:
    internal = MagicMock(return_value="triagem")
    monkeypatch.setattr(repo, "_get_or_create_triagem", internal)

    result = repo.get_or_create_triagem(55)

    assert result == "triagem"
    internal.assert_called_once_with(repo.db.session, 55)


def test_update_triagem_delegates_to_internal(monkeypatch: pytest.MonkeyPatch) -> None:
    internal = MagicMock(return_value=None)
    monkeypatch.setattr(repo, "_update_triagem", internal)
    triagem = SimpleNamespace()
    dto = SimpleNamespace()

    result = repo.update_triagem(triagem, dto)

    assert result is None
    internal.assert_called_once_with(repo.db.session, triagem, dto)


def test_get_patient_department_delegates_to_internal(monkeypatch: pytest.MonkeyPatch) -> None:
    internal = MagicMock(return_value="UTI")
    monkeypatch.setattr(repo, "_get_patient_department", internal)

    result = repo.get_patient_department(9)

    assert result == "UTI"
    internal.assert_called_once_with(repo.db.session, 9)


# Internal query builders

def test_get_nrs_assessment_internal_builds_query_chain() -> None:
    session = MagicMock()
    query = session.query.return_value
    filtered = query.filter.return_value
    ordered = filtered.order_by.return_value
    expected = SimpleNamespace(id=1)
    ordered.first.return_value = expected

    result = repo._get_nrs_assessment(session, 88)

    session.query.assert_called_once_with(repo.NutricionalNrs)
    query.filter.assert_called_once()
    filtered.order_by.assert_called_once()
    ordered.first.assert_called_once_with()
    assert result is expected


def test_get_or_create_triagem_internal_returns_existing_without_persist() -> None:
    session = MagicMock()
    query = session.query.return_value
    filtered = query.filter.return_value
    existing = SimpleNamespace(id=10)
    filtered.first.return_value = existing

    result = repo._get_or_create_triagem(session, 77)

    assert result is existing
    session.add.assert_not_called()
    session.flush.assert_not_called()


def test_get_or_create_triagem_internal_creates_with_defaults() -> None:
    session = MagicMock()
    query = session.query.return_value
    filtered = query.filter.return_value
    filtered.first.return_value = None

    result = repo._get_or_create_triagem(session, 42)

    assert isinstance(result, repo.NutricionalScreening)
    assert result.nratendimento == 42
    assert result.protocolo == "NRS2002"
    assert result.nrs_completo is False
    assert result.nrs_total is None
    assert result.classificacao is None
    session.add.assert_called_once_with(result)
    session.flush.assert_called_once_with()


def test_update_triagem_internal_updates_fields_and_flushes() -> None:
    session = MagicMock()
    triagem = SimpleNamespace(
        nrs_nut=None,
        nrs_doenca=None,
        nrs_idade=None,
        nrs_total=None,
        nrs_completo=False,
        nrs_ref_at=None,
        calculado_at=None,
    )
    now = datetime(2026, 4, 11, 12, 0, 0)
    dto = NrsScoreDTO(
        id=1,
        nrs_nut=2,
        nrs_doenca=1,
        nrs_idade=1,
        nrs_total=4,
        nrs_completo=True,
        nrs_ref_at=now,
        calculado_at=now,
    )

    result = repo._update_triagem(session, triagem, dto)

    assert result is None
    assert triagem.nrs_nut == 2
    assert triagem.nrs_doenca == 1
    assert triagem.nrs_idade == 1
    assert triagem.nrs_total == 4
    assert triagem.nrs_completo is True
    assert triagem.nrs_ref_at == now
    assert triagem.calculado_at == now
    session.add.assert_called_once_with(triagem)
    session.flush.assert_called_once_with()


def test_get_patient_department_internal_returns_name() -> None:
    session = MagicMock()
    query = session.query.return_value
    joined = query.join.return_value
    filtered = joined.filter.return_value
    ordered = filtered.order_by.return_value
    limited = ordered.limit.return_value
    limited.first.return_value = SimpleNamespace(name="UTI Adulto")

    result = repo._get_patient_department(session, 1001)

    assert result == "UTI Adulto"


def test_get_patient_department_internal_returns_none_when_missing() -> None:
    session = MagicMock()
    query = session.query.return_value
    joined = query.join.return_value
    filtered = joined.filter.return_value
    ordered = filtered.order_by.return_value
    limited = ordered.limit.return_value
    limited.first.return_value = None

    result = repo._get_patient_department(session, 1002)

    assert result is None


# Raw SQL mapping helpers

def test_get_nutricional_cid_override_maps_rows_to_tuples() -> None:
    session = MagicMock()
    exec_result = MagicMock()
    exec_result.fetchall.return_value = [("A41", 2), ("B34", 1)]
    session.execute.return_value = exec_result

    result = repo.get_nutricional_cid_override(session)

    assert result == [("A41", 2), ("B34", 1)]
    session.execute.assert_called_once()


def test_get_nutricional_cid_gravidade_maps_rows_to_tuples() -> None:
    session = MagicMock()
    exec_result = MagicMock()
    exec_result.fetchall.return_value = [("A", 1), ("B", 2)]
    session.execute.return_value = exec_result

    result = repo.get_nutricional_cid_gravidade(session)

    assert result == [("A", 1), ("B", 2)]
    session.execute.assert_called_once()


def test_get_nutricional_cid_override_returns_empty_list_when_no_rows() -> None:
    session = MagicMock()
    exec_result = MagicMock()
    exec_result.fetchall.return_value = []
    session.execute.return_value = exec_result

    result = repo.get_nutricional_cid_override(session)

    assert result == []


def test_get_nutricional_cid_gravidade_returns_empty_list_when_no_rows() -> None:
    session = MagicMock()
    exec_result = MagicMock()
    exec_result.fetchall.return_value = []
    session.execute.return_value = exec_result

    result = repo.get_nutricional_cid_gravidade(session)

    assert result == []


def test_build_cid_mappings_builds_dicts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(repo, "get_nutricional_cid_override", lambda _s: [("A41", 2)])
    monkeypatch.setattr(repo, "get_nutricional_cid_gravidade", lambda _s: [("A", 1), ("B", 2)])

    mappings = repo.build_cid_mappings(MagicMock())

    assert mappings.overrides == {"A41": 2}
    assert mappings.chapters == {"A": 1, "B": 2}


def test_build_cid_mappings_handles_empty_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(repo, "get_nutricional_cid_override", lambda _s: [])
    monkeypatch.setattr(repo, "get_nutricional_cid_gravidade", lambda _s: [])

    mappings = repo.build_cid_mappings(MagicMock())

    assert mappings.overrides == {}
    assert mappings.chapters == {}


def test_get_cid_mappings_cached_uses_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    build_mock = MagicMock(return_value=SimpleNamespace(overrides={}, chapters={}))
    monkeypatch.setattr(repo, "build_cid_mappings", build_mock)

    first = repo.get_cid_mappings_cached()
    second = repo.get_cid_mappings_cached()

    assert first is second
    build_mock.assert_called_once_with(repo.db.session)

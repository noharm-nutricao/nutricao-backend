"""Unit tests: nutritional D7 service status calculation."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from services.nutritional import nutritional_patient_service as service


def _make_d7(concluido=False, dt_prevista=None):
    """mock d7 object"""
    return SimpleNamespace(
        id=1,
        nratendimento=1001,
        concluido=concluido,
        dt_prevista=dt_prevista or datetime.now(timezone.utc) + timedelta(days=7),
        created_at=datetime(2026, 4, 23, 10, 0, 0),
        updated_at=None,
    )


# --- _calculate_status --------------------------------------------------


def test_status_concluido_when_flag_is_true():
    d7 = _make_d7(concluido=True)
    assert service._calculate_status(d7) == "concluido"


def test_status_pendente_when_more_than_48h_ahead():
    now = datetime.now(timezone.utc)
    d7 = _make_d7(dt_prevista=now + timedelta(hours=49))
    assert service._calculate_status(d7) == "pendente"


def test_status_vencendo_when_less_than_48h_but_still_future():
    now = datetime.now(timezone.utc)
    d7 = _make_d7(dt_prevista=now + timedelta(hours=24))
    assert service._calculate_status(d7) == "vencendo"


def test_status_vencendo_at_exactly_48h_boundary():
    now = datetime.now(timezone.utc)
    # exactly at the boundary (≤ 48h, > now) → vencendo
    d7 = _make_d7(dt_prevista=now + timedelta(hours=48))
    assert service._calculate_status(d7) == "vencendo"


def test_status_vencido_when_past_due():
    now = datetime.now(timezone.utc)
    d7 = _make_d7(dt_prevista=now - timedelta(minutes=1))
    assert service._calculate_status(d7) == "vencido"


def test_status_vencido_when_far_in_past():
    now = datetime.now(timezone.utc)
    d7 = _make_d7(dt_prevista=now - timedelta(days=3))
    assert service._calculate_status(d7) == "vencido"


def test_status_concluido_takes_priority_over_vencido():
    """concluido=True overrides any date condition."""
    now = datetime.now(timezone.utc)
    d7 = _make_d7(concluido=True, dt_prevista=now - timedelta(days=10))
    assert service._calculate_status(d7) == "concluido"


def test_status_handles_naive_dt_prevista():
    """DB may return timezone-naive datetimes; comparison must not raise."""
    naive_future = datetime.utcnow() + timedelta(days=7)
    d7 = _make_d7(dt_prevista=naive_future)
    result = service._calculate_status(d7)
    assert result in {"pendente", "vencendo", "vencido", "concluido"}


# --- _d7_to_dict --------------------------------------------------------


def test_d7_to_dict_contains_required_fields():
    d7 = _make_d7()
    result = service._d7_to_dict(d7)
    assert "id" in result
    assert "dt_prevista" in result
    assert "concluido" in result
    assert "status" in result
    # assert "updated_at" in result


def test_d7_to_dict_status_is_string():
    d7 = _make_d7()
    result = service._d7_to_dict(d7)
    assert isinstance(result["status"], str)


# def test_d7_to_dict_updated_at_none_when_not_set():
#     d7 = _make_d7()
#     d7.updated_at = None
#     result = service._d7_to_dict(d7)
#     assert result["updated_at"] is None


# def test_d7_to_dict_updated_at_iso_when_set():
#     d7 = _make_d7()
#     d7.updated_at = datetime(2026, 4, 26, 9, 0, 0)
#     result = service._d7_to_dict(d7)
#     assert result["updated_at"] == "2026-04-26T09:00:00"


# --- create_d7 ----------------------------------------------------------


def _fake_d7(concluido=False, days_ahead=7):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=3,
        nratendimento=1001,
        concluido=concluido,
        dt_prevista=now + timedelta(days=days_ahead),
        created_at=now,
        updated_at=None,
    )


def test_create_d7_returns_dict_with_status():
    user = SimpleNamespace(id=1)
    fake_d7 = _fake_d7()

    with patch.object(
        service.nutritional_repository,
        "upsert_d7",
        return_value=fake_d7,
    ):
        result = service.create_d7.__wrapped__(nratendimento=1001, user_context=user)

    assert result["id"] == 3
    assert result["status"] == "pendente"
    assert result["concluido"] is False


def test_create_d7_calls_upsert_with_correct_args():
    user = SimpleNamespace(id=7)
    fake_d7 = _fake_d7()
    captured = {}

    def fake_upsert(nratendimento, idusuario):
        captured["nratendimento"] = nratendimento
        captured["idusuario"] = idusuario
        return fake_d7

    with patch.object(service.nutritional_repository, "upsert_d7", side_effect=fake_upsert):
        service.create_d7.__wrapped__(nratendimento=1001, user_context=user)

    assert captured["nratendimento"] == 1001
    assert captured["idusuario"] == 7


# --- get_d7 -------------------------------------------------------------


def test_get_d7_returns_none_when_no_active_d7():
    user = SimpleNamespace(id=1)

    with patch.object(service.nutritional_repository, "get_active_d7", return_value=None):
        result = service.get_d7.__wrapped__(nratendimento=1001, user_context=user)

    assert result is None


def test_get_d7_returns_dict_with_status_when_found():
    user = SimpleNamespace(id=1)
    fake_d7 = _fake_d7(days_ahead=2)

    with patch.object(service.nutritional_repository, "get_active_d7", return_value=fake_d7):
        result = service.get_d7.__wrapped__(nratendimento=1001, user_context=user)

    assert result is not None
    assert result["status"] in {"pendente", "vencendo", "vencido"}


# --- close_d7 -----------------------------------------------------------


def test_close_d7_returns_dict_with_concluido_true():
    user = SimpleNamespace(id=1)
    fake_d7 = _fake_d7(concluido=True)
    fake_d7.updated_at = datetime(2026, 4, 26, 9, 0, 0)

    with patch.object(service.nutritional_repository, "close_d7", return_value=fake_d7):
        result = service.close_d7.__wrapped__(nratendimento=1001, id=3, user_context=user)

    assert result["concluido"] is True
    assert result["status"] == "concluido"
    # assert result["updated_at"] is not None


def test_close_d7_calls_repository_with_correct_args():
    user = SimpleNamespace(id=1)
    fake_d7 = _fake_d7(concluido=True)
    captured = {}

    def fake_close(id, nratendimento):
        captured["id"] = id
        captured["nratendimento"] = nratendimento
        return fake_d7

    with patch.object(service.nutritional_repository, "close_d7", side_effect=fake_close):
        service.close_d7.__wrapped__(nratendimento=1001, id=3, user_context=user)

    assert captured["id"] == 3
    assert captured["nratendimento"] == 1001

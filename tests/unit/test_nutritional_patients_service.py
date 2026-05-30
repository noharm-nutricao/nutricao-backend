"""Unit tests for nutritional_patients_service helper functions."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from models.enums import SegmentTypeEnum
from models.requests.nutritional_patients_request import NutritionalPatientsRequest
from services.nutritional import nutritional_active_patients_service as service


def _call_get_patients(request_data):
    wrapped = getattr(service.get_patients, "__wrapped__", service.get_patients)
    return wrapped(request_data=request_data)

@pytest.mark.parametrize(
    "birthdate, now, expected",
    [
        # Normal case: birthday already passed this year
        (datetime(1959, 3, 15), datetime(2026, 4, 10, tzinfo=timezone.utc), 67),
        # Birthday has NOT happened yet this year
        (datetime(1990, 12, 25), datetime(2026, 4, 10, tzinfo=timezone.utc), 35),
        # Birthday is today
        (datetime(2000, 4, 10), datetime(2026, 4, 10, tzinfo=timezone.utc), 26),
        # Newborn (same year)
        (datetime(2026, 1, 1), datetime(2026, 4, 10, tzinfo=timezone.utc), 0),
        # None birthdate
        (None, datetime(2026, 4, 10, tzinfo=timezone.utc), None),
    ],
)
def test_calculate_age(birthdate, now, expected):
    """_calculate_age retorna idade em anos completos"""
    assert service._calculate_age(birthdate, now) == expected


@pytest.mark.parametrize(
    "admission_date, now, expected",
    [
        # 14 days ago
        (datetime(2026, 3, 27), datetime(2026, 4, 10, tzinfo=timezone.utc), 14),
        # Admitted today
        (datetime(2026, 4, 10), datetime(2026, 4, 10, tzinfo=timezone.utc), 0),
        # 1 day ago
        (datetime(2026, 4, 9), datetime(2026, 4, 10, tzinfo=timezone.utc), 1),
        # None
        (None, datetime(2026, 4, 10, tzinfo=timezone.utc), None),
    ],
)
def test_calculate_days(admission_date, now, expected):
    """_calculate_days retorna dias de internação"""
    assert service._calculate_days(admission_date, now) == expected


@pytest.mark.parametrize(
    "peso, altura, expected",
    [
        # Normal: 58kg, 183cm → 58 / (1.83²) ≈ 17.3
        (58.0, 183.0, 17.3),
        # Normal: 65kg, 160cm → 65 / (1.60²) ≈ 25.4
        (65.0, 160.0, 25.4),
        # Normal: 80kg, 175cm → 80 / (1.75²) ≈ 26.1
        (80.0, 175.0, 26.1),
        # Missing peso
        (None, 183.0, None),
        # Missing altura
        (58.0, None, None),
        # Both missing
        (None, None, None),
        # Zero altura (edge case)
        (58.0, 0, None),
    ],
)
def test_calculate_imc(peso, altura, expected):
    """_calculate_imc calcula IMC corretamente (peso kg, altura cm)"""
    result = service._calculate_imc(peso, altura)
    if expected is None:
        assert result is None
    else:
        assert result == expected


def test_get_patients_maps_icu_row_and_mnutric_payload(monkeypatch):
    fixed_now = datetime(2026, 4, 10, tzinfo=timezone.utc)

    class FrozenDateTime:
        @classmethod
        def now(cls, tz=None):
            return fixed_now if tz else fixed_now.replace(tzinfo=None)

    row = SimpleNamespace(
        id=101,
        leito="U-12",
        ala="UTI",
        fksetor=7,
        nome_setor="UTI Adulto",
        tp_segmento=SegmentTypeEnum.ICU.value,
        dtinternacao=datetime(2026, 4, 8),
        dtnascimento=datetime(1980, 4, 9),
        peso=80.0,
        altura=175.0,
        haval=25.66,
        d7=1,
        sev=None,
        freq_horas="24h",
        glim_diag=None,
        glim_fen=None,
        glim_etiol=None,
        nrs_data={
            "nrs_total": 3,
            "nrs_nut": 1,
            "nrs_doenca": 1,
            "nrs_idade": 1,
        },
        mnutric_data={
            "mn_total": 6,
            "mn_idade": 2,
            "mn_apache": 1,
            "mn_sofa": 1,
            "mn_comor": 1,
            "mn_dias": 1,
            "mn_apache_manual": True,
            "mn_sofa_manual": True,
        },
    )

    captured = {}

    def fake_get_patients(*, setor, ala):
        captured["setor"] = setor
        captured["ala"] = ala
        return [row]

    monkeypatch.setattr(service, "datetime", FrozenDateTime)
    monkeypatch.setattr(
        service.nutritional_patients_repository,
        "get_patients",
        fake_get_patients,
    )

    request_data = NutritionalPatientsRequest(setor=7, ala="UTI")
    result = _call_get_patients(request_data=request_data)

    assert captured == {"setor": 7, "ala": "UTI"}
    assert len(result) == 1

    patient = result[0]
    assert patient["id"] == 101
    assert patient["protocolo"] == "MNUTRIC"
    assert patient["idade"] == 46
    assert patient["dias"] == 2
    assert patient["imc"] == 26.1
    assert patient["haval"] == 25.7
    assert patient["d7"] is True
    assert patient["sev"] == "bx"
    assert patient["freq_horas"] == 24
    assert patient["glim_diag"] is None
    assert patient["glim_fen"] == []
    assert patient["glim_etiol"] == []
    assert patient["pri"] == 1
    assert patient["campo1"] == {
        "mnutric_total": 6,
        "mn_dims": {
            "idade": 2,
            "apache": 1,
            "sofa": 1,
            "comor": 1,
            "dias": 1,
        },
        "nrs_total": 3,
        "nrs_dims": {
            "nut": 1,
            "doenca": 1,
            "idade": 1,
        },
    }


def test_get_patients_maps_nrs_row_defaults_and_unknown_frequency(monkeypatch):
    fixed_now = datetime(2026, 4, 10, tzinfo=timezone.utc)

    class FrozenDateTime:
        @classmethod
        def now(cls, tz=None):
            return fixed_now if tz else fixed_now.replace(tzinfo=None)

    row = SimpleNamespace(
        id=202,
        leito="C-03",
        ala="Clínica",
        fksetor=2,
        nome_setor="Clínica Médica",
        tp_segmento=None,
        dtinternacao=None,
        dtnascimento=None,
        peso=None,
        altura=None,
        haval=None,
        d7=None,
        sev="al",
        freq_horas="10h",
        glim_diag="moderada",
        glim_fen=["perda_peso"],
        glim_etiol=["inflamacao"],
        nrs_data={
            "nrs_total": 4,
            "nrs_nut": 2,
            "nrs_doenca": 1,
            "nrs_idade": 1,
        },
        mnutric_data=None,
    )

    monkeypatch.setattr(service, "datetime", FrozenDateTime)
    monkeypatch.setattr(
        service.nutritional_patients_repository,
        "get_patients",
        lambda *, setor, ala: [row],
    )

    request_data = NutritionalPatientsRequest()
    result = _call_get_patients(request_data=request_data)

    assert len(result) == 1
    patient = result[0]
    assert patient["protocolo"] == "NRS2002"
    assert patient["idade"] is None
    assert patient["dias"] is None
    assert patient["imc"] is None
    assert patient["haval"] is None
    assert patient["d7"] is False
    assert patient["sev"] == "al"
    assert patient["freq_horas"] is None
    assert patient["glim_diag"] == "moderada"
    assert patient["glim_fen"] == ["perda_peso"]
    assert patient["glim_etiol"] == ["inflamacao"]
    assert patient["campo1"] == {
        "nrs_total": 4,
        "nrs_dims": {
            "nut": 2,
            "doenca": 1,
            "idade": 1,
        },
    }


def test_build_campo1_returns_nrs_for_nrs_protocol():
    row = SimpleNamespace(
        nrs_data={
            "nrs_total": 3,
            "nrs_nut": 1,
            "nrs_doenca": 1,
            "nrs_idade": 1,
        },
        mnutric_data=None,
    )

    assert service._build_campo1("NRS2002", row) == {
        "nrs_total": 3,
        "nrs_dims": {
            "nut": 1,
            "doenca": 1,
            "idade": 1,
        },
    }


def test_build_campo1_returns_none_when_no_nrs_for_nrs_protocol():
    row = SimpleNamespace(nrs_data=None, mnutric_data=None)
    assert service._build_campo1("NRS2002", row) is None


def test_build_campo1_includes_nrs_for_mnutric_protocol():
    row = SimpleNamespace(
        nrs_data={
            "nrs_total": 2,
            "nrs_nut": 1,
            "nrs_doenca": 0,
            "nrs_idade": 1,
        },
        mnutric_data={
            "mn_total": 6,
            "mn_idade": 2,
            "mn_apache": 1,
            "mn_sofa": 1,
            "mn_comor": 1,
            "mn_dias": 1,
            "mn_apache_manual": True,
            "mn_sofa_manual": True,
        },
    )

    assert service._build_campo1("MNUTRIC", row) == {
        "mnutric_total": 6,
        "mn_dims": {
            "idade": 2,
            "apache": 1,
            "sofa": 1,
            "comor": 1,
            "dias": 1,
        },
        "nrs_total": 2,
        "nrs_dims": {
            "nut": 1,
            "doenca": 0,
            "idade": 1,
        },
    }


def test_build_campo1_incomplete_mnutric_includes_nrs_when_available():
    row = SimpleNamespace(
        nrs_data={
            "nrs_total": 4,
            "nrs_nut": 2,
            "nrs_doenca": 1,
            "nrs_idade": 1,
        },
        mnutric_data={
            "mn_total": 4,
            "mn_idade": 1,
            "mn_apache": 2,
            "mn_sofa": 1,
            "mn_comor": 0,
            "mn_dias": 2,
            "mn_apache_manual": False,
            "mn_sofa_manual": True,
        },
    )

    assert service._build_campo1("MNUTRIC", row) == {
        "dados_incompletos": True,
        "mn_dims": {
            "idade": 1,
            "apache": None,
            "sofa": None,
            "comor": 0,
            "dias": 2,
        },
        "nrs_total": 4,
        "nrs_dims": {
            "nut": 2,
            "doenca": 1,
            "idade": 1,
        },
    }


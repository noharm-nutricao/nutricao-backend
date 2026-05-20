"""Unit tests: mNUTRIC patient service."""

from datetime import datetime as real_datetime
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from services.nutritional import nutritional_patient_service as service

FIXED_NOW = real_datetime(2026, 4, 12, 10, 0, 0)
ICD_WITHOUT_COMORBITY = ""      # gera comorbity = 0
ICD_WITH_COMORBITY = "A00"      # gera comorbity = 1

class FrozenDateTime:
    @classmethod
    def now(cls):
        return FIXED_NOW


@pytest.fixture(autouse=True)
def freeze_now(monkeypatch):
    monkeypatch.setattr(service, "datetime", FrozenDateTime)


def _patient(age, id_icd, admission_days_ago):
    admission_date = FIXED_NOW - timedelta(days=admission_days_ago)
    return SimpleNamespace(
        birthdate=real_datetime(FIXED_NOW.year - age, 4, 1),
        id_icd=id_icd,
        admissionDate=admission_date,
        utiEntryDate=admission_date,
    )


@pytest.mark.parametrize(
    (
        "age",
        "id_icd",
        "admission_days_ago",
        "apache",
        "sofa",
        "expected",
    ),
    [
        pytest.param(
            40,
            ICD_WITHOUT_COMORBITY,
            0,
            14,
            5,
            {
                "total": 0,
                "age": 0,
                "apache": 0,
                "sofa": 0,
                "comorbity": 0,
                "daysUTI": 0,
                "classify": "bx",
                "dados_incompletos": False,
            },
            id="total-0-bx",
        ),
        pytest.param(
            52,
            ICD_WITHOUT_COMORBITY,
            0,
            14,
            5,
            {
                "total": 1,
                "age": 1,
                "apache": 0,
                "sofa": 0,
                "comorbity": 0,
                "daysUTI": 0,
                "classify": "bx",
                "dados_incompletos": False,
            },
            id="total-1-bx",
        ),
        pytest.param(
            75,
            ICD_WITHOUT_COMORBITY,
            0,
            14,
            5,
            {
                "total": 2,
                "age": 2,
                "apache": 0,
                "sofa": 0,
                "comorbity": 0,
                "daysUTI": 0,
                "classify": "bx",
                "dados_incompletos": False,
            },
            id="total-2-bx",
        ),
        pytest.param(
            52,
            ICD_WITHOUT_COMORBITY,
            0,
            16,
            8,
            {
                "total": 3,
                "age": 1,
                "apache": 1,
                "sofa": 1,
                "comorbity": 0,
                "daysUTI": 0,
                "classify": "md",
                "dados_incompletos": False,
            },
            id="total-3-md",
        ),
        pytest.param(
            75,
            ICD_WITHOUT_COMORBITY,
            0,
            16,
            8,
            {
                "total": 4,
                "age": 2,
                "apache": 1,
                "sofa": 1,
                "comorbity": 0,
                "daysUTI": 0,
                "classify": "md",
                "dados_incompletos": False,
            },
            id="total-4-md",
        ),
        pytest.param(
            75,
            ICD_WITHOUT_COMORBITY,
            0,
            22,
            8,
            {
                "total": 5,
                "age": 2,
                "apache": 2,
                "sofa": 1,
                "comorbity": 0,
                "daysUTI": 0,
                "classify": "al",
                "dados_incompletos": False,
            },
            id="total-5-al",
        ),
        pytest.param(
            75,
            ICD_WITHOUT_COMORBITY,
            2,
            22,
            8,
            {
                "total": 6,
                "age": 2,
                "apache": 2,
                "sofa": 1,
                "comorbity": 0,
                "daysUTI": 1,
                "classify": "al",
                "dados_incompletos": False,
            },
            id="total-6-al",
        ),
        pytest.param(
            75,
            ICD_WITH_COMORBITY,
            2,
            22,
            8,
            {
                "total": 7,
                "age": 2,
                "apache": 2,
                "sofa": 1,
                "comorbity": 1,
                "daysUTI": 1,
                "classify": "cr",
                "dados_incompletos": False,
            },
            id="total-7-cr",
        ),
        pytest.param(
            75,
            ICD_WITH_COMORBITY,
            2,
            28,
            8,
            {
                "total": 8,
                "age": 2,
                "apache": 3,
                "sofa": 1,
                "comorbity": 1,
                "daysUTI": 1,
                "classify": "cr",
                "dados_incompletos": False,
            },
            id="total-8-cr",
        ),
        pytest.param(
            75,
            ICD_WITH_COMORBITY,
            2,
            28,
            10,
            {
                "total": 9,
                "age": 2,
                "apache": 3,
                "sofa": 2,
                "comorbity": 1,
                "daysUTI": 1,
                "classify": "cr",
                "dados_incompletos": False,
            },
            id="total-9-cr",
        ),
        pytest.param(
            40,
            ICD_WITHOUT_COMORBITY,
            0,
            None,
            None,
            {
                "total": 0,
                "age": 0,
                "apache": 0,
                "sofa": 0,
                "comorbity": 0,
                "daysUTI": 0,
                "classify": None,
                "dados_incompletos": True,
            },
            id="dados-incompletos-apache-sofa-none",
        ),
    ],
)
def test_calculate_mnutric(age, id_icd, admission_days_ago, apache, sofa, expected):
    """calculate_mnutric: returns expected result for documented scenarios"""
    patient = _patient(
        age=age,
        id_icd=id_icd,
        admission_days_ago=admission_days_ago,
    )

    result = service.calculate_mnutric(patient, apache=apache, sofa=sofa)

    assert result == expected


def test_recalculate_mnutric_restores_dimension_scores_and_normalizes_patient():
    source_patient = SimpleNamespace(
        nratendimento=123,
        dtnascimento=real_datetime(1950, 4, 1),
        dtinternacao=FIXED_NOW - timedelta(days=2),
        dt_ultima_transferencia=FIXED_NOW - timedelta(days=1),
        idcid="A00",
    )
    screening = SimpleNamespace(mn_apache=2, mn_sofa=1)

    with patch(
        "services.nutritional.nutritional_patient_service.nutritional_repository.get_saved_mnutric",
        return_value=screening,
    ), patch(
        "services.nutritional.nutritional_patient_service.save_manual_mnutric",
    ):
        result = service.recalculate_mnutric(source_patient)

    assert result["dados_incompletos"] is False
    assert result["apache"] == 2
    assert result["sofa"] == 1
    assert result["comorbity"] == 1
    assert result["age"] == 2
    assert result["daysUTI"] == 0


@pytest.mark.parametrize(
    "patient",
    [
        pytest.param(
            SimpleNamespace(
                nratendimento=None,
                dtnascimento=real_datetime(1950, 4, 1),
                dtinternacao=FIXED_NOW - timedelta(days=2),
            ),
            id="missing-admission-number",
        ),
        pytest.param(
            SimpleNamespace(
                nratendimento=123,
                dtnascimento=None,
                dtinternacao=FIXED_NOW - timedelta(days=2),
            ),
            id="missing-birthdate",
        ),
        pytest.param(
            SimpleNamespace(
                nratendimento=123,
                dtnascimento=real_datetime(1950, 4, 1),
                dtinternacao=None,
            ),
            id="missing-admission-date",
        ),
    ],
)
def test_recalculate_mnutric_returns_none_when_required_fields_are_missing(patient):
    assert service.recalculate_mnutric(patient) is None


def test_recalculate_mnutric_returns_dados_incompletos_when_screening_is_missing():
    source_patient = SimpleNamespace(
        nratendimento=123,
        dtnascimento=real_datetime(1950, 4, 1),
        dtinternacao=FIXED_NOW - timedelta(days=2),
        idcid="",
    )

    with patch(
        "services.nutritional.nutritional_patient_service.nutritional_repository.get_saved_mnutric",
        return_value=None,
    ), patch(
        "services.nutritional.nutritional_patient_service.save_manual_mnutric",
    ):
        result = service.recalculate_mnutric(source_patient)

    assert result["dados_incompletos"] is True
    assert result["classify"] is None
    assert result["apache"] == 0
    assert result["sofa"] == 0

"""Unit tests: mNUTRIC patient service."""

from datetime import datetime as real_datetime
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

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
        utiEntryDate=FIXED_NOW,
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
    screening = SimpleNamespace(mn_apache=2, mn_sofa=1, mn_apache_manual=True, mn_sofa_manual=True)

    with patch(
        "services.nutritional.nutritional_patient_service.nutritional_repository.get_saved_mnutric",
        return_value=screening,
    ), patch(
        "services.nutritional.nutritional_patient_service.nutritional_repository.update_mnutric_scores",
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
        "services.nutritional.nutritional_patient_service.nutritional_repository.update_mnutric_scores",
    ):
        result = service.recalculate_mnutric(source_patient)

    assert result["dados_incompletos"] is True
    assert result["classify"] is None
    assert result["apache"] is None
    assert result["sofa"] is None


# ---------------------------------------------------------------------------
# _restore_apache_ii_from_dimension
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "score,expected",
    [
        (None, None),
        (0, 0),
        (1, 15),
        (2, 20),
        (3, 28),
        (10, 10),  # unknown → passthrough
    ],
)
def test_restore_apache_ii_from_dimension(score, expected):
    assert service._restore_apache_ii_from_dimension(score) == expected


# ---------------------------------------------------------------------------
# _restore_sofa_from_dimension
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "score,expected",
    [
        (None, None),
        (0, 0),
        (1, 6),
        (2, 10),
        (5, 5),  # unknown → passthrough
    ],
)
def test_restore_sofa_from_dimension(score, expected):
    assert service._restore_sofa_from_dimension(score) == expected


# ---------------------------------------------------------------------------
# calculate_mnutric: save error handling
# ---------------------------------------------------------------------------


def test_calculate_mnutric_logs_error_and_still_returns_when_save_fails():
    patient = SimpleNamespace(
        admissionNumber=42,
        birthdate=real_datetime(1970, 1, 1),
        id_icd="",
        admissionDate=FIXED_NOW,
        utiEntryDate=FIXED_NOW,
    )

    with patch(
        "services.nutritional.nutritional_patient_service.save_manual_mnutric",
        side_effect=RuntimeError("DB error"),
    ):
        result = service.calculate_mnutric(patient, apache=0, sofa=0)

    assert result is not None
    assert "total" in result


def test_calculate_mnutric_skips_save_when_admission_number_is_none():
    patient = SimpleNamespace(
        admissionNumber=None,
        birthdate=real_datetime(1970, 1, 1),
        id_icd="",
        admissionDate=FIXED_NOW,
        utiEntryDate=FIXED_NOW,
    )

    with patch(
        "services.nutritional.nutritional_patient_service.save_manual_mnutric",
    ) as mock_save:
        service.calculate_mnutric(patient, apache=0, sofa=0)

    mock_save.assert_not_called()


# ---------------------------------------------------------------------------
# get_patients: exception path (bypass @has_permission via __wrapped__)
# ---------------------------------------------------------------------------


def test_get_patients_raises_when_repository_fails():
    with patch(
        "services.nutritional.nutritional_patient_service.nutritional_repository.get_patients_repository",
        side_effect=RuntimeError("DB down"),
    ):
        with pytest.raises(Exception, match="Estamos com problemas"):
            service.get_patients.__wrapped__()


# ---------------------------------------------------------------------------
# _handle_d7_closure
# ---------------------------------------------------------------------------


class TestHandleD7Closure:
    def test_non_d7_prox_visita_does_nothing(self):
        with patch(
            "services.nutritional.nutritional_patient_service.nutritional_repository.get_active_d7"
        ) as mock_get, patch(
            "services.nutritional.nutritional_patient_service.nutritional_repository.create_d7"
        ) as mock_create:
            service._handle_d7_closure(nratendimento=1, prox_visita="24h", idusuario=1)

        mock_get.assert_not_called()
        mock_create.assert_not_called()

    def test_d7_prox_visita_closes_active_and_creates_new(self):
        mock_active_d7 = MagicMock()
        mock_active_d7.id = 99

        with patch(
            "services.nutritional.nutritional_patient_service.nutritional_repository.get_active_d7",
            return_value=mock_active_d7,
        ) as mock_get, patch(
            "services.nutritional.nutritional_patient_service.nutritional_repository.close_d7"
        ) as mock_close, patch(
            "services.nutritional.nutritional_patient_service.nutritional_repository.create_d7"
        ) as mock_create:
            service._handle_d7_closure(nratendimento=1, prox_visita="D7", idusuario=7)

        mock_get.assert_called_once_with(1)
        mock_close.assert_called_once_with(id=99, nratendimento=1)
        mock_create.assert_called_once()
        _, kwargs = mock_create.call_args
        assert kwargs["nratendimento"] == 1
        assert kwargs["idusuario"] == 7

    def test_d7_prox_visita_creates_new_when_no_active_d7(self):
        with patch(
            "services.nutritional.nutritional_patient_service.nutritional_repository.get_active_d7",
            return_value=None,
        ), patch(
            "services.nutritional.nutritional_patient_service.nutritional_repository.close_d7"
        ) as mock_close, patch(
            "services.nutritional.nutritional_patient_service.nutritional_repository.create_d7"
        ) as mock_create:
            service._handle_d7_closure(nratendimento=2, prox_visita="D7", idusuario=5)

        mock_close.assert_not_called()
        mock_create.assert_called_once()
        _, kwargs = mock_create.call_args
        assert kwargs["nratendimento"] == 2
        assert kwargs["idusuario"] == 5

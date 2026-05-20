from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from services.nutritional import nutritional_nrs_service as svc


@pytest.fixture
def patient() -> SimpleNamespace:
    return SimpleNamespace(
        admissionNumber=1,
        id_icd="A123",
        birthdate=datetime(1950, 5, 20),
    )


@pytest.fixture
def triagem() -> SimpleNamespace:
    return SimpleNamespace(
        id=10,
        nratendimento=1,
        nrs_ref_at=datetime(2024, 1, 1, 10, 0, 0),
    )


@pytest.fixture
def nrs_row() -> SimpleNamespace:
    return SimpleNamespace(
        triagem_imc_baixo=True,
        triagem_perda_peso=False,
        triagem_ingestao_reduzida=False,
        triagem_doenca_grave=False,
        score_comprometimento=2,
        updated_at=datetime(2025, 1, 1, 10, 0, 0),
    )


@pytest.fixture
def cid_mappings() -> svc.CidMappings:
    return svc.CidMappings(
        overrides={"A12": 2, "B34": 1},
        chapters={"A": 1, "B": 2, "C": 0},
    )


# 1) score_nrs_component_a

def test_score_nrs_component_a_returns_none_when_row_is_none() -> None:
    assert svc.score_nrs_component_a(None) is None


def test_score_nrs_component_a_returns_zero_when_no_risk_flags() -> None:
    row = SimpleNamespace(
        triagem_imc_baixo=False,
        triagem_perda_peso=False,
        triagem_ingestao_reduzida=False,
        triagem_doenca_grave=False,
        score_comprometimento=3,
    )
    assert svc.score_nrs_component_a(row) == 0


def test_score_nrs_component_a_returns_score_when_any_risk_flag_true() -> None:
    row = SimpleNamespace(
        triagem_imc_baixo=False,
        triagem_perda_peso=True,
        triagem_ingestao_reduzida=False,
        triagem_doenca_grave=False,
        score_comprometimento=2,
    )
    assert svc.score_nrs_component_a(row) == 2


def test_score_nrs_component_a_defaults_to_zero_when_score_missing() -> None:
    row = SimpleNamespace(
        triagem_imc_baixo=True,
        triagem_perda_peso=False,
        triagem_ingestao_reduzida=False,
        triagem_doenca_grave=False,
    )
    assert svc.score_nrs_component_a(row) == 0


# 2) _normalize_department_name

@pytest.mark.parametrize(
    "raw_name,expected",
    [
        (" UTI  Adulto ", "uti adulto"),
        ("Unidade de Terapia Intensiva", "unidade de terapia intensiva"),
        ("Unidade de Tratamento IntensívA", "unidade de tratamento intensiva"),
        ("  Clínica   Médica  ", "clinica medica"),
        ("Centro\tde\nTerapia   Intensiva", "centro de terapia intensiva"),
    ],
)
def test_normalize_department_name(raw_name: str, expected: str) -> None:
    assert svc._normalize_department_name(raw_name) == expected


# 3) is_uti_helper

@pytest.mark.parametrize(
    "department,expected",
    [
        (None, False),
        ("", False),
        ("UTI", True),
        ("u.t.i", True),
        ("U-T-I", True),
        ("CTI", True),
        ("UTIN", True),
        ("Unidade de Terapia Intensiva", True),
        ("Centro de Tratamento Intensivo", True),
        ("Cuidados intensivos", True),
        ("UTI pediátrica", True),
        ("UTI neonatal", True),
        ("Neo UTI", True),
        ("Enfermaria", False),
        ("Clínica médica", False),
        ("Ambulatório", False),
    ],
)
def test_is_uti_helper_parametrized(department: str, expected: bool) -> None:
    assert svc.is_uti_helper(department) is expected


# 4) is_uti_wrapper

def test_is_uti_wrapper_returns_true_when_segment_is_icu() -> None:
    get_segment_type_fn = MagicMock(return_value=3)
    get_department_fn = MagicMock()

    result = svc.is_uti_wrapper(321, get_segment_type_fn, get_department_fn)

    assert result is True
    get_segment_type_fn.assert_called_once_with(321)
    get_department_fn.assert_not_called()


def test_is_uti_wrapper_returns_false_when_segment_is_not_icu() -> None:
    get_segment_type_fn = MagicMock(return_value=1)
    get_department_fn = MagicMock()

    result = svc.is_uti_wrapper(321, get_segment_type_fn, get_department_fn)

    assert result is False
    get_segment_type_fn.assert_called_once_with(321)
    get_department_fn.assert_not_called()


def test_is_uti_wrapper_falls_back_to_department_when_segment_missing() -> None:
    get_segment_type_fn = MagicMock(return_value=None)
    get_department_fn = MagicMock(return_value="UTI adulto")

    result = svc.is_uti_wrapper(321, get_segment_type_fn, get_department_fn)

    assert result is True
    get_segment_type_fn.assert_called_once_with(321)
    get_department_fn.assert_called_once_with(321)


def test_is_uti_wrapper_fallback_returns_false_when_department_missing() -> None:
    get_segment_type_fn = MagicMock(return_value=None)
    get_department_fn = MagicMock(return_value=None)

    result = svc.is_uti_wrapper(321, get_segment_type_fn, get_department_fn)

    assert result is False
    get_segment_type_fn.assert_called_once_with(321)


# 5) is_uti

def test_is_uti_delegates_to_wrapper(monkeypatch: pytest.MonkeyPatch) -> None:
    wrapper_mock = MagicMock(return_value=True)
    monkeypatch.setattr(svc, "is_uti_wrapper", wrapper_mock)

    result = svc.is_uti(99)

    assert result is True
    wrapper_mock.assert_called_once_with(
        99,
        svc.get_patient_segment_type,
        svc.get_patient_department,
    )


# 6) score_nrs_component_b

def test_score_nrs_component_b_delegates_to_internal(monkeypatch: pytest.MonkeyPatch) -> None:
    internal_mock = MagicMock(return_value=2)
    monkeypatch.setattr(svc, "_score_nrs_component_b", internal_mock)

    result = svc.score_nrs_component_b(10, "A123")

    assert result == 2
    internal_mock.assert_called_once_with(10, "A123", svc.is_uti, svc.get_cid_mappings_cached)


# 7) _score_nrs_component_b

def test_internal_component_b_returns_3_for_icu() -> None:
    is_uti_fn = MagicMock(return_value=True)
    get_mappings_fn = MagicMock()

    result = svc._score_nrs_component_b(1, "A123", is_uti_fn, get_mappings_fn)

    assert result == 3
    get_mappings_fn.assert_not_called()


def test_internal_component_b_returns_0_for_empty_cid() -> None:
    is_uti_fn = MagicMock(return_value=False)
    get_mappings_fn = MagicMock()

    result = svc._score_nrs_component_b(1, "", is_uti_fn, get_mappings_fn)

    assert result == 0
    get_mappings_fn.assert_not_called()


def test_internal_component_b_uses_prefix_override(cid_mappings: svc.CidMappings) -> None:
    is_uti_fn = MagicMock(return_value=False)
    get_mappings_fn = MagicMock(return_value=cid_mappings)

    result = svc._score_nrs_component_b(1, "A1299", is_uti_fn, get_mappings_fn)

    assert result == 2


def test_internal_component_b_falls_back_to_chapter_score(cid_mappings: svc.CidMappings) -> None:
    is_uti_fn = MagicMock(return_value=False)
    get_mappings_fn = MagicMock(return_value=cid_mappings)

    result = svc._score_nrs_component_b(1, "C991", is_uti_fn, get_mappings_fn)

    assert result == 0


def test_internal_component_b_returns_zero_when_chapter_not_mapped() -> None:
    is_uti_fn = MagicMock(return_value=False)
    get_mappings_fn = MagicMock(return_value=svc.CidMappings(overrides={}, chapters={}))

    result = svc._score_nrs_component_b(1, "Z991", is_uti_fn, get_mappings_fn)

    assert result == 0


def test_internal_component_b_len_lt_3_uses_chapter_score(
    cid_mappings: svc.CidMappings,
) -> None:
    is_uti_fn = MagicMock(return_value=False)
    get_mappings_fn = MagicMock(return_value=cid_mappings)

    result = svc._score_nrs_component_b(1, "A", is_uti_fn, get_mappings_fn)

    assert result == 1


# 8) calculate_age

def test_calculate_age_with_mocked_now_year(monkeypatch: pytest.MonkeyPatch) -> None:
    class FixedDateTime:
        @classmethod
        def now(cls) -> datetime:
            return datetime(2026, 4, 11, 12, 0, 0)

    monkeypatch.setattr(svc, "datetime", FixedDateTime)

    assert svc.calculate_age(datetime(2000, 10, 1, 0, 0, 0)) == 26


# 9) build_nrs_update

def test_build_nrs_update_with_nrs_row_uses_row_timestamp(
    patient: SimpleNamespace,
    triagem: SimpleNamespace,
    nrs_row: SimpleNamespace,
) -> None:
    now = datetime(2026, 4, 11, 12, 0, 0)
    score_a_fn = MagicMock(return_value=2)
    score_b_fn = MagicMock(return_value=1)
    calc_age_fn = MagicMock(return_value=80)
    now_fn = MagicMock(return_value=now)

    dto = svc.build_nrs_update(
        patient,
        triagem,
        nrs_row,
        score_nrs_component_a_fn=score_a_fn,
        score_nrs_component_b_fn=score_b_fn,
        calc_age_fn=calc_age_fn,
        now_fn=now_fn,
    )

    assert dto.id == triagem.id
    assert dto.nrs_nut == 2
    assert dto.nrs_doenca == 1
    assert dto.nrs_idade == 1
    assert dto.nrs_total == 4
    assert dto.nrs_completo is True
    assert dto.nrs_ref_at == nrs_row.updated_at
    assert dto.calculado_at == now
    score_a_fn.assert_called_once_with(nrs_row)
    score_b_fn.assert_called_once_with(patient.admissionNumber, patient.id_icd)


def test_build_nrs_update_without_nrs_row_uses_triagem_ref(
    patient: SimpleNamespace,
    triagem: SimpleNamespace,
) -> None:
    now = datetime(2026, 4, 11, 13, 0, 0)
    score_a_fn = MagicMock(return_value=3)
    score_b_fn = MagicMock(return_value=2)
    calc_age_fn = MagicMock(return_value=40)
    now_fn = MagicMock(return_value=now)

    dto = svc.build_nrs_update(
        patient,
        triagem,
        None,
        score_nrs_component_a_fn=score_a_fn,
        score_nrs_component_b_fn=score_b_fn,
        calc_age_fn=calc_age_fn,
        now_fn=now_fn,
    )

    assert dto.id == triagem.id
    assert dto.nrs_nut is None
    assert dto.nrs_doenca == 2
    assert dto.nrs_idade == 0
    assert dto.nrs_total == 2
    assert dto.nrs_completo is False
    assert dto.nrs_ref_at == triagem.nrs_ref_at
    assert dto.calculado_at == now
    score_a_fn.assert_not_called()


# 10) __recalculate_nrs

def test_recalculate_internal_calls_dependencies_and_updates(
    patient: SimpleNamespace,
    triagem: SimpleNamespace,
    nrs_row: SimpleNamespace,
) -> None:
    get_or_create_fn = MagicMock(return_value=triagem)
    get_nrs_fn = MagicMock(return_value=nrs_row)
    updater_fn = MagicMock()
    score_a_fn = MagicMock(return_value=2)
    score_b_fn = MagicMock(return_value=1)
    calc_age_fn = MagicMock(return_value=80)
    now = datetime(2026, 4, 11, 15, 0, 0)
    now_fn = MagicMock(return_value=now)

    svc.__recalculate_nrs(
        patient,
        get_or_create_triagem_fn=get_or_create_fn,
        nutritional_nrs_repo_fn=get_nrs_fn,
        updater_func=updater_fn,
        score_nrs_component_a_fn=score_a_fn,
        score_nrs_component_b_fn=score_b_fn,
        calc_age_fn=calc_age_fn,
        now_fn=now_fn,
    )

    get_or_create_fn.assert_called_once_with(patient.admissionNumber)
    get_nrs_fn.assert_called_once_with(patient.admissionNumber)
    updater_fn.assert_called_once()

    updated_triagem, dto = updater_fn.call_args.args
    assert updated_triagem is triagem
    assert dto.nrs_nut == 2
    assert dto.nrs_doenca == 1
    assert dto.nrs_idade == 1
    assert dto.nrs_total == 4
    assert dto.nrs_completo is True


def test_recalculate_internal_without_nrs_marks_incomplete(
    patient: SimpleNamespace,
    triagem: SimpleNamespace,
) -> None:
    get_or_create_fn = MagicMock(return_value=triagem)
    get_nrs_fn = MagicMock(return_value=None)
    updater_fn = MagicMock()
    score_a_fn = MagicMock(return_value=2)
    score_b_fn = MagicMock(return_value=0)
    calc_age_fn = MagicMock(return_value=30)
    now_fn = MagicMock(return_value=datetime(2026, 4, 11, 16, 0, 0))

    svc.__recalculate_nrs(
        patient,
        get_or_create_triagem_fn=get_or_create_fn,
        nutritional_nrs_repo_fn=get_nrs_fn,
        updater_func=updater_fn,
        score_nrs_component_a_fn=score_a_fn,
        score_nrs_component_b_fn=score_b_fn,
        calc_age_fn=calc_age_fn,
        now_fn=now_fn,
    )

    _, dto = updater_fn.call_args.args
    assert dto.nrs_nut is None
    assert dto.nrs_completo is False
    assert dto.nrs_total == 0
    score_a_fn.assert_not_called()


# 11) recalculate_nrs

def test_recalculate_nrs_delegates_to_internal(monkeypatch: pytest.MonkeyPatch, patient: SimpleNamespace) -> None:
    internal_mock = MagicMock(return_value=None)
    monkeypatch.setattr(svc, "__recalculate_nrs", internal_mock)

    result = svc.recalculate_nrs(patient)

    assert result is None
    internal_mock.assert_called_once_with(patient)


# Casos de Teste Obrigatórios (matriz funcional de admissão)


def _classificacao_por_total(nrs_total: int) -> str:
    return "al" if nrs_total >= 3 else "bx"


@pytest.mark.parametrize(
    "cenario,score_comprometimento,flags,comp_b,idade,expected_a,expected_b,expected_c,expected_total,expected_classe,expected_completo",
    [
        (
            "Traz Score de Comprometimento = 3 | Não (CID Leve) | 72 anos",
            3,
            dict(
                triagem_imc_baixo=True,
                triagem_perda_peso=False,
                triagem_ingestao_reduzida=False,
                triagem_doenca_grave=False,
            ),
            0,
            72,
            3,
            0,
            1,
            4,
            "al",
            True,
        ),
        (
            "Todas as 4 respostas da Triagem Inicial = False | Não (CID Leve) | 50 anos",
            3,
            dict(
                triagem_imc_baixo=False,
                triagem_perda_peso=False,
                triagem_ingestao_reduzida=False,
                triagem_doenca_grave=False,
            ),
            0,
            50,
            0,
            0,
            0,
            0,
            "bx",
            True,
        ),
        (
            "Não enviou formulário (Registro Inexistente) | Sim (UTI = 3pts) | 71 anos",
            None,
            None,
            3,
            71,
            None,
            3,
            1,
            4,
            "al",
            False,
        ),
        (
            "Traz Score de Comprometimento = 1 | Sim (UTI = 3pts) | 65 anos",
            1,
            dict(
                triagem_imc_baixo=True,
                triagem_perda_peso=False,
                triagem_ingestao_reduzida=False,
                triagem_doenca_grave=False,
            ),
            3,
            65,
            1,
            3,
            0,
            4,
            "al",
            True,
        ),
    ],
)
def test_casos_obrigatorios_nrs(
    cenario: str,
    score_comprometimento: int | None,
    flags: dict | None,
    comp_b: int,
    idade: int,
    expected_a: int | None,
    expected_b: int,
    expected_c: int,
    expected_total: int,
    expected_classe: str,
    expected_completo: bool,
) -> None:
    triagem = SimpleNamespace(
        id=900,
        nratendimento=1,
        nrs_ref_at=datetime(2024, 1, 1, 10, 0, 0),
    )
    patient = SimpleNamespace(
        admissionNumber=1,
        id_icd="A001",
        birthdate=datetime(2000, 1, 1),
    )

    if flags is None:
        nrs_row = None
    else:
        nrs_row = SimpleNamespace(
            **flags,
            score_comprometimento=score_comprometimento,
            updated_at=datetime(2025, 1, 1, 10, 0, 0),
        )

    dto = svc.build_nrs_update(
        patient,
        triagem,
        nrs_row,
        score_nrs_component_a_fn=svc.score_nrs_component_a,
        score_nrs_component_b_fn=lambda admission_number, cid: comp_b,
        calc_age_fn=lambda _: idade,
        now_fn=lambda: datetime(2026, 4, 11, 12, 0, 0),
    )

    assert dto.nrs_nut == expected_a, cenario
    assert dto.nrs_doenca == expected_b, cenario
    assert dto.nrs_idade == expected_c, cenario
    assert dto.nrs_total == expected_total, cenario
    assert _classificacao_por_total(dto.nrs_total) == expected_classe, cenario
    assert dto.nrs_completo is expected_completo, cenario


def test_score_nrs_component_a_when_all_triagem_fields_missing_returns_zero_with_risk_false() -> None:
    row = SimpleNamespace(score_comprometimento=3)

    result = svc.score_nrs_component_a(row)

    assert result == 0


@pytest.mark.parametrize(
    "department",
    [
        "UTI coronariana",
        "unidade de cuidados intensivos",
        "Unidade de Tratamento Intensivo",
        "Terapia Intensiva",
    ],
)
def test_is_uti_helper_additional_positive_patterns(department: str) -> None:
    assert svc.is_uti_helper(department) is True


@pytest.mark.parametrize(
    "department",
    [
        "Centro Cirúrgico",
        "Unidade de Internação",
        "Hospital Dia",
    ],
)
def test_is_uti_helper_additional_negative_patterns(department: str) -> None:
    assert svc.is_uti_helper(department) is False


def test_internal_component_b_uses_uppercase_chapter_for_lowercase_cid() -> None:
    is_uti_fn = MagicMock(return_value=False)
    mappings = svc.CidMappings(overrides={}, chapters={"A": 2})
    get_mappings_fn = MagicMock(return_value=mappings)

    result = svc._score_nrs_component_b(1, "a991", is_uti_fn, get_mappings_fn)

    assert result == 2


def test_internal_component_b_prefers_override_over_chapter() -> None:
    is_uti_fn = MagicMock(return_value=False)
    mappings = svc.CidMappings(overrides={"A12": 1}, chapters={"A": 3})
    get_mappings_fn = MagicMock(return_value=mappings)

    result = svc._score_nrs_component_b(1, "A123", is_uti_fn, get_mappings_fn)

    assert result == 1


def test_build_nrs_update_with_nrs_row_and_none_score_component_a() -> None:
    patient = SimpleNamespace(
        admissionNumber=1,
        id_icd="A123",
        birthdate=datetime(1960, 1, 1),
    )
    triagem = SimpleNamespace(id=10, nrs_ref_at=datetime(2024, 1, 1, 10, 0, 0))
    nrs_row = SimpleNamespace(updated_at=datetime(2025, 1, 1, 10, 0, 0))

    dto = svc.build_nrs_update(
        patient,
        triagem,
        nrs_row,
        score_nrs_component_a_fn=lambda _row: None,
        score_nrs_component_b_fn=lambda _adm, _cid: 2,
        calc_age_fn=lambda _birthdate: 80,
        now_fn=lambda: datetime(2026, 4, 11, 12, 0, 0),
    )

    assert dto.nrs_nut is None
    assert dto.nrs_doenca == 2
    assert dto.nrs_idade == 1
    assert dto.nrs_total == 3
    assert dto.nrs_completo is False
    assert dto.nrs_ref_at == nrs_row.updated_at


def test_recalculate_internal_passes_nrs_row_to_component_a_function() -> None:
    patient = SimpleNamespace(
        admissionNumber=1,
        id_icd="A123",
        birthdate=datetime(1960, 1, 1),
    )
    triagem = SimpleNamespace(id=10, nrs_ref_at=datetime(2024, 1, 1, 10, 0, 0))
    nrs_row = SimpleNamespace(updated_at=datetime(2025, 1, 1, 10, 0, 0))

    get_or_create_fn = MagicMock(return_value=triagem)
    get_nrs_fn = MagicMock(return_value=nrs_row)
    updater_fn = MagicMock()
    score_a_fn = MagicMock(return_value=1)

    svc.__recalculate_nrs(
        patient,
        get_or_create_triagem_fn=get_or_create_fn,
        nutritional_nrs_repo_fn=get_nrs_fn,
        updater_func=updater_fn,
        score_nrs_component_a_fn=score_a_fn,
        score_nrs_component_b_fn=lambda _adm, _cid: 0,
        calc_age_fn=lambda _birthdate: 50,
        now_fn=lambda: datetime(2026, 4, 11, 12, 0, 0),
    )

    score_a_fn.assert_called_once_with(nrs_row)

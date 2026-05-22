"""Unit tests for nutritional_patients_repository.get_patients."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from sqlalchemy import func, literal
from sqlalchemy.sql.elements import Case

from models.enums import SegmentTypeEnum
from models.nutritional import NutritionalAssessment, NutritionalScreening
from models.prescription import Patient
from models.segment import Segment
from repository import nutritional_patients_repository as repo


def _make_subquery_builder(scalar_result):
    """Create a fluent mock for subquery chains ending in scalar_subquery()."""
    subquery = MagicMock()
    subquery.filter.return_value = subquery
    subquery.correlate.return_value = subquery
    subquery.order_by.return_value = subquery
    subquery.limit.return_value = subquery
    subquery.scalar_subquery.return_value = scalar_result
    return subquery


def _make_last_assessment_builder():
    """Create a fluent mock for last_assessment ordered subquery."""
    grouped = MagicMock()
    grouped.distinct.return_value = grouped
    grouped.group_by.return_value = grouped
    grouped.order_by.return_value = grouped

    subquery = MagicMock()
    grouped.subquery.return_value = subquery
    return grouped, subquery


def _make_main_query(rows):
    """Create a fluent mock for the main SELECT query chain."""
    main_query = MagicMock()
    main_query.select_from.return_value = main_query
    main_query.outerjoin.return_value = main_query
    main_query.filter.return_value = main_query
    main_query.order_by.return_value = main_query
    main_query.all.return_value = rows
    return main_query


def _setup_session(monkeypatch, rows):
    """Patch repo.db.session with mocked query builders."""
    main_query = _make_main_query(rows)
    last_assessment_query, last_assessment_subquery = _make_last_assessment_builder()

    mocked_session = MagicMock()
    mocked_session.query.side_effect = [
        _make_subquery_builder(func.now()),  # haval_subq
        _make_subquery_builder(literal(0)),  # d7_subq
        last_assessment_query,  # last_assessment grouped subquery
        _make_subquery_builder(literal(None)),  # sev_subq
        _make_subquery_builder(literal(None)),  # nrs_total_subq
        _make_subquery_builder(literal(None)),  # mnutric_total_subq
        _make_subquery_builder(literal(None)),  # glim_diag_subq
        _make_subquery_builder(literal(None)),  # glim_fen_subq
        _make_subquery_builder(literal(None)),  # glim_etiol_subq
        _make_subquery_builder(literal(None)),  # nrs_data_subq
        _make_subquery_builder(literal(None)),  # mnutric_data_subq
        main_query,
    ]

    monkeypatch.setattr(repo.db, "session", mocked_session)
    return mocked_session, main_query, last_assessment_query, last_assessment_subquery


def _setup_session_with_sev_subq(monkeypatch, rows):
    """Patch repo.db.session and return the sev subquery builder for inspection."""
    main_query = _make_main_query(rows)
    last_assessment_query, last_assessment_subquery = _make_last_assessment_builder()
    sev_subq_builder = _make_subquery_builder(literal(None))

    mocked_session = MagicMock()
    mocked_session.query.side_effect = [
        _make_subquery_builder(func.now()),  # haval_subq
        _make_subquery_builder(literal(0)),  # d7_subq
        last_assessment_query,  # last_assessment grouped subquery
        sev_subq_builder,  # sev_subq
        _make_subquery_builder(literal(None)),  # nrs_total_subq
        _make_subquery_builder(literal(None)),  # mnutric_total_subq
        _make_subquery_builder(literal(None)),  # glim_diag_subq
        _make_subquery_builder(literal(None)),  # glim_fen_subq
        _make_subquery_builder(literal(None)),  # glim_etiol_subq
        _make_subquery_builder(literal(None)),  # nrs_data_subq
        _make_subquery_builder(literal(None)),  # mnutric_data_subq
        main_query,
    ]

    monkeypatch.setattr(repo.db, "session", mocked_session)
    return (
        mocked_session,
        main_query,
        last_assessment_query,
        last_assessment_subquery,
        sev_subq_builder,
    )


def _get_filter(main_query, index):
    return main_query.filter.call_args_list[index].args[0]


def _assert_same_column(expression_column, model_attr):
    model_column = model_attr.property.columns[0]
    assert expression_column.name == model_column.name
    assert expression_column.table.name == model_column.table.name


def test_get_patients_without_optional_filters(monkeypatch):
    rows = [SimpleNamespace(id=1)]
    mocked_session, main_query, _, last_assessment_subquery = _setup_session(
        monkeypatch, rows
    )

    result = repo.get_patients()

    assert result == rows
    assert mocked_session.query.call_count == 12
    main_query.select_from.assert_called_once_with(Patient)
    assert main_query.outerjoin.call_count == 4
    assert main_query.filter.call_count == 1
    main_query.order_by.assert_called_once()
    order_args = main_query.order_by.call_args.args
    assert len(order_args) == 7
    assert isinstance(order_args[0], Case)
    main_query.all.assert_called_once_with()

    first_join_target = main_query.outerjoin.call_args_list[0].args[0]
    assert first_join_target is last_assessment_subquery

    base_filter = _get_filter(main_query, 0)
    _assert_same_column(base_filter.left, Patient.dischargeDate)


def test_get_patients_builds_last_assessment_subquery(monkeypatch):
    _, _, last_assessment_query, _ = _setup_session(monkeypatch, rows=[])

    repo.get_patients()

    last_assessment_query.distinct.assert_called_once_with(
        NutritionalAssessment.nratendimento
    )
    assert last_assessment_query.order_by.call_count == 1
    last_assessment_query.subquery.assert_called_once_with("last_assessment")


def test_get_patients_builds_sev_subq_with_protocol_filter(monkeypatch):
    _, _, _, _, sev_subq_builder = _setup_session_with_sev_subq(
        monkeypatch, rows=[]
    )

    repo.get_patients()

    assert sev_subq_builder.filter.call_count == 2

    protocolo_filter = sev_subq_builder.filter.call_args_list[1].args[0]
    _assert_same_column(protocolo_filter.left, NutritionalScreening.protocolo)
    assert isinstance(protocolo_filter.right, Case)

    when_cond, when_result = protocolo_filter.right.whens[0]
    _assert_same_column(when_cond.left, Segment.type)
    assert when_cond.right.value == SegmentTypeEnum.ICU.value
    assert when_result.value == "MNUTRIC"
    assert protocolo_filter.right.else_.value == "NRS2002"

    assert sev_subq_builder.correlate.call_args.args == (Patient, Segment)


def test_get_patients_with_setor_applies_department_filter(monkeypatch):
    _, main_query, _, _ = _setup_session(monkeypatch, rows=[])

    repo.get_patients(setor=123)

    assert main_query.filter.call_count == 2
    setor_filter = _get_filter(main_query, 1)
    _assert_same_column(setor_filter.left, Patient.idDepartment)
    assert setor_filter.right.value == 123


def test_get_patients_with_ala_uti_is_case_insensitive(monkeypatch):
    _, main_query, _, _ = _setup_session(monkeypatch, rows=[])

    repo.get_patients(ala="uti")

    assert main_query.filter.call_count == 2
    ala_filter = _get_filter(main_query, 1)
    _assert_same_column(ala_filter.left, Segment.type)
    assert ala_filter.right.value == SegmentTypeEnum.ICU.value


def test_get_patients_with_ala_enfermaria_uses_not_icu_or_null(monkeypatch):
    _, main_query, _, _ = _setup_session(monkeypatch, rows=[])

    repo.get_patients(ala="Enfermaria")

    assert main_query.filter.call_count == 2
    ala_filter = _get_filter(main_query, 1)
    clauses = list(ala_filter.clauses)
    assert len(clauses) == 2

    not_icu_clause, null_clause = clauses
    _assert_same_column(not_icu_clause.left, Segment.type)
    assert not_icu_clause.right.value == SegmentTypeEnum.ICU.value
    _assert_same_column(null_clause.left, Segment.type)
    assert str(null_clause.right) == "NULL"


def test_get_patients_with_unknown_ala_filters_only_null_segment(monkeypatch):
    _, main_query, _, _ = _setup_session(monkeypatch, rows=[])

    repo.get_patients(ala="CLINICA")

    assert main_query.filter.call_count == 2
    ala_filter = _get_filter(main_query, 1)
    _assert_same_column(ala_filter.left, Segment.type)
    assert str(ala_filter.right) == "NULL"


def test_get_patients_with_setor_and_ala_applies_both_filters(monkeypatch):
    _, main_query, _, _ = _setup_session(monkeypatch, rows=[])

    repo.get_patients(setor=77, ala="UTI")

    assert main_query.filter.call_count == 3

    setor_filter = _get_filter(main_query, 1)
    ala_filter = _get_filter(main_query, 2)

    _assert_same_column(setor_filter.left, Patient.idDepartment)
    assert setor_filter.right.value == 77

    _assert_same_column(ala_filter.left, Segment.type)
    assert ala_filter.right.value == SegmentTypeEnum.ICU.value
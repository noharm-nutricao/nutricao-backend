"""Single-query retrieval of the LLM clinical context for one admission.
Issue #88, Step 1. Returns, for a given ``nratendimento``, the patient's
clinical context with **no PII**: scalar patient fields plus four collections
(screenings, glim, assessments, alerts), each built in the database as a JSON
array via ``json_agg(json_build_object(...))``.
The column whitelist of each table lives inside its ``json_build_object`` — that
is where we decide which columns survive (see the plan's field policy). ``id``,
user foreign keys and bookkeeping dates (``updated_at``/``created_at``) are
simply not selected. ``birthdate`` is never selected: age is derived in SQL.
Each child subquery is filtered by the literal ``admission_number`` rather than
correlated to ``Patient``. They are therefore self-contained scalar subqueries,
which keeps the limited collections (assessments/alerts) free of LATERAL.
"""

from datetime import datetime
from typing import Any, Mapping, Optional

from sqlalchemy import Connection, func, text
from sqlalchemy.dialects.postgresql import aggregate_order_by, insert

from models.main import db, dbSession
from models.nutritional import (
    NutritionalAlert,
    NutritionalAssessment,
    NutritionalGlim,
    NutritionalLlmSummary,
    NutritionalScreening,
)
from models.prescription import Patient

def get_clinical_context(admission_number: int, max_assessments: int, max_alerts: int = 3):
    """Return one row with the PII-free clinical context, or ``None``.
    Args:
        admission_number: the ``nratendimento`` (passed by the client).
        max_assessments: LIMIT applied to the assessments collection.
    Returns:
        A SQLAlchemy ``Row`` whose columns are the scalar patient fields plus
        ``screenings``, ``glim``, ``assessments`` and ``alerts`` (each already a
        list of dicts, deserialized from JSON), or ``None`` if the admission
        does not exist.
    """

    # idade derivada no SQL — birthdate (PII) nunca sai do banco; nulo -> nulo
    age_expr = func.date_part("year", func.age(Patient.birthdate)).cast(db.Integer)

    # --- coleções SEM limite: json_agg direto, ordenado dentro do agregado ---
    screenings = (
        db.session.query(
            func.coalesce(
                func.json_agg(
                    aggregate_order_by(
                        func.json_build_object(
                            "protocolo", NutritionalScreening.protocolo,
                            "nrs_nut", NutritionalScreening.nrs_nut,
                            "nrs_doenca", NutritionalScreening.nrs_doenca,
                            "nrs_idade", NutritionalScreening.nrs_idade,
                            "nrs_total", NutritionalScreening.nrs_total,
                            "nrs_completo", NutritionalScreening.nrs_completo,
                            "mn_idade", NutritionalScreening.mn_idade,
                            "mn_apache", NutritionalScreening.mn_apache,
                            "mn_sofa", NutritionalScreening.mn_sofa,
                            "mn_comor", NutritionalScreening.mn_comor,
                            "mn_dias", NutritionalScreening.mn_dias,
                            "mn_total", NutritionalScreening.mn_total,
                            "mn_apache_manual", NutritionalScreening.mn_apache_manual,
                            "mn_sofa_manual", NutritionalScreening.mn_sofa_manual,
                            "classificacao", NutritionalScreening.classificacao,
                        ),
                        NutritionalScreening.created_at.desc(),
                        NutritionalScreening.id.desc(),
                    )
                ),
                func.json_build_array(),
            )
        )
        .filter(NutritionalScreening.nratendimento == admission_number)
        .scalar_subquery()
        .label("screenings")
    )

    glim = (
        db.session.query(
            func.coalesce(
                func.json_agg(
                    aggregate_order_by(
                        func.json_build_object(
                            "diagnostico", NutritionalGlim.diagnostico,
                            "fenotipos", NutritionalGlim.fenotipos,
                            "etiologias", NutritionalGlim.etiologias,
                            "observacao", NutritionalGlim.observacao,
                        ),
                        NutritionalGlim.created_at.desc(),
                        NutritionalGlim.id.desc(),
                    )
                ),
                func.json_build_array(),
            )
        )
        .filter(NutritionalGlim.nratendimento == admission_number)
        .scalar_subquery()
        .label("glim")
    )

    # --- coleções COM limite: ordenar + LIMIT numa subquery interna; o id é
    # exposto só para ordenar o agregado externo (não entra no json_build_object) ---
    assessments_inner = (
        db.session.query(
            NutritionalAssessment.conduta.label("conduta"),
            NutritionalAssessment.frequencia.label("frequencia"),
            NutritionalAssessment.ingestao.label("ingestao"),
            NutritionalAssessment.meta_kcal.label("meta_kcal"),
            NutritionalAssessment.meta_prot.label("meta_prot"),
            NutritionalAssessment.created_at.label("created_at"),
            NutritionalAssessment.id.label("id"),
        )
        .filter(NutritionalAssessment.nratendimento == admission_number)
        .order_by(
            NutritionalAssessment.created_at.desc(),
            NutritionalAssessment.id.desc(),
        )
        .limit(max_assessments)
        .subquery("assessments_inner")
    )
    assessments = (
        db.session.query(
            func.coalesce(
                func.json_agg(
                    aggregate_order_by(
                        func.json_build_object(
                            "conduta", assessments_inner.c.conduta,
                            "frequencia", assessments_inner.c.frequencia,
                            "ingestao", assessments_inner.c.ingestao,
                            "meta_kcal", assessments_inner.c.meta_kcal,
                            "meta_prot", assessments_inner.c.meta_prot,
                            "created_at", assessments_inner.c.created_at,
                        ),
                        assessments_inner.c.created_at.desc(),
                        assessments_inner.c.id.desc(),
                    )
                ),
                func.json_build_array(),
            )
        )
        .select_from(assessments_inner)
        .scalar_subquery()
        .label("assessments")
    )

    alerts_inner = (
        db.session.query(
            NutritionalAlert.tipo.label("tipo"),
            NutritionalAlert.descricao.label("descricao"),
            NutritionalAlert.severidade.label("severidade"),
            NutritionalAlert.created_at.label("created_at"),
            NutritionalAlert.id.label("id"),
        )
        .filter(
            NutritionalAlert.nratendimento == admission_number,
            NutritionalAlert.ativo.is_(True),
        )
        .order_by(
            NutritionalAlert.created_at.desc(),
            NutritionalAlert.id.desc(),
        )
        .limit(max_alerts)
        .subquery("alerts_inner")
    )
    alerts = (
        db.session.query(
            func.coalesce(
                func.json_agg(
                    aggregate_order_by(
                        func.json_build_object(
                            "tipo", alerts_inner.c.tipo,
                            "descricao", alerts_inner.c.descricao,
                            "severidade", alerts_inner.c.severidade,
                        ),
                        alerts_inner.c.created_at.desc(),
                        alerts_inner.c.id.desc(),
                    )
                ),
                func.json_build_array(),
            )
        )
        .select_from(alerts_inner)
        .scalar_subquery()
        .label("alerts")
    )

    return (
        db.session.query(
            age_expr.label("age"),
            Patient.gender.label("gender"),
            Patient.weight.label("weight"),
            Patient.height.label("height"),
            Patient.weightDate.label("weight_date"),
            Patient.dialysis.label("dialysis"),
            Patient.lactating.label("lactating"),
            Patient.pregnant.label("pregnant"),
            Patient.id_icd.label("id_icd"),
            screenings,
            glim,
            assessments,
            alerts,
        )
        .filter(Patient.admissionNumber == admission_number)
        .first()
    )


def _current_schema() -> str:
    """Scheenant ativo, lido das execution options da conexão."""
    connection: Connection = db.session.connection()
    execute_options: Mapping[str, Any] = connection.get_execution_options()
    schema_translate_map: dict = execute_options.get("schema_translate_map", {})
    ret: str = schema_translate_map.get(None) or "demo"
    return ret


def _is_llm_resumo_table_ready() -> bool:
    """True se a tabela ``nutricional_llm_resumo`` existe no schema atual."""
    schema = _current_schema()
    return bool(
        db.session.execute(
            text(
                "SELECT EXISTS ("
                "    SELECT 1 FROM information_schema.tables "
                "    WHERE table_schema = :schema "
                "      AND table_name = 'nutricional_llm_resumo'"
                ")"
            ),
            {"schema": schema},
        ).scalar()
    )


def get_cached_summary(context_hash: str) -> Optional[NutritionalLlmSummary]:
    """Retorna o resumo já pronto para ``context_hash`` (HIT) ou ``None``.

    Se a tabela ainda não existe (sem migration), trata como MISS (``None``).
    """
    if not _is_llm_resumo_table_ready():
        return None

    return (
        db.session.query(NutritionalLlmSummary)
        .filter(
            NutritionalLlmSummary.context_hash == context_hash,
            NutritionalLlmSummary.status == "done",
        )
        .first()
    )


def insert_pending_job(
    context_hash: str,
    nratendimento: int,
    report_type: str,
    max_assessments: int,
    prompt_version: str,
    model: str,
) -> None:
    """Registra o pedido (status ``pending``) de forma idempotente.

    ``INSERT ... ON CONFLICT (context_hash) DO NOTHING`` + commit imediato (Opção A):
    o marcador fica visível na hora (dedup atômico) e a conexão é liberada antes do
    LLM. Após o commit, reaplica o schema (o ``schema_translate_map`` é perdido no
    commit). No-op se a tabela ainda não existe.
    """
    if not _is_llm_resumo_table_ready():
        return

    schema = _current_schema()

    stmt = (
        insert(NutritionalLlmSummary)
        .values(
            context_hash=context_hash,
            nratendimento=nratendimento,
            report_type=report_type,
            max_assessments=max_assessments,
            prompt_version=prompt_version,
            model=model,
            status="pending",
        )
        .on_conflict_do_nothing(index_elements=["context_hash"])
    )

    db.session.execute(stmt)
    db.session.commit()
    dbSession.setSchema(schema)


def mark_summary_done(
    context_hash: str,
    summary: str,
    tokens_used: Optional[int],
    processed_at: datetime,
) -> None:
    """Marca o resumo como pronto (``status='done'``) na linha do ``context_hash``.

    Sem commit próprio — segue a transação da request (o ``@api_endpoint`` commita). No-op se a
    tabela ainda não existe.
    """
    if not _is_llm_resumo_table_ready():
        return

    db.session.query(NutritionalLlmSummary).filter(
        NutritionalLlmSummary.context_hash == context_hash
    ).update(
        {
            "status": "done",
            "summary": summary,
            "tokens_used": tokens_used,
            "processed_at": processed_at,
        },
        synchronize_session=False,
    )
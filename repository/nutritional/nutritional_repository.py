from datetime import datetime, timedelta, timezone
from sqlalchemy import text

from exception.validation_error import ValidationError
from models.enums import SegmentTypeEnum
from models.main import db
from models.nutritional import NutritionalD7, NutritionalScreening
from models.prescription import Patient
from utils import status


def get_patients_repository():
    rows = db.session.query(Patient).all()

    return [
        {
            "id": r.admissionNumber,
            "fkpessoa": r.idPatient,
            "fkhospital": r.idHospital,
            "dtinternacao": r.admissionDate.isoformat() if r.admissionDate else None,
            "dtnascimento": r.birthdate.isoformat() if r.birthdate else None,
            "sexo": r.gender,
            "peso": r.weight,
            "altura": r.height,
            "leito": r.bed,
            "fksetor": r.idDepartment,
            "dtpeso": r.weightDate.isoformat() if r.weightDate else None,
            "anotacao": r.observation,
            "cor": r.skinColor,
            "update_at": r.update.isoformat() if r.update else None,
            "update_by": r.user,
            "alertatexto": r.alert,
            "alertadata": r.alertDate.isoformat() if r.alertDate else None,
            "alertavigencia": r.alertExpire.isoformat() if r.alertExpire else None,
            "alerta_by": r.alertBy,
            "motivoalta": r.dischargeReason,
            "dtalta": r.dischargeDate.isoformat() if r.dischargeDate else None,
            "dialise": r.dialysis,
            "lactante": r.lactating,
            "gestante": r.pregnant,
            "st_concilia": r.st_conciliation,
            "marcadores": r.tags if r.tags else [],
            "medico_responsavel": r.responsiblePhysician,
            "idcid": r.id_icd,
            "dt_ultima_transferencia": r.lastTransferDate.isoformat() if r.lastTransferDate else None,
            "dt_alta_prevista": r.dischargeDateForecast.isoformat() if r.dischargeDateForecast else None,
            "cidade": r.city,
        }
        for r in rows
    ]


def save_manual_mnutric(admission_number: int, mnutric: dict):
    """Persiste entrada manual do nutricionista (PUT /mnutric-manual).

    Seta mn_apache_manual=True e mn_sofa_manual=True sinalizando que
    APACHE II e SOFA foram informados — libera dados_incompletos=False no frontend.
    """
    if not _is_nutritional_screening_table_ready():
        return None

    screening = (
        db.session.query(NutritionalScreening)
        .filter(NutritionalScreening.nratendimento == admission_number)
        .filter(NutritionalScreening.protocolo == "MNUTRIC")
        .first()
    )

    if screening is None:
        screening = NutritionalScreening()
        screening.nratendimento = admission_number
        screening.protocolo = "MNUTRIC"
        db.session.add(screening)

    screening.mn_apache = mnutric["apache"]
    screening.mn_sofa = mnutric["sofa"]
    screening.mn_apache_manual = True
    screening.mn_sofa_manual = True
    screening.mn_idade = mnutric["age"]
    screening.mn_comor = mnutric["comorbity"]
    screening.mn_dias = mnutric["daysUTI"]
    screening.mn_total = mnutric["total"]
    screening.classificacao = mnutric["classify"]

    db.session.flush()

    return screening


def update_mnutric_scores(admission_number: int, mnutric: dict):
    """Atualiza scores calculados pelo job periódico.

    Preserva mn_apache, mn_sofa e os flags mn_apache_manual/mn_sofa_manual —
    somente o job chama esta função. Não altera a condição dados_incompletos.
    """
    if not _is_nutritional_screening_table_ready():
        return None

    screening = (
        db.session.query(NutritionalScreening)
        .filter(NutritionalScreening.nratendimento == admission_number)
        .filter(NutritionalScreening.protocolo == "MNUTRIC")
        .order_by(NutritionalScreening.id.desc())
        .first()
    )

    if screening is None:
        screening = NutritionalScreening()
        screening.nratendimento = admission_number
        screening.protocolo = "MNUTRIC"
        screening.mn_apache_manual = False
        screening.mn_sofa_manual = False
        db.session.add(screening)

    screening.mn_idade = mnutric["age"]
    screening.mn_comor = mnutric["comorbity"]
    screening.mn_dias = mnutric["daysUTI"]

    dados_incompletos = not screening.mn_apache_manual or not screening.mn_sofa_manual
    if not dados_incompletos:
        screening.mn_total = mnutric["total"]
        screening.classificacao = mnutric["classify"]

    db.session.flush()

    return screening

def get_saved_mnutric(admission_number: int):
    if not _is_nutritional_screening_table_ready():
        return None

    return (
        db.session.query(NutritionalScreening)
        .filter(NutritionalScreening.nratendimento == admission_number)
        .filter(NutritionalScreening.protocolo == "MNUTRIC")
        .order_by(NutritionalScreening.id.desc())
        .first()
    )

def get_active_admissions(schema: str):
    """Return all active admissions with ICU protocol flag.

    Active means dtalta IS NULL. Uses LEFT JOINs on segmentosetor and segmento
    so patients whose sector has no segment mapping are still included
    (is_icu defaults to False via COALESCE).

    Returns:
        List of rows with fields:
            nratendimento, fksetor, dtnascimento, dtinternacao,
            peso, altura, idcid, tp_segmento (int|None), is_icu (bool)
    """
    db.session.execute(text(f'SET LOCAL search_path TO "{schema}"'))
    query = text(
        """
        SELECT
            p.nratendimento,
            p.fksetor,
            p.dtnascimento,
            p.dtinternacao,
            p.peso,
            p.altura,
            p.idcid,
            p.dt_ultima_transferencia,
            seg.tp_segmento,
            COALESCE(seg.tp_segmento = :icu_type, false) AS is_icu
        FROM pessoa p
        LEFT JOIN segmentosetor ss  ON ss.fksetor     = p.fksetor
        LEFT JOIN segmento seg      ON seg.idsegmento  = ss.idsegmento
        WHERE p.dtalta IS NULL
        """
    )
    result = db.session.execute(query, {"icu_type": SegmentTypeEnum.ICU.value})
    return result.fetchall()

def get_active_d7(nratendimento: int):
    return (
        db.session.query(NutritionalD7)
        .filter(
            NutritionalD7.nratendimento == nratendimento,
            NutritionalD7.concluido.is_(False),
        )
        .first()
    )


def upsert_d7(nratendimento: int, idusuario: int) -> NutritionalD7:
    now = datetime.now(timezone.utc)
    dt_prevista = now + timedelta(days=7)

    d7 = get_active_d7(nratendimento)

    if d7 is None:
        d7 = NutritionalD7()
        d7.nratendimento = nratendimento
        d7.idusuario = idusuario
        d7.created_at = now
        db.session.add(d7)
    else:
        d7.updated_at = now

    d7.dt_prevista = dt_prevista
    d7.concluido = False

    db.session.flush()
    return d7


def close_d7(id: int, nratendimento: int) -> NutritionalD7:
    d7 = (
        db.session.query(NutritionalD7)
        .filter(
            NutritionalD7.id == id,
            NutritionalD7.nratendimento == nratendimento,
        )
        .first()
    )

    if d7 is None:
        raise ValidationError(
            "D7 não encontrado",
            "errors.notFound",
            status.HTTP_404_NOT_FOUND,
        )

    d7.concluido = True
    d7.updated_at = datetime.now(timezone.utc)

    db.session.flush()
    return d7


# Verify if we have the screening table and their columns.
def _is_nutritional_screening_table_ready() -> bool:
    connection = db.session.connection()
    schema = connection.get_execution_options().get("schema_translate_map", {}).get(None) or "demo"

    table_exists = bool(
        db.session.execute(
            text(
                "SELECT EXISTS ("
                "    SELECT 1 FROM information_schema.tables "
                "    WHERE table_schema = :schema "
                "      AND table_name = 'nutricional_triagem'"
                ")"
            ),
            {"schema": schema},
        ).scalar()
    )

    if not table_exists:
        return False

    required_columns = {
        "id",
        "nratendimento",
        "protocolo",
        "mn_idade",
        "mn_apache",
        "mn_sofa",
        "mn_comor",
        "mn_dias",
        "mn_total",
        "mn_apache_manual",
        "mn_sofa_manual",
        "classificacao",
    }
    existing_columns = {
        row[0]
        for row in db.session.execute(
            text(
                "SELECT column_name "
                "FROM information_schema.columns "
                "WHERE table_schema = :schema "
                "  AND table_name = 'nutricional_triagem'"
            ),
            {"schema": schema},
        ).all()
    }

    return required_columns.issubset(existing_columns)

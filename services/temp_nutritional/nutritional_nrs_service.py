from datetime import datetime
import re
from typing import Any, Callable, Optional
import unicodedata

from models.main import db
from models.prescription import Patient
from models.temp_nutritional import NutricionalNrs, NutricionalTriagem
from repository.nutritional_temp.nutritional_nrs_repository import (
    get_nrs_assessment,
    get_or_create_triagem,
    get_patient_department,
    update_triagem,
)
from services.temp_nutritional.nutritional_dtos import NrsScoreDTO


def score_nrs_component_a(nrs_row: Optional[NutricionalNrs]) -> Optional[int]:
    """
    Calcula o Componente A (Comprometimento Nutricional) utilizando o formulário
    fechado do hospital como fonte única da verdade, sem recálculo com dados internos.
    Retorna 0 a 3, ou None caso o formulário não tenha sido preenchido.
    """
    if not nrs_row:
        return None
    tem_risco_admissional = any(
        [
            getattr(nrs_row, "triagem_imc_baixo", False),
            getattr(nrs_row, "triagem_perda_peso", False),
            getattr(nrs_row, "triagem_ingestao_reduzida", False),
            getattr(nrs_row, "triagem_doenca_grave", False),
        ]
    )
    if not tem_risco_admissional:
        return 0
    return getattr(nrs_row, "score_comprometimento", 0)


_ICU_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bu[\s\./\-_]*t[\s\./\-_]*i\b", re.IGNORECASE),
    re.compile(r"\bcti\b", re.IGNORECASE),
    re.compile(r"\butin\b", re.IGNORECASE),
    re.compile(r"\bunidade\s+de\s+terapia\s+intensiva\b", re.IGNORECASE),
    re.compile(r"\bunidade\s+de\s+tratamento\s+intensiv[oa]\b", re.IGNORECASE),
    re.compile(r"\bcentro\s+de\s+terapia\s+intensiva\b", re.IGNORECASE),
    re.compile(r"\bcentro\s+de\s+tratamento\s+intensiv[oa]\b", re.IGNORECASE),
    re.compile(r"\bunidade\s+de\s+cuidados?\s+intensivos?\b", re.IGNORECASE),
    re.compile(r"\bcuidados?\s+intensivos?\b", re.IGNORECASE),
    re.compile(r"\bterapia\s+intensiva\b", re.IGNORECASE),
    re.compile(r"\btratamento\s+intensiv[oa]\b", re.IGNORECASE),
    re.compile(r"\buti\s+(adult[oa]|adulto\s+geral)\b", re.IGNORECASE),
    re.compile(r"\buti\s+(pediatric[oa]|pediatria|pediatrica)\b", re.IGNORECASE),
    re.compile(r"\buti\s+(neo|neonatal|neonatologia)\b", re.IGNORECASE),
    re.compile(r"\buti\s+coronarian[ao]\b", re.IGNORECASE),
    re.compile(r"\bneo\s*uti\b", re.IGNORECASE),
)


def _normalize_department_name(department: str) -> str:
    normalized = unicodedata.normalize("NFKD", department)
    without_accents = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    collapsed_spaces = re.sub(r"\s+", " ", without_accents)
    return collapsed_spaces.strip().lower()


def is_uti_helper(patient_department: str) -> bool:
    if not patient_department:
        return False
    normalized_department = _normalize_department_name(patient_department)
    return any(regex.search(normalized_department) for regex in _ICU_PATTERNS)


def is_uti_wrapper(
    nratendimento: int, get_patient_department_fn: Callable[[int], Optional[str]]
) -> bool:
    department: Optional[str] = get_patient_department_fn(nratendimento)
    return is_uti_helper(department)


def is_uti(nratendimento: int) -> bool:
    return is_uti_wrapper(nratendimento, get_patient_department)


def score_nrs_component_b(
    nratendimento: int, cid: str, is_uti_fn: Callable[[int], bool]
) -> int:
    # Camada 1: setor UTI -> score 3 independente do CID
    if is_uti_fn(nratendimento):
        return 3
    if not cid:
        return 0
    # Camada 2: override de 3 chars (mais especifico)
    override = db.query(
        "SELECT score_nrs FROM demo.nutricional_cid_override WHERE prefixo3 = %s",
        [cid[:3]],
    )
    if override:
        return override[0].score_nrs
    # Camada 3: fallback por capitulo (1 char)
    chapter = db.query(
        "SELECT score_nrs FROM demo.nutricional_cid_gravidade WHERE prefixo = %s",
        [cid[0].upper()],
    )
    return chapter[0].score_nrs if chapter else 0


def calculate_age(dt_nascimento: datetime):
    return datetime.now().year - dt_nascimento.year


def build_nrs_update(
    patient: Patient,
    triagem: NutricionalTriagem,
    nrs_row: Optional[NutricionalNrs],
    *,
    score_nrs_component_a_fn: Callable[[Optional[Any]], Optional[int]],
    score_nrs_component_b_fn: Callable[[int, str, Callable], int],
    calc_age_fn: Callable[[datetime], int],
    now_fn: Callable[[], datetime],
    is_uti_fn: Callable[[int],bool]
) -> NrsScoreDTO:
    if nrs_row:
        comp_a = score_nrs_component_a_fn(nrs_row)
        nrs_ref_at = nrs_row.updated_at
    else:
        comp_a = None
        nrs_ref_at = triagem.nrs_ref_at
    comp_b = score_nrs_component_b_fn(patient.admissionNumber, patient.idcid, is_uti_fn)
    comp_c = 1 if calc_age_fn(patient.dtnascimento) >= 70 else 0
    completo = comp_a is not None
    total = (comp_a or 0) + comp_b + comp_c
    return NrsScoreDTO(
        id=triagem.id,
        nrs_nut=comp_a,
        nrs_doenca=comp_b,
        nrs_idade=comp_c,
        nrs_total=total,
        nrs_completo=completo,
        nrs_ref_at=nrs_ref_at,
        calculado_at=now_fn(),
    )


def __recalculate_nrs(
    patient: Patient,
    *,
    get_or_create_triagem_fn: Callable[[int], Any],
    nutritional_nrs_repo_fn: Callable[[int], Optional[NutricionalNrs]],
    updater_func: Callable[[NutricionalTriagem, NrsScoreDTO], None],
    score_nrs_component_a_fn: Callable[[Optional[NutricionalNrs]], Optional[int]],
    score_nrs_component_b_fn: Callable[[str, bool], int],
    calc_age_fn: Callable[[datetime], int],
    now_fn: Callable[[], datetime] = datetime.now,
) -> None:
    triagem: NutricionalTriagem = get_or_create_triagem_fn(patient.nratendimento)
    nrs_row: Optional[NutricionalNrs] = nutritional_nrs_repo_fn(patient.nratendimento)
    nrs_score_dto: NrsScoreDTO = build_nrs_update(
        patient,
        triagem,
        nrs_row,
        score_nrs_component_a_fn=score_nrs_component_a_fn,
        score_nrs_component_b_fn=score_nrs_component_b_fn,
        calc_age_fn=calc_age_fn,
        now_fn=now_fn,
    )
    updater_func(
        triagem,
        nrs_score_dto,
    )
    return None


def recalculate_nrs(patient: Patient) -> None:
    __recalculate_nrs(
        patient,
        get_or_create_triagem_fn=get_or_create_triagem,
        nutritional_nrs_repo_fn=get_nrs_assessment,
        updater_func=update_triagem,
        score_nrs_component_a_fn=score_nrs_component_a,
        score_nrs_component_b_fn=score_nrs_component_b,
        calc_age_fn=calculate_age,
        now_fn=datetime.now,
    )
    return None

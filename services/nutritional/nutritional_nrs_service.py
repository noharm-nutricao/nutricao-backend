from datetime import datetime
import re

from typing import Any, Callable, Optional
import unicodedata
from models.enums import SegmentTypeEnum
from models.nutritional import NutritionalNrs, NutritionalScreening
from models.prescription import Patient
from repository.nutritional.nutritional_nrs_repository import (
    get_cid_mappings_cached,
    get_nrs_assessment,
    get_or_create_triagem,
    get_patient_segment_type,
    get_patient_department,
    update_triagem,
)
from services.nutritional.nutritional_dtos import CidMappings, NrsScoreDTO

ICU_PATTERNS: tuple[re.Pattern[str], ...] = (
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


def score_nrs_component_a(nrs_row: Optional[NutritionalNrs]) -> Optional[int]:
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


def _normalize_department_name(department: str) -> str:
    normalized = unicodedata.normalize("NFKD", department)
    without_accents = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    collapsed_spaces = re.sub(r"\s+", " ", without_accents)
    return collapsed_spaces.strip().lower()


def is_uti_helper(patient_department: Optional[str]) -> bool:
    if not patient_department:
        return False
    normalized_department = _normalize_department_name(patient_department)
    return any(regex.search(normalized_department) for regex in ICU_PATTERNS)


def is_uti_wrapper(
    nratendimento: int,
    get_patient_segment_type_fn: Callable[[int], Optional[int]],
    get_patient_department_fn: Callable[[int], Optional[str]],
) -> bool:
    segment_type: Optional[int] = get_patient_segment_type_fn(nratendimento)
    if segment_type is not None:
        return segment_type == SegmentTypeEnum.ICU.value
    department: Optional[str] = get_patient_department_fn(nratendimento)
    return is_uti_helper(department)


def is_uti(nratendimento: int) -> bool:
    return is_uti_wrapper(
        nratendimento,
        get_patient_segment_type,
        get_patient_department,
    )


def classify_nrs_score(nrs_total: int) -> str:
    if nrs_total >= 5:
        return "cr"
    if nrs_total >= 3:
        return "al"
    if nrs_total >= 1:
        return "md"
    return "bx"


def score_nrs_component_b(is_icu: bool, cid: str) -> int:
    return _score_nrs_component_b(is_icu, cid, get_cid_mappings_cached)


def _score_nrs_component_b(
    is_icu: bool,
    cid: str,
    get_cid_mappings_cached_fn: Callable[[], CidMappings],
) -> int:
    if is_icu:
        return 3
    if not cid:
        return 0

    mappings: CidMappings = get_cid_mappings_cached_fn()
    if len(cid) >= 3:
        prefix3: str = cid[:3]
        if prefix3 in mappings.overrides:
            return mappings.overrides[prefix3]

    chapter = cid[0].upper()
    return mappings.chapters.get(chapter, 0)


def calculate_age(dt_nascimento: datetime) -> int:
    hoje = datetime.today()
    return hoje.year - dt_nascimento.year - (
        (hoje.month, hoje.day) < (dt_nascimento.month, dt_nascimento.day)
    )


def build_nrs_update(
    patient: Patient,
    triagem: NutritionalScreening,
    nrs_row: Optional[NutritionalNrs],
    is_icu: bool,
    *,
    score_nrs_component_a_fn: Callable[[Optional[Any]], Optional[int]],
    score_nrs_component_b_fn: Callable[[bool, str], int],
    calc_age_fn: Callable[[datetime], int],
    now_fn: Callable[[], datetime]
) -> NrsScoreDTO:
    comp_a: Optional[int]
    nrs_ref_at: datetime
    if nrs_row:
        comp_a = score_nrs_component_a_fn(nrs_row)
        nrs_ref_at = nrs_row.updated_at
    else:
        comp_a = None
        nrs_ref_at = triagem.nrs_ref_at
    comp_b: int = score_nrs_component_b_fn(is_icu, patient.id_icd)
    comp_c: int = 1 if calc_age_fn(patient.birthdate) >= 70 else 0
    completo: bool = comp_a is not None
    total: int = (comp_a or 0) + comp_b + comp_c
    classificacao: str = classify_nrs_score(total)
    return NrsScoreDTO(
        id=triagem.id,
        nrs_nut=comp_a,
        nrs_doenca=comp_b,
        nrs_idade=comp_c,
        nrs_total=total,
        classificacao=classificacao,
        nrs_completo=completo,
        nrs_ref_at=nrs_ref_at,
        calculado_at=now_fn(),
    )


def __recalculate_nrs(
    patient: Patient,
    is_icu: bool,
    *,
    get_or_create_triagem_fn: Callable[[int], Any] = get_or_create_triagem,
    nutritional_nrs_repo_fn: Callable[
        [int], Optional[NutritionalNrs]
    ] = get_nrs_assessment,
    updater_func: Callable[[NutritionalScreening, NrsScoreDTO], None] = update_triagem,
    score_nrs_component_a_fn: Callable[
        [Optional[NutritionalNrs]], Optional[int]
    ] = score_nrs_component_a,
    score_nrs_component_b_fn: Callable[[bool, str], int] = score_nrs_component_b,
    calc_age_fn: Callable[[datetime], int] = calculate_age,
    now_fn: Callable[[], datetime] = datetime.now
) -> None:
    triagem: NutritionalScreening = get_or_create_triagem_fn(patient.admissionNumber)
    nrs_row: Optional[NutritionalNrs] = nutritional_nrs_repo_fn(patient.admissionNumber)
    nrs_score_dto: NrsScoreDTO = build_nrs_update(
        patient,
        triagem,
        nrs_row,
        is_icu,
        score_nrs_component_a_fn=score_nrs_component_a_fn,
        score_nrs_component_b_fn=score_nrs_component_b_fn,
        calc_age_fn=calc_age_fn,
        now_fn=now_fn,
    )
    updater_func(
        triagem,
        nrs_score_dto,
    )
    return nrs_score_dto


def recalculate_nrs(patient: Patient, is_icu: bool) -> NrsScoreDTO:
    return __recalculate_nrs(patient, is_icu)

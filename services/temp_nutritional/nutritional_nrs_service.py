from datetime import datetime
from typing import Any, Callable, Optional

from models.prescription import Patient
from models.temp_nutritional import NutricionalNrs, NutricionalTriagem
from repository.nutritional_temp.nutritional_nrs_repository import get_nrs_assessment
from services.temp_nutritional.nutritional_dtos import NrsScoreDTO


def score_nrs_component_a(nrs_row) -> int | None:
    """
    Calcula o Componente A (Comprometimento Nutricional) utilizando o formulário
    fechado do hospital como fonte única da verdade, sem recálculo com dados internos.
    Retorna 0 a 3, ou None caso o formulário não tenha sido preenchido.
    """
    # Se o hospital ainda não enviou a triagem admissional, o score fica incompleto (Parcial)
    if not nrs_row:
        return None

    # ETAPA 1: Triagem Inicial (Gatekeeper)
    # Verifica se a equipe assistencial marcou 'Sim' (True) para qualquer um dos 4 fatores
    tem_risco_admissional = any(
        [
            getattr(nrs_row, "triagem_imc_baixo", False),
            getattr(nrs_row, "triagem_perda_peso", False),
            getattr(nrs_row, "triagem_ingestao_reduzida", False),
            getattr(nrs_row, "triagem_doenca_grave", False),
        ]
    )

    # Se todas as respostas da triagem inicial forem negativas ('Não'), o protocolo da Nestlé
    # determina que não há risco. A avaliação encerra aqui com nota 0.
    if not tem_risco_admissional:
        return 0

    # ETAPA 2: Triagem Final (Score de Comprometimento Nutricional)
    # Se o paciente pontuou em qualquer risco na Etapa 1, resgatamos a nota (0 a 3)
    # que o profissional de saúde selecionou na tela do prontuário eletrônico.
    return getattr(nrs_row, "score_comprometimento", 0)


def score_nrs_component_b(cid: str, is_uti: bool) -> int:
    # Camada 1: setor UTI -> score 3 independente do CID
    if is_uti:
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


# TODO: it's necessary to update the bellow functions
def get_or_create_triagem(nr_atendimento: int):
    return None


def calculate_age(dt_nascimento: datetime):
    return None


def update_triagem(nr_atentimento: int, triagem: NrsScoreDTO) -> None:
    return None


def build_nrs_update(
    patient: Patient,
    triagem: NutricionalTriagem,
    nrs_row: Optional[NutricionalNrs],
    *,
    score_nrs_component_a_fn: Callable[[Any | None], Optional[int]],
    score_nrs_component_b_fn: Callable[[str, bool], int],
    calc_age_fn: Callable[[datetime], int],
    now_fn: Callable[[], datetime],
) -> NrsScoreDTO:
    if nrs_row:
        comp_a = score_nrs_component_a_fn(nrs_row)
        nrs_ref_at = nrs_row.updated_at
    else:
        comp_a = None
        nrs_ref_at = triagem.nrs_ref_at
    comp_b = score_nrs_component_b_fn(patient.idcid, patient.is_uti)
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
    updater_func: Callable[[int, dict[str, Any]], None],
    score_nrs_component_a_fn: Callable[[Any | None], Optional[int]],
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
        patient.nratendimento,
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

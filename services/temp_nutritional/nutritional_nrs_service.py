from dataclasses import dataclass
from datetime import datetime
from typing import Optional
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
    tem_risco_admissional = any([
        getattr(nrs_row, 'triagem_imc_baixo', False),
        getattr(nrs_row, 'triagem_perda_peso', False),
        getattr(nrs_row, 'triagem_ingestao_reduzida', False),
        getattr(nrs_row, 'triagem_doenca_grave', False)
    ])

    # Se todas as respostas da triagem inicial forem negativas ('Não'), o protocolo da Nestlé
    # determina que não há risco. A avaliação encerra aqui com nota 0.
    if not tem_risco_admissional:
        return 0

    # ETAPA 2: Triagem Final (Score de Comprometimento Nutricional)
    # Se o paciente pontuou em qualquer risco na Etapa 1, resgatamos a nota (0 a 3)
    # que o profissional de saúde selecionou na tela do prontuário eletrônico.
    return getattr(nrs_row, 'score_comprometimento', 0)
def score_nrs_component_b(cid: str, is_uti: bool) -> int:
    # Camada 1: setor UTI -> score 3 independente do CID
    if is_uti:
        return 3
    if not cid:
        return 0
    # Camada 2: override de 3 chars (mais especifico)
    override = db.query(
        "SELECT score_nrs FROM demo.nutricional_cid_override WHERE prefixo3 = %s",
        [cid[:3]]
    )
    if override:
        return override[0].score_nrs
    # Camada 3: fallback por capitulo (1 char)
    chapter = db.query(
        "SELECT score_nrs FROM demo.nutricional_cid_gravidade WHERE prefixo = %s",
        [cid[0].upper()]
    )
    return chapter[0].score_nrs if chapter else 0

def recalculate_nrs(patient) -> None:
    # Garante a existência do registro na tabela base
    triagem = get_or_create_triagem(patient.nratendimento)
 
    # Busca a última triagem enviada pelo hospital de forma direta e rápida (O(1))
    nrs_rows = db.query(
        '''
        SELECT * FROM demo.nutricional_nrs
        WHERE nratendimento = %s
        ORDER BY updated_at DESC LIMIT 1
        ''',
        [patient.nratendimento]
    )
 
    # Lógica limpa: se o hospital já enviou algum questionário, calcula o Componente A
    if nrs_rows:
        nrs_row = nrs_rows
        # score_nrs_component_a utiliza a nota do formulário como fonte da verdade
        comp_a = score_nrs_component_a(nrs_row)
        nrs_ref_at = nrs_row.updated_at
    else:
        # Se o hospital nunca enviou nada para este atendimento, o score A fica nulo
        comp_a = None
        nrs_ref_at = triagem.nrs_ref_at

    # Recalcula variáveis que podem mudar a qualquer momento da internação
    comp_b = score_nrs_component_b(patient.idcid, patient.is_uti)
    comp_c = 1 if calcular_idade(patient.dtnascimento) >= 70 else 0
 
    # Define flags de completude e o somatório
    completo = comp_a is not None
    total    = (comp_a or 0) + comp_b + comp_c
 
    # Atualiza a tabela de triagem de forma consolidada
    update_triagem(patient.nratendimento, {
        'nrs_nut':      comp_a,
        'nrs_doenca':   comp_b,
        'nrs_idade':    comp_c,
        'nrs_total':    total,
        'nrs_completo': completo,
        'nrs_ref_at':   nrs_ref_at,
        'calculado_at': datetime.now(),
    })
    
    return None
#TODO: it's necessary to update the bellow functions
@dataclass
class Triagem:
    nrs_nut: Optional[int]
    nrs_doenca: int
    nrs_idade: int
    nrs_total: int
    nrs_completo: bool
    calculado_at: datetime

def get_or_create_triagem(nr_atendimento: int):
    return None
def calcular_idade(dt_nascimento: datetime):
    return None
def update_triagem(nr_atentimento: int, triagem: Triagem)->None:
    return None
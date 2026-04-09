from typing import Optional

from models.main import db
from models.temp_nutritional import NutricionalNrs, NutricionalTriagem


def get_nrs_assessment(nratendimento: int) -> Optional[NutricionalNrs]:
    return (
        db.session.query(NutricionalNrs)
        .filter(NutricionalNrs.nratendimento == nratendimento)
        .order_by(NutricionalNrs.updated_at.desc())
        .first()
    )


def get_or_create_triagem(nratendimento: int) -> NutricionalTriagem:
    triagem: Optional[NutricionalTriagem] = (
        db.session.query(NutricionalTriagem)
        .filter(NutricionalTriagem.nratendimento == nratendimento)
        .first()
    )
    if triagem:
        return triagem

    triagem = NutricionalTriagem(
        nratendimento=nratendimento,
        protocolo="NRS2002",
        nrs_nut=None,
        nrs_doenca=None,
        nrs_idade=None,
        nrs_total=None,
        nrs_completo=False,
        nrs_ref_at=None,
        mn_idade=None,
        mn_apache=None,
        mn_sofa=None,
        mn_comor=None,
        mn_dias=None,
        mn_total=None,
        mn_apache_manual=None,
        mn_sofa_manual=None,
        classificacao=None,
        calculado_at=None,
    )
    db.session.add(triagem)
    db.session.flush()
    return triagem
